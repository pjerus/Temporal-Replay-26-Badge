# Runs on the badge. Sends Syma S107G helicopter frames: STEPS is a list of
# (yaw, pitch, throttle, ms); yaw and pitch 0..127 with 63 centred, throttle 0..127.
# Frame: 2000/2000 us header, 32 bits MSB first (yaw, pitch, channel bit + throttle, trim),
# each bit a 300 us mark then a 300 us (0) or 700 us (1) space, then a closing mark.
import time, struct
STEPS = __STEPS__
CHANNEL_B = __CHANNEL_B__      # the remote's A/B switch
TRIM = 63
PERIOD_MS = 180 if CHANNEL_B else 120
def frame(yaw, pitch, throttle):
    word = (yaw << 24) | (pitch << 16) | (((0x80 if CHANNEL_B else 0) | throttle) << 8) | TRIM
    pairs = [(2000, 2000)] + [(300, 700 if (word >> i) & 1 else 300) for i in range(31, -1, -1)] + [(300, 1000)]
    return b''.join(struct.pack('<HH', m, s) for m, s in pairs)
ir_start(); ir_set_mode("raw"); ir_tx_power(50)
for yaw, pitch, throttle, ms in STEPS:
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        ir_raw_send(frame(yaw, pitch, throttle), 38000); time.sleep_ms(PERIOD_MS)
    print("did", yaw, pitch, throttle, ms)
for _ in range(4):
    ir_raw_send(frame(63, 63, 0), 38000); time.sleep_ms(PERIOD_MS)
ir_set_mode("badge"); ir_stop()
print("DONE")
