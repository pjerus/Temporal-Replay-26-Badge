import asyncio

import pytest

from emotion_channel.backends import parse_state, BadgeUnreachable
from emotion_channel.client import EmotionClient
from emotion_channel.frame import decode_emotion


def test_parse_state_override_active():
    # flags=0b11 (active+face), mood=5, inten=230, msLeft/100=50, autoMood=0, batt=76
    buf = bytes([0b11, 5, 230, 50, 0, 0, 76])
    s = parse_state(buf)
    assert s["override"]["mood"] == "surprised"
    assert s["override"]["ms_left"] == 5000
    assert s["face_on_screen"] is True
    assert s["battery_pct"] == 76


def test_parse_state_idle():
    # flags=0, autoMood byte (index 5) = 2 -> "tired"
    buf = bytes([0, 0, 0, 0, 0, 2, 50])
    s = parse_state(buf)
    assert s["override"] is None
    assert s["autonomous"] == "tired"


class FakeBackend:
    def __init__(self):
        self.sent = None

    async def send(self, frame):
        self.sent = frame

    async def read_state(self):
        return bytes([0b01, 1, 204, 100, 0, 0, 90])


def test_client_inject_roundtrips_frame():
    be = FakeBackend()
    c = EmotionClient(be)
    state = asyncio.run(c.inject("happy", 0.8, 20000))
    assert decode_emotion(be.sent)["mood"] == "happy"   # backend received a valid frame
    assert state["override"]["mood"] == "happy"


def test_client_clear_calls_backend_and_reads_state():
    class FakeClear:
        def __init__(self):
            self.cleared = False

        async def clear(self):
            self.cleared = True

        async def read_state(self):
            return bytes([0, 0, 0, 0, 0, 0, 90])  # no override

    be = FakeClear()
    state = asyncio.run(EmotionClient(be).clear())
    assert be.cleared is True
    assert state["override"] is None
