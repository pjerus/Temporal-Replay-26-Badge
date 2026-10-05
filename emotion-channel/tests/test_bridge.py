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


def test_delete_clears_the_override():
    class Clearable(FakeBackend):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.on = True

        async def clear(self):
            self.on = False

        async def read_state(self):
            return bytes([0b01, 1, 204, 100, 0, 0, 88]) if self.on else bytes([0, 0, 0, 0, 0, 0, 88])

    r = app(Clearable).request("DELETE", "/emotion", params={"target": "lobby"},
                               headers={"Authorization": "Bearer k3y"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["state"]["override"] is None


def test_delete_requires_api_key():
    r = app().request("DELETE", "/emotion", params={"target": "lobby"})
    assert r.status_code == 401


def test_sequence_plays_steps_in_order():
    import asyncio
    import httpx

    class Recorder(FakeBackend):
        sent = []

        async def send(self, frame):
            from emotion_channel.frame import decode_emotion
            Recorder.sent.append(decode_emotion(frame)["mood"])

    Recorder.sent = []
    application = create_app(REG, api_key="k3y", backend_factory=Recorder)
    steps = [{"mood": "curious", "intensity": 0.5, "ttl_ms": 20},
             {"mood": "happy", "intensity": 0.5, "ttl_ms": 20}]

    async def run():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post("/sequence", headers={"Authorization": "Bearer k3y"},
                             json={"target": "lobby", "steps": steps})
            assert r.status_code == 200 and r.json()["ok"] is True
            await asyncio.sleep(0.15)  # let the background task finish both steps

    asyncio.run(run())
    assert Recorder.sent == ["curious", "happy"]


def test_inject_interrupts_running_sequence():
    import asyncio
    import httpx

    class Rec(FakeBackend):
        sent = []

        async def send(self, frame):
            from emotion_channel.frame import decode_emotion
            Rec.sent.append(decode_emotion(frame)["mood"])

    Rec.sent = []
    application = create_app(REG, api_key="k3y", backend_factory=Rec)
    hdr = {"Authorization": "Bearer k3y"}

    async def run():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            await c.post("/sequence", headers=hdr,
                         json={"target": "lobby", "steps": [{"mood": "tired", "intensity": 0.5, "ttl_ms": 50}], "loop": True})
            await asyncio.sleep(0.06)
            await c.post("/emotion", headers=hdr,
                         json={"target": "lobby", "mood": "angry", "intensity": 1.0, "ttl_ms": 100})
            n = len(Rec.sent)
            await asyncio.sleep(0.2)  # a live loop would add ~4 more "tired"
            assert "angry" in Rec.sent
            assert [m for m in Rec.sent[n:] if m == "tired"] == []  # sequence was cancelled

    asyncio.run(run())


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
