import time, struct, binascii
def frame(data):
    n1, n2, n3 = 0x8, 0x1, data & 0xF
    n4 = 0xF ^ n1 ^ n2 ^ n3
    bits = (n1 << 12) | (n2 << 8) | (n3 << 4) | n4
    pairs = [(158, 1026)] + [((158, 553) if (bits >> i) & 1 else (158, 263)) for i in range(15, -1, -1)] + [(158, 1026)]
    return b''.join(struct.pack('<HH', m, s) for m, s in pairs)
ir_start()
print("tx power", ir_tx_power())
ir_set_mode("raw")
ir_flush()
rc = ir_raw_send(frame(0), 38000)
print("send rc", rc)
time.sleep_ms(200)
got = 0
for _ in range(20):
    b = ir_raw_capture()
    if b:
        got += 1
        print("ECHO", binascii.hexlify(b).decode())
    time.sleep_ms(10)
print("echoes", got, "activity", ir_activity())
ir_set_mode("badge")
ir_stop()
