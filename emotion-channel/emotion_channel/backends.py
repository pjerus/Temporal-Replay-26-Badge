"""Transport backends for the emotion channel.

A Backend sends an encoded emotion frame and reads the device state. The
BLE backend talks straight to the badge (Option E); the HTTP backend
(Task 9) talks to the bridge (Option D). Both carry the same frames."""
from __future__ import annotations

import asyncio
from typing import Protocol

from . import config
from .frame import MOODS


class BadgeUnreachable(Exception):
    """The badge could not be reached (out of range, disconnected, etc.)."""


class Backend(Protocol):
    async def send(self, frame: bytes) -> None: ...
    async def read_state(self) -> bytes: ...


def parse_state(buf: bytes) -> dict:
    """Decode the 7-byte state characteristic. Mirrors the layout in
    firmware/src/emotion/EmotionBleService.cpp."""
    if len(buf) != 7:
        raise ValueError(f"state must be 7 bytes, got {len(buf)}")
    flags, ov_mood, ov_inten, ms_lo, ms_hi, auto_mood, batt = buf
    active = bool(flags & 0x01)
    ds = ms_lo | (ms_hi << 8)
    override = None
    if active:
        override = {
            "mood": MOODS[ov_mood] if ov_mood < len(MOODS) else "unknown",
            "intensity": ov_inten / 255,
            "ms_left": None if ds == 0xFFFF else ds * 100,  # None = latch
        }
    return {
        "override": override,
        "autonomous": MOODS[auto_mood] if auto_mood < len(MOODS) else "unknown",
        "face_on_screen": bool(flags & 0x02),
        "battery_pct": batt,
    }


class BleBackend:
    """Talks directly to the badge's GATT service over Bluetooth LE.

    Holds one connection and reuses it across send/read — reconnecting per
    call is slow and, on macOS, the address often won't re-resolve between
    back-to-back connects."""

    def __init__(self, address: str, secret: bytes, *, uuids: dict | None = None):
        self.address = address
        self.secret = secret
        self.uuids = uuids or config.DEFAULT_UUIDS
        self._client = None

    async def _ensure(self):
        from bleak import BleakClient
        from bleak.exc import BleakError
        if self._client is not None and self._client.is_connected:
            return self._client
        try:
            self._client = BleakClient(self.address)
            await self._client.connect()
            return self._client
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            self._client = None
            raise BadgeUnreachable(str(e)) from e

    async def send(self, frame: bytes) -> None:
        from bleak.exc import BleakError
        c = await self._ensure()
        try:
            await c.write_gatt_char(
                self.uuids["emotion"], self.secret + frame, response=True
            )
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            raise BadgeUnreachable(str(e)) from e

    async def read_state(self) -> bytes:
        from bleak.exc import BleakError
        c = await self._ensure()
        try:
            return bytes(await c.read_gatt_char(self.uuids["state"]))
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            raise BadgeUnreachable(str(e)) from e

    async def clear(self) -> None:
        from bleak.exc import BleakError
        from .frame import encode_clear
        c = await self._ensure()
        try:
            await c.write_gatt_char(self.uuids["emotion"], self.secret + encode_clear(), response=True)
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            raise BadgeUnreachable(str(e)) from e

    async def sequence(self, steps, loop: bool = False) -> None:
        # Direct BLE: step through here (blocks the caller for the timeline).
        from .frame import encode_emotion
        while True:
            for s in steps:
                await self.send(encode_emotion(s["mood"], s["intensity"], s["ttl_ms"], source=s.get("source", 0)))
                await asyncio.sleep(s["ttl_ms"] / 1000)
            if not loop:
                return

    async def close(self) -> None:
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()
        self._client = None


class HttpBackend:
    """Client-side mirror of the bridge, so a skill can drive a badge
    through the HTTP endpoint with the same EmotionClient it would use for
    direct BLE. Decodes the frame and reposts it as the bridge's JSON."""

    def __init__(self, base_url: str, api_key: str, target: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.target = target
        self._cached = None  # state bytes from the last send, consumed by read_state

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def send(self, frame: bytes) -> None:
        import base64
        import httpx
        from .frame import decode_emotion
        d = decode_emotion(frame)
        payload = {
            "target": self.target, "mood": d["mood"], "intensity": d["intensity"],
            "ttl_ms": d["ttl_ms"], "source": d["source"],
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.base_url}/emotion", json=payload, headers=self._headers())
        if r.status_code == 502:
            raise BadgeUnreachable(r.json().get("error", "badge unreachable"))
        r.raise_for_status()
        self._cached = base64.b64decode(r.json()["state_raw"])

    async def read_state(self) -> bytes:
        import base64
        import httpx
        if self._cached is not None:
            raw, self._cached = self._cached, None
            return raw
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.base_url}/state", params={"target": self.target}, headers=self._headers())
        if r.status_code == 502:
            raise BadgeUnreachable(r.json().get("error", "badge unreachable"))
        r.raise_for_status()
        return base64.b64decode(r.json()["state_raw"])

    async def clear(self) -> None:
        import base64
        import httpx
        async with httpx.AsyncClient() as c:
            r = await c.request("DELETE", f"{self.base_url}/emotion",
                                params={"target": self.target}, headers=self._headers())
        if r.status_code == 502:
            raise BadgeUnreachable(r.json().get("error", "badge unreachable"))
        r.raise_for_status()
        self._cached = base64.b64decode(r.json()["state_raw"])

    async def sequence(self, steps, loop: bool = False) -> None:
        # Via the bridge the sequence runs server-side; this just hands it off.
        import httpx
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.base_url}/sequence",
                             json={"target": self.target, "steps": list(steps), "loop": loop},
                             headers=self._headers())
        r.raise_for_status()
