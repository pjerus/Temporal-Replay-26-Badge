"""Emotion wire frame — the cross-language contract.

Keep byte-for-byte identical to firmware/src/emotion/EmotionFrame.h.
Layout (6 bytes, little-endian):
    byte 0   mood index (0..7)
    byte 1   intensity (0..255 -> 0.0..1.0)
    byte 2-3 ttl in deciseconds (uint16; 0 = latch until replaced/cleared)
    byte 4   source id
    byte 5   flags (bit0 = speaking)
"""
import struct

MOODS = ["neutral", "happy", "tired", "sad", "angry", "surprised", "curious", "scared"]
_SPEAKING_BIT = 0x01


def _mood_index(mood):
    if isinstance(mood, int):
        if not 0 <= mood < len(MOODS):
            raise ValueError(f"mood index out of range: {mood}")
        return mood
    try:
        return MOODS.index(mood)
    except ValueError:
        raise ValueError(f"unknown mood: {mood!r}")


def encode_emotion(mood, intensity, ttl_ms, source=0, speaking=False):
    mi = _mood_index(mood)
    inten = max(0, min(255, round(float(intensity) * 255)))
    ttl_ds = max(0, min(0xFFFF, round(int(ttl_ms) / 100)))
    flags = _SPEAKING_BIT if speaking else 0
    return struct.pack("<BBHBB", mi, inten, ttl_ds, source & 0xFF, flags)


def decode_emotion(buf):
    if len(buf) != 6:
        raise ValueError(f"emotion frame must be 6 bytes, got {len(buf)}")
    mi, inten, ttl_ds, source, flags = struct.unpack("<BBHBB", buf)
    if mi >= len(MOODS):
        raise ValueError(f"mood index out of range: {mi}")
    return {
        "mood": MOODS[mi],
        "intensity": inten / 255,
        "ttl_ms": ttl_ds * 100,
        "source": source,
        "speaking": bool(flags & _SPEAKING_BIT),
    }
