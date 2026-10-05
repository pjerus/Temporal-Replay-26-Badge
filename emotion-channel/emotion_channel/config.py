"""Settings for the emotion channel, read from the environment with
defaults. Nothing project-specific is baked into shared code."""
import os

# Must match firmware/src/emotion/EmotionBleService.cpp.
DEFAULT_UUIDS = {
    "service": "ae3428d5-a3d6-4a2d-a827-6a7c5fd1d4e0",
    "emotion": "5a413f11-6b24-4987-a5a9-93774a4c783f",
    "state": "021ece59-011c-44cb-8f30-2931c0885d11",
}


def badge_secret() -> bytes:
    """8-byte shared secret prefixed to each write. Matches the firmware's
    compile-time dev default; override with EMOTION_BADGE_SECRET once a
    provisioning/pairing flow exists."""
    v = os.environ.get("EMOTION_BADGE_SECRET")
    b = v.encode() if v is not None else b"TEMPORAL"
    if len(b) != 8:
        raise ValueError("EMOTION_BADGE_SECRET must be exactly 8 bytes")
    return b


def api_key() -> str:
    return os.environ.get("EMOTION_API_KEY", "")


# Registered with the local-dev-hosting port registry (see Task 9 note).
DEFAULT_BRIDGE_PORT = 8026


def bridge_port() -> int:
    return int(os.environ.get("EMOTION_BRIDGE_PORT", DEFAULT_BRIDGE_PORT))


def badge_registry() -> dict:
    """{target: {"address", "secret"}} for the bridge. From EMOTION_BADGES
    (JSON {name: {address, secret}}) or, for a single badge, from
    EMOTION_BADGE_ADDRESS + the shared secret."""
    raw = os.environ.get("EMOTION_BADGES")
    if raw:
        import json
        data = json.loads(raw)
        return {
            name: {
                "address": v["address"],
                "secret": v["secret"].encode() if isinstance(v["secret"], str) else bytes(v["secret"]),
            }
            for name, v in data.items()
        }
    addr = os.environ.get("EMOTION_BADGE_ADDRESS")
    if addr:
        return {"badge": {"address": addr, "secret": badge_secret()}}
    return {}
