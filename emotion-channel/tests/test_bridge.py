import pytest
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


def test_empty_api_key_refused():
    # Fail closed: an unset EMOTION_API_KEY must not start an open endpoint.
    with pytest.raises(ValueError):
        create_app(REG, api_key="")


def test_empty_token_rejected():
    r = app().post("/emotion", headers={"Authorization": "Bearer "},
                   json={"target": "lobby", "mood": "happy", "intensity": 0.8, "ttl_ms": 20000})
    assert r.status_code == 401


def test_badge_unreachable_is_502():
    class Dead(FakeBackend):
        async def send(self, frame):
            raise BadgeUnreachable("out of range")
    r = app(Dead).post("/emotion", headers={"Authorization": "Bearer k3y"},
                       json={"target": "lobby", "mood": "happy", "intensity": 0.8, "ttl_ms": 20000})
    assert r.status_code == 502 and r.json()["ok"] is False


def test_same_target_requests_serialize():
    # A bleak client can't run overlapping ops; same-target requests must
    # serialize around the send+read pair, or two readers cross.
    import asyncio
    import httpx

    class Serial:
        depth = 0
        violated = False

        def __init__(self, address, secret, **kw):
            pass

        async def send(self, frame):
            Serial.depth += 1
            if Serial.depth > 1:
                Serial.violated = True
            await asyncio.sleep(0.02)

        async def read_state(self):
            await asyncio.sleep(0.02)
            Serial.depth -= 1
            if Serial.depth != 0:
                Serial.violated = True
            return bytes([0b01, 1, 204, 100, 0, 0, 88])

    Serial.depth, Serial.violated = 0, False
    application = create_app(REG, api_key="k3y", backend_factory=Serial)
    body = {"target": "lobby", "mood": "happy", "intensity": 0.5, "ttl_ms": 5000}
    hdr = {"Authorization": "Bearer k3y"}

    async def run():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await asyncio.gather(
                c.post("/emotion", headers=hdr, json=body),
                c.post("/emotion", headers=hdr, json=body),
            )

    r1, r2 = asyncio.run(run())
    assert r1.status_code == 200 and r2.status_code == 200
    assert Serial.violated is False
