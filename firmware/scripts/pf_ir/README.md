# Power Functions over infrared

Scripts from the 2026-10-06 experiment: a badge drives LEGO Power Functions motors through a
LEGO IR receiver, commanded from the Mac over USB. Throwaway-grade, kept for reference.

Needs a badge flashed with the `echo-ir` build (no emotion BLE service; with it the IR receiver
has no memory to start). Run with PlatformIO's Python, which has pyserial:

    cd firmware/scripts/pf_ir
    ~/.platformio/penv/bin/python badge_exec.py ir_listen.py 100 > capture.txt   # press the LEGO remote at the badge
    ~/.platformio/penv/bin/python pf_decode.py capture.txt
    ~/.platformio/penv/bin/python pf_send.py 5 1500                              # both outputs, 1.5 s
    ~/.platformio/penv/bin/python badge_exec.py ir_selfcheck.py                  # badge hears its own echo

| File | What it does |
|---|---|
| `badge_exec.py` | Runs a Python file on the badge through its USB raw REPL. Waits 1.2 s after connecting: the firmware ignores input for 350 ms. No app may be open on the badge. |
| `ir_listen.py` | Runs on the badge. Records raw IR for 90 s or 60 frames. |
| `pf_decode.py` | Decodes a capture as Power Functions frames. |
| `ir_send_pf.py` | Runs on the badge (template filled in by `pf_send.py`). Sends "combo direct" frames every 90 ms, then coast. |
| `pf_send.py` | Mac-side wrapper for the above. |
| `ir_selfcheck.py` | Sends a coast frame and captures the badge's own reflection. |
| `example_capture.txt` | Pat's remote, channel 1. |

Found: the remote sends mode 1 (combo direct: each output forward, backward or coast) on channel 1,
repeating about every 100 ms; the receiver stops when frames stop. Transmit power must be raised
from the default 10% to 50% to reach a receiver inside a model. Aim the badge's top edge at the dome.
