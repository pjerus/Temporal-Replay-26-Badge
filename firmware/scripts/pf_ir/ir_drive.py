# Runs on the badge. Drives a two-tread platform through a LEGO Power Functions IR receiver
# using "combo PWM" frames (7 speed steps per output; the receiver stops when frames stop).
# STEPS is a list of (left, right, ms) with speeds -7..7; positive is tread forward.
import time, struct
STEPS = __STEPS__
CHANNEL = 0          # remote channel 1
# Mapping found 2026-10-06 on Pat's tank base: output A = left tread, B = right tread,
# In this speed mode LEGO "backward" runs the left tread forward but the right tread backward
# (measured), so the right side is flipped below.
def pwm(speed):
    if speed == 0: return 0                    # coast
    return (16 - speed) if speed > 0 else -speed
def frame(left, right):
    n1 = 0x4 | CHANNEL                         # escape=1 selects combo PWM
    n2 = pwm(-right)                           # output B, flipped
    n3 = pwm(left)                             # output A
    n4 = 0xF ^ n1 ^ n2 ^ n3
    bits = (n1 << 12) | (n2 << 8) | (n3 << 4) | n4
    pairs = [(158, 1026)] + [((158, 553) if (bits >> i) & 1 else (158, 263)) for i in range(15, -1, -1)] + [(158, 1026)]
    return b''.join(struct.pack('<HH', m, s) for m, s in pairs)
ir_start(); ir_set_mode("raw"); ir_tx_power(50)
for left, right, ms in STEPS:
    f = frame(left, right); t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        ir_raw_send(f, 38000); time.sleep_ms(90)
    print("did", left, right, ms)
for _ in range(4):
    ir_raw_send(frame(0, 0), 38000); time.sleep_ms(90)
ir_set_mode("badge"); ir_stop()
print("DONE")
