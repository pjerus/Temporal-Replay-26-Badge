"""Plasma — sin/cos field that flows through the matrix.

Brightness per cell = composite of two phase-shifted sine waves, with time
as a third dimension. Cheap to compute, mesmerising at this resolution.
"""

import math
import time

from badge import *
from badge_app import GCTicker

W = 8
H = 8
FRAME_MS = 60

# Spatial wavelengths (cells per radian-ish). Smaller numbers = tighter waves.
KX1 = 0.9
KY1 = 0.7
KX2 = 0.5
KY2 = 1.1

# Time speeds for each wave.
T1 = 0.07
T2 = 0.05

# Pre-computed sin lookup keeps the per-pixel work to two indexed adds.
_SIN_RES = 256
_SIN_TABLE = [int(127 + 127 * math.sin(2 * math.pi * i / _SIN_RES))
              for i in range(_SIN_RES)]


def _isin(idx):
    return _SIN_TABLE[idx & (_SIN_RES - 1)]


def run():
    led_override_begin()
    led_clear()
    led_brightness(255)

    t = 0
    gc_ticker = GCTicker()

    try:
        while True:
            if button_pressed(BTN_BACK):
                break

            # Phase offsets at this t (scaled into _SIN_RES indices).
            tphase1 = int(t * T1 * _SIN_RES)
            tphase2 = int(t * T2 * _SIN_RES)

            for y in range(H):
                for x in range(W):
                    a = _isin(int((x * KX1 + y * KY1) * _SIN_RES / 8) + tphase1)
                    b = _isin(int((x * KX2 - y * KY2) * _SIN_RES / 8) + tphase2)
                    # Average of two waves stays in 0..255.
                    led_set_pixel(x, y, (a + b) >> 1)

            t += 1
            gc_ticker.tick()
            time.sleep_ms(FRAME_MS)
    finally:
        led_clear()
        try:
            led_override_end()
        except Exception:
            pass
