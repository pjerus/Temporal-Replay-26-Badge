"""The emotion bridge (Option D): one API-key HTTP endpoint in front of
one or more badges reached over BLE. A skill-enabled AI POSTs a mood and
gets back the resulting face state. Runs on the host (laptop) or on an
intermediate box like a Raspberry Pi that owns several badges."""
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
        be = backend_for(body.get("target"))
        frame = encode_emotion(body["mood"], body["intensity"], body["ttl_ms"],
                               source=body.get("source", 0))
        try:
            await be.send(frame)
            raw = await be.read_state()
        except BadgeUnreachable as e:
            return JSONResponse(status_code=502, content={"ok": False, "error": str(e)})
        return _state_response(raw, applied=parse_state(raw)["override"] is not None)

    @app.get("/state")
    async def get_state(target: str, authorization: str = Header(None)):
        check_auth(authorization)
        be = backend_for(target)
        try:
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
