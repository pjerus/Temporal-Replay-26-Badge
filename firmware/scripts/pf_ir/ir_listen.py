import time, binascii
ir_start()
ir_set_mode("raw")
ir_flush()
print("LISTENING")
t0 = time.ticks_ms()
n = 0
while time.ticks_diff(time.ticks_ms(), t0) < 90000 and n < 60:
    buf = ir_raw_capture()
    if buf:
        n += 1
        print("F", time.ticks_diff(time.ticks_ms(), t0), binascii.hexlify(buf).decode())
    else:
        time.sleep_ms(5)
ir_set_mode("badge")
ir_stop()
print("END", n)
