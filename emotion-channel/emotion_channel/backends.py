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
    """Talks directly to the badge's GATT service over Bluetooth LE."""

    def __init__(self, address: str, secret: bytes, *, uuids: dict | None = None):
        self.address = address
        self.secret = secret
        self.uuids = uuids or config.DEFAULT_UUIDS

    async def send(self, frame: bytes) -> None:
        from bleak import BleakClient
        from bleak.exc import BleakError
        try:
            async with BleakClient(self.address) as c:
                await c.write_gatt_char(
                    self.uuids["emotion"], self.secret + frame, response=True
                )
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            raise BadgeUnreachable(str(e)) from e

    async def read_state(self) -> bytes:
        from bleak import BleakClient
        from bleak.exc import BleakError
        try:
            async with BleakClient(self.address) as c:
                return bytes(await c.read_gatt_char(self.uuids["state"]))
        except (BleakError, asyncio.TimeoutError, OSError) as e:
            raise BadgeUnreachable(str(e)) from e
