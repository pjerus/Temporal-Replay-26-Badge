"""The one client an AI (or a skill) uses to inject an emotion and read
the face's state. Transport-agnostic: hand it a BleBackend (direct) or an
HttpBackend (via the bridge)."""
from .backends import parse_state
from .frame import encode_emotion


class EmotionClient:
    def __init__(self, backend):
        self.backend = backend

    async def inject(self, mood, intensity, ttl_ms, source=0, speaking=False) -> dict:
        """Set an emotion, then read back and return the resulting state."""
        frame = encode_emotion(mood, intensity, ttl_ms, source=source, speaking=speaking)
        await self.backend.send(frame)
        return parse_state(await self.backend.read_state())

    async def clear(self) -> dict:
        """Drop any override and return the device to its autonomous behaviour."""
        await self.backend.clear()
        return parse_state(await self.backend.read_state())

    async def sequence(self, steps, loop=False) -> dict:
        """Play a list of {mood, intensity, ttl_ms} steps in order. Over the
        bridge this runs server-side (returns at once); direct over BLE it
        runs here. Either way a later inject/clear/sequence interrupts it."""
        await self.backend.sequence(steps, loop)
        return parse_state(await self.backend.read_state())

    async def state(self) -> dict:
        return parse_state(await self.backend.read_state())
