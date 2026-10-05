import pytest
from emotion_channel.frame import encode_emotion, decode_emotion, MOODS


def test_roundtrip_happy():
    buf = encode_emotion("happy", 0.8, 20000, source=1)
    assert len(buf) == 6
    d = decode_emotion(buf)
    assert d["mood"] == "happy"
    assert abs(d["intensity"] - 0.8) < 0.01
    assert d["ttl_ms"] == 20000
    assert d["source"] == 1
    assert d["speaking"] is False


def test_mood_order_is_fixed():
    assert MOODS == ["neutral", "happy", "tired", "sad", "angry", "surprised", "curious", "scared"]


def test_ttl_zero_is_latch():
    assert decode_emotion(encode_emotion("angry", 1.0, 0))["ttl_ms"] == 0


def test_ttl_caps_at_uint16_deciseconds():
    # 2 bytes of deciseconds -> max 65535 ds = 6553500 ms
    assert decode_emotion(encode_emotion("sad", 0.5, 9_999_999))["ttl_ms"] == 6553500


def test_bad_mood_rejected():
    with pytest.raises(ValueError):
        encode_emotion("ecstatic", 0.5, 1000)


def test_short_buffer_rejected():
    with pytest.raises(ValueError):
        decode_emotion(b"\x01\x02")
