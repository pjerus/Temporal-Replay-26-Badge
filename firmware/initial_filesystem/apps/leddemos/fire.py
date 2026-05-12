"""Fire — bottom-row sparks rising and fading via cellular automaton.

Each cell's brightness is the average of the three cells below it minus a
random decay. The bottom row is randomized fresh each frame to keep the
fire alive.
"""

import random
import time

from badge import *
from badge_app import GCTicker

W = 8
H = 8
FRAME_MS = 70

# Per-frame decay subtracted from each cell after averaging.
DECAY_MIN = 18
DECAY_MAX = 38

# Bottom row "fuel" — random brightness in this band each frame.
FUEL_LOW = 180
FUEL_HIGH = 255

# Hide the dimmest tail so cells fully extinguish (avoids permanent low glow).
EXTINGUISH_BELOW = 8


def _seed():
    try:
        random.seed(time.ticks_ms())
    except Exception:
        pass


def _new_buf():
    return [0] * (W * H)


def run():
    _seed()
    led_override_begin()
    led_clear()
    led_brightness(180)

    cur = _new_buf()
    nxt = _new_buf()
    gc_ticker = GCTicker()

    try:
        while True:
            if button_pressed(BTN_BACK):
                break

            # Refuel bottom row.
            for x in range(W):
                cur[(H - 1) * W + x] = random.randint(FUEL_LOW, FUEL_HIGH)

            # Propagate upward: each cell becomes the avg of three cells
            # below it (left/center/right), minus a decay.
            for y in range(H - 1):
                src_y = y + 1
                for x in range(W):
                    a = cur[src_y * W + x]
                    b = cur[src_y * W + (x - 1 if x > 0 else x)]
                    c = cur[src_y * W + (x + 1 if x < W - 1 else x)]
                    avg = (a + b + c) // 3
                    decay = random.randint(DECAY_MIN, DECAY_MAX)
                    val = avg - decay
                    if val < EXTINGUISH_BELOW:
                        val = 0
                    nxt[y * W + x] = val
            # Bottom row stays as cur (just refueled).
            for x in range(W):
                nxt[(H - 1) * W + x] = cur[(H - 1) * W + x]

            # Render.
            for y in range(H):
                for x in range(W):
                    led_set_pixel(x, y, nxt[y * W + x])

            cur, nxt = nxt, cur
            gc_ticker.tick()
            time.sleep_ms(FRAME_MS)
    finally:
        led_clear()
        try:
            led_override_end()
        except Exception:
            pass
