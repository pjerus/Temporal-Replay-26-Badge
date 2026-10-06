import pytest
from pf_ble_drive import build_cmd, parse_state

S = b"ABCDEFGH"

def test_build_cmd_layout():
    assert build_cmd(S, 4, 4, 10) == S + bytes([40, 40, 10])
    assert build_cmd(S, -4.3, 0, 2) == S + bytes([256 - 43, 0, 2])

@pytest.mark.parametrize("args", [(7.1, 0, 5), (0, -7.1, 5), (1, 1, 0), (1, 1, 11)])
def test_build_cmd_rejects_out_of_range(args):
    with pytest.raises(ValueError):
        build_cmd(S, *args)

def test_build_cmd_needs_8_byte_secret():
    with pytest.raises(ValueError):
        build_cmd(b"short", 1, 1, 5)

def test_parse_state():
    st = parse_state(bytes([0x03, 256 - 25, 33, 6, 87, 36, 32, 1]))
    assert st == {"driving": True, "ir_ready": True, "low_memory": False, "rejected": False,
                  "left": -2.5, "right": 3.3, "left_s": 0.6, "battery": 87,
                  "free_kb": 9.0, "min_free_kb": 8.0, "accepted": 1}

def test_parse_state_wrong_length():
    with pytest.raises(ValueError):
        parse_state(b"\x00" * 7)