from fastapi.testclient import TestClient
from emotion_channel.bridge import create_app
from emotion_channel.backends import BadgeUnreachable


class FakeBackend:
    def __init__(self, address, secret, **kw):
        self.last = None

    async def send(self, frame):
        self.last = frame

    async def read_state(self):
        return bytes([0b01, 1, 204, 100, 0, 0, 88])


REG = {"lobby": {"address": "AA:BB", "secret": b"12345678"}}


def app(factory=FakeBackend):
    return TestClient(create_app(REG, api_key="k3y", backend_factory=factory))


def test_requires_api_key():
    r = app().post("/emotion", json={"target": "lobby", "mood": "happy", "intensity": 0.8, "ttl_ms": 20000})
    assert r.status_code == 401


def test_happy_path():
    r = app().post("/emotion", headers={"Authorization": "Bearer k3y"},
                   json={"target": "lobby", "mood": "happy", "intensity": 0.8, "ttl_ms": 20000})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["state"]["override"]["mood"] == "happy"


def test_unknown_target():
    r = app().post("/emotion", headers={"Authorization": "Bearer k3y"},
                   json={"target": "nope", "mood": "happy", "intensity": 0.8, "ttl_ms": 20000})
    assert r.status_code == 404


def test_badge_unreachable_is_502():
    class Dead(FakeBackend):
        async def send(self, frame):
            raise BadgeUnreachable("out of range")
    r = app(Dead).post("/emotion", headers={"Authorization": "Bearer k3y"},
                       json={"target": "lobby", "mood": "happy", "intensity": 0.8, "ttl_ms": 20000})
    assert r.status_code == 502 and r.json()["ok"] is False
