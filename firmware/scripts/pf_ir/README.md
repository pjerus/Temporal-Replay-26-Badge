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

## Driving the tank base

    ~/.platformio/penv/bin/python pf_drive.py 5 5 1500           # both treads forward, speed 5, 1.5 s
    ~/.platformio/penv/bin/python pf_drive.py 5 -5 1000 0 0 300 -3 -3 800   # spin right, pause, back up

`pf_drive.py` (Mac side) fills in `ir_drive.py` (badge side). Speeds are -7..7 per tread, positive
forward. It uses the "combo PWM" mode: seven speed steps per output, and the receiver still stops
when frames stop.

Measured 2026-10-06 on Pat's base, treads off the ground: output A is the left tread, B the right;
the right side is flipped in `ir_drive.py` because the two motors face opposite ways; speed 3 is
the slowest that turns both treads (at 2 the left one stalls). Not yet tested on the floor.

Floor results, 2026-10-06 (carpet, no load on the platform, speed 4): about one foot in 1.5 s; the left tread runs
slower, corrected by `LEFT_TRIM = 1.09` in `ir_drive.py` (straight forward and in reverse);
a spin at 4 / -4 turns about 180 degrees per second, so 500 ms is a quarter turn. Fractional
speeds alternate between the two nearest steps frame by frame.

## Driving over Bluetooth (no cable)

Needs the badge on the `echo-drive` firmware. Set `ROCKY_TREAD_SECRET` to the badge's 8-character
shared secret first (it is the emotion channel's secret; do not put it in a file here).

    uv run --with bleak pf_ble_drive.py --status          # connect, print status and memory
    uv run --with bleak pf_ble_drive.py 4 4 1500          # forward, speed 4, 1.5 s

The script resends the command five times a second; each is valid for 0.6 s. If the script dies or
Bluetooth drops, the badge sends a stop and goes quiet, and the LEGO receiver stops by itself too.
Trim, right-side flip, channel and IR power are `tr_*` lines in the badge's `settings.txt`.
Status prints free internal memory now and the lowest since power-on; the badge refuses to drive
below 6 KB.

Hardware results, 2026-10-06. Free internal memory with a controller connected: 12.5 KB on USB
(lowest since power-on 7.25 KB), about 19 KB on battery. Driven cable-free on carpet: forward,
back, both quarter turns. Stops confirmed: script killed mid-move (stopped within a second) and
IR beam blocked (stops, resumes when uncovered). Bluetooth switched off mid-move was not tested.
The ten-minute soak has not been run. The battery percent in the status reads 0 on battery.

Two builds carry the drive service: `echo-drive` (spare badge, announces as "Rocky IR Tread",
shows a status line) and `echo-face-drive` (the face badge: face stays on screen, Bluetooth name
unchanged). To drive the face badge set `ROCKY_TREAD_NAME=TemporalBadge`.

`badge.dev("info")` over the USB REPL reads name|title|company; `badge.dev("info", "name", "")`
sets one field. Both badges were blanked this way.

## Drive app on the badge

Both drive builds have a DRIVE entry on the main menu: joystick steers (gentle push slow, full
push full speed), up/down buttons held = full speed forward/reverse, left/right buttons = a
timed quarter turn, up and down together = stop and exit. It feeds the same stop logic as the
Bluetooth drive, and Bluetooth drive commands are dropped while it is open. The heading shows
the badge's name (set with `badge.dev("info", "name", "...")`): the spare is "Rocky IR Tread",
the face badge "Rocky Face". Checked by Pat on the face badge 2026-10-06.

## Syma S107G helicopter

The same raw IR sender flies a Syma S107G indoor helicopter (38 kHz; 2000/2000 us header, 32 bits
of yaw, pitch, channel + throttle, trim; a frame every 120 ms on channel A). The frame is 34
pulses, so TX-only builds allow 40 per raw send. From the Mac over USB:
`s107.py <yaw> <pitch> <throttle> <ms>` (yaw and pitch 0..127 with 63 centred, throttle 0..127).
On the badge: the HELI menu entry on the drive builds. Up/down buttons step the throttle,
left/right trim, joystick turns and tilts, up and down together cuts the rotors and exits.
Settings `hl_chan`, `hl_trim`, `hl_step`. Rotors start near 30% throttle. Proven 2026-10-06 on
Rocky Face: rotors spin from the script and from the app. Stick and trim directions and real
flight are untested, and the screen still shows a sent/failed frame counter from that proving.
