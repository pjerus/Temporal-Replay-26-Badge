# Send LEGO Power Functions "combo direct" frames, as captured from Pat's remote (channel 1).
# DATA is BBAA: per output 00 float, 01 one way, 10 the other way, 11 brake.
import time, struct
DATA = __DATA__
RUN_MS = __RUN_MS__
def frame(data, channel=0):
    n1 = 0x8 | channel            # toggle=1, escape=0, channel bits (as the remote sends)
    n2 = 0x1                      # address 0, mode 001 = combo direct (stops by itself when frames stop)
    n3 = data & 0xF
    n4 = 0xF ^ n1 ^ n2 ^ n3
    bits = (n1 << 12) | (n2 << 8) | (n3 << 4) | n4
    pairs = [(158, 1026)]
    for i in range(15, -1, -1):
        pairs.append((158, 553) if (bits >> i) & 1 else (158, 263))
    pairs.append((158, 1026))
    b = b''
    for m, s in pairs:
        b += struct.pack('<HH', m, s)
    return b
ir_start()
ir_set_mode("raw")
ir_tx_power(50)   # the default 10% did not reach a receiver inside a model
go, stop = frame(DATA), frame(0)
t0 = time.ticks_ms(); n = 0
while time.ticks_diff(time.ticks_ms(), t0) < RUN_MS:
    ir_raw_send(go, 38000); n += 1
    time.sleep_ms(90)
for _ in range(5):
    ir_raw_send(stop, 38000)
    time.sleep_ms(90)
ir_set_mode("badge")
ir_stop()
print("SENT", n, "frames, data", DATA)
