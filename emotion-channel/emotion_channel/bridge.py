"""The emotion bridge (Option D): one API-key HTTP endpoint in front of
one or more badges reached over BLE. A skill-enabled AI POSTs a mood and
gets back the resulting face state. Runs on the host (laptop) or on an
intermediate box like a Raspberry Pi that owns several badges."""
import asyncio
import base64
import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .backends import BadgeUnreachable, BleBackend, parse_state
from .frame import encode_emotion


def create_app(registry, api_key, backend_factory=BleBackend):
    """registry: {target: {"address": str, "secret": bytes}}. One backend
    is kept per target (so a BLE connection is reused across requests)."""
    if not api_key:
        raise ValueError("api_key must be set (EMOTION_API_KEY); refusing to serve with auth disabled")
    app = FastAPI(title="emotion-bridge")
    backends = {}
    locks = {}
    sequences = {}  # target -> running asyncio.Task

    def lock_for(target):
        # One BleakClient per target can't run overlapping ops; serialize
        # every operation on a target so concurrent callers don't cross.
        if target not in locks:
            locks[target] = asyncio.Lock()
        return locks[target]

    def cancel_sequence(target):
        # Any new command for a target takes over from a running sequence.
        task = sequences.pop(target, None)
        if task is not None:
            task.cancel()

    def check_auth(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization[len("Bearer "):]
        if not token or not secrets.compare_digest(token, api_key):
            raise HTTPException(status_code=401, detail="bad api key")

    def backend_for(target):
        if target not in registry:
            raise HTTPException(status_code=404, detail=f"unknown target {target!r}")
        if target not in backends:
            entry = registry[target]
            backends[target] = backend_factory(entry["address"], entry["secret"])
        return backends[target]

    def _state_response(raw, *, applied=None):
        state = parse_state(raw)
        body = {"ok": True, "state": state, "state_raw": base64.b64encode(raw).decode()}
        if applied is not None:
            body["applied"] = applied
        return body

    @app.post("/emotion")
    async def post_emotion(body: dict, authorization: str = Header(None)):
        check_auth(authorization)
        target = body.get("target")
        be = backend_for(target)
        cancel_sequence(target)  # a direct inject takes over from a sequence
        frame = encode_emotion(body["mood"], body["intensity"], body["ttl_ms"],
                               source=body.get("source", 0))
        try:
            async with lock_for(target):
                await be.send(frame)
                raw = await be.read_state()
        except BadgeUnreachable as e:
            return JSONResponse(status_code=502, content={"ok": False, "error": str(e)})
        return _state_response(raw, applied=parse_state(raw)["override"] is not None)

    @app.delete("/emotion")
    async def delete_emotion(target: str, authorization: str = Header(None)):
        check_auth(authorization)
        be = backend_for(target)
        cancel_sequence(target)
        try:
            async with lock_for(target):
                await be.clear()
                raw = await be.read_state()
        except BadgeUnreachable as e:
            return JSONResponse(status_code=502, content={"ok": False, "error": str(e)})
        return _state_response(raw)

    @app.post("/sequence")
    async def post_sequence(body: dict, authorization: str = Header(None)):
        check_auth(authorization)
        target = body.get("target")
        be = backend_for(target)
        steps = list(body.get("steps") or [])
        loop = bool(body.get("loop", False))
        cancel_sequence(target)

        async def play():
            try:
                while True:
                    for s in steps:
                        frame = encode_emotion(s["mood"], s["intensity"], s["ttl_ms"],
                                               source=s.get("source", 0))
                        async with lock_for(target):
                            await be.send(frame)
                        await asyncio.sleep(s["ttl_ms"] / 1000)
                    if not loop:
                        return
            except BadgeUnreachable:
                return  # badge dropped mid-sequence; stop quietly

        if steps:
            sequences[target] = asyncio.create_task(play())
        return {"ok": True, "accepted": len(steps), "loop": loop}

    @app.get("/state")
    async def get_state(target: str, authorization: str = Header(None)):
        check_auth(authorization)
        be = backend_for(target)
        try:
            async with lock_for(target):
                raw = await be.read_state()
        except BadgeUnreachable as e:
            return JSONResponse(status_code=502, content={"ok": False, "error": str(e)})
        return _state_response(raw)

    return app


def main():
    import uvicorn
    from . import config
    uvicorn.run(create_app(config.badge_registry(), config.api_key()),
                host="127.0.0.1", port=config.bridge_port())


if __name__ == "__main__":
    main()
