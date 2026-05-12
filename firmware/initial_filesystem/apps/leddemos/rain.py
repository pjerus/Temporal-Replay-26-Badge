"""Matrix Rain — falling brightness streaks per column.

Each column has its own drop position and speed. The drop's head is
brightest; cells trail behind it with falling brightness.
"""

import random
import time

from badge import *
from badge_app import GCTicker, ticks_add

W = 8
H = 8
FRAME_MS = 90

HEAD_BRIGHTNESS = 255
TRAIL_DECAY = 60   # subtracted per row of trail distance
DECAY_PER_FRAME = 30   # subtracted from every pixel each frame

# Cadence per column: lower number = faster drop. Each column picks a
# random multiplier in this band so the rain isn't synchronized.
SPEED_MIN_MS = 80
SPEED_MAX_MS = 220


def _seed():
    try:
        random.seed(time.ticks_ms())
    except Exception:
        pass


def _new_column():
    return {
        "y": random.randint(-H, 0),                # head row; negative = above the matrix
        "speed": random.randint(SPEED_MIN_MS, SPEED_MAX_MS),
        "next_step": 0,
    }


def run():
    _seed()
    led_override_begin()
    led_clear()
    led_brightness(255)

    columns = [_new_column() for _ in range(W)]
    buf = [0] * (W * H)
    gc_ticker = GCTicker()
    now = time.ticks_ms()
    for c in columns:
        c["next_step"] = ticks_add(now, random.randint(0, c["speed"]))

    try:
        while True:
            if button_pressed(BTN_BACK):
                break
            now = time.ticks_ms()

            # Decay every cell so old trails fade.
            for i in range(W * H):
                v = buf[i] - DECAY_PER_FRAME
                buf[i] = v if v > 0 else 0

            # Advance each column when its per-column timer fires.
            for x, col in enumerate(columns):
                if time.ticks_diff(now, col["next_step"]) >= 0:
                    col["y"] += 1
                    col["next_step"] = ticks_add(now, col["speed"])
                    if col["y"] >= H + H:
                        # Recycle once the head + trail have left the matrix.
                        columns[x] = _new_column()
                        columns[x]["next_step"] = ticks_add(
                            now, columns[x]["speed"])

                # Stamp the head + a trail above it.
                head_y = col["y"]
                for trail in range(H):
                    y = head_y - trail
                    if 0 <= y < H:
                        v = HEAD_BRIGHTNESS - trail * TRAIL_DECAY
                        if v > buf[y * W + x]:
                            buf[y * W + x] = v

            for y in range(H):
                for x in range(W):
                    led_set_pixel(x, y, buf[y * W + x])

            gc_ticker.tick()
            time.sleep_ms(FRAME_MS)
    finally:
        led_clear()
        try:
            led_override_end()
        except Exception:
            pass
