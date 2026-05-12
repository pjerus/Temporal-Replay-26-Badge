"""Rave Billboard — name tag display with multiple animated effects.

Reads the display name from /apps/billboard/name.txt (first non-empty line,
stripped). Falls back to "BADGE" if the file is missing or empty.

Effects on entry → mode picker. CONFIRM cycles to next effect mid-run;
BACK exits to the apps menu.
"""

__title__ = "Billboard"
__description__ = "Rave name tag display"
__order__ = 2

import math
import random
import time

from badge import *
from badge_app import GCTicker, read_stick_4way, ticks_add

NAME_PATH = "/apps/billboard/name.txt"
DEFAULT_NAME = "BADGE"

OLED_W = 128
OLED_H = 64

# Default font on this badge is 6x8 px per char at text_size=1.
CHAR_W = 6
CHAR_H = 8


# ── name loading ─────────────────────────────────────────────────────────────

def load_name():
    try:
        with open(NAME_PATH, "r") as f:
            for raw in f:
                line = raw.strip()
                if line:
                    return line
    except Exception:
        pass
    return DEFAULT_NAME


def fit_text_size(text):
    """Pick the largest text_size 1..4 that still fits horizontally."""
    n = len(text) if text else 1
    for size in (4, 3, 2, 1):
        if n * CHAR_W * size <= OLED_W:
            return size
    return 1


def centered_xy(text, size):
    w = len(text) * CHAR_W * size
    h = CHAR_H * size
    x = max(0, (OLED_W - w) // 2)
    y = max(0, (OLED_H - h) // 2)
    return x, y


def big_centered(text):
    """Render text as large as it'll fit, centered."""
    size = fit_text_size(text)
    x, y = centered_xy(text, size)
    try:
        oled_set_text_size(size)
    except Exception:
        pass
    oled_set_cursor(x, y)
    oled_print(text)
    try:
        oled_set_text_size(1)
    except Exception:
        pass


# ── matrix helpers ───────────────────────────────────────────────────────────

def matrix_fill(b):
    for y in range(8):
        for x in range(8):
            led_set_pixel(x, y, b)


def matrix_clear():
    led_clear()


def matrix_column_sweep(col, lo=20, hi=255):
    """Light one column hi, others lo."""
    for x in range(8):
        b = hi if x == col else lo
        for y in range(8):
            led_set_pixel(x, y, b)


def matrix_border(phase, dim=15, bright=255):
    """Light the perimeter cells, with one cell at `phase` glowing brightest.
    phase is an integer that walks the border (28 cells around an 8x8)."""
    perim = []
    for x in range(8):
        perim.append((x, 0))
    for y in range(1, 8):
        perim.append((7, y))
    for x in range(6, -1, -1):
        perim.append((x, 7))
    for y in range(6, 0, -1):
        perim.append((0, y))
    head = phase % len(perim)
    matrix_clear()
    for i, (x, y) in enumerate(perim):
        if i == head:
            led_set_pixel(x, y, bright)
        elif i == (head - 1) % len(perim) or i == (head + 1) % len(perim):
            led_set_pixel(x, y, bright // 2)
        else:
            led_set_pixel(x, y, dim)


# ── effects ──────────────────────────────────────────────────────────────────

def effect_scroll(name, deadline_ticks):
    """Name slides right→left across the OLED. Matrix sweeps in sync."""
    size = 3 if len(name) <= 6 else 2
    text_w = len(name) * CHAR_W * size
    text_h = CHAR_H * size
    y = (OLED_H - text_h) // 2
    x = OLED_W
    SPEED = 2  # px per frame
    last_col = -1
    while True:
        if button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM):
            return
        if deadline_ticks is not None and time.ticks_diff(deadline_ticks, time.ticks_ms()) <= 0:
            return
        oled_clear()
        try:
            oled_set_text_size(size)
        except Exception:
            pass
        oled_set_cursor(x, y)
        oled_print(name)
        try:
            oled_set_text_size(1)
        except Exception:
            pass
        oled_show()

        # Matrix column sweep tracks scroll progress.
        col = 7 - (((-x) // 4) % 8)
        if col != last_col:
            matrix_column_sweep(col)
            last_col = col

        x -= SPEED
        if x < -text_w:
            x = OLED_W
        time.sleep_ms(40)


def effect_strobe(name, deadline_ticks):
    """Hard inversion every other frame, both displays."""
    inv = False
    last_redraw = 0
    last_invert = 0
    while True:
        now = time.ticks_ms()
        if button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM):
            try:
                oled_invert(False)
            except Exception:
                pass
            return
        if deadline_ticks is not None and time.ticks_diff(deadline_ticks, now) <= 0:
            try:
                oled_invert(False)
            except Exception:
                pass
            return

        if time.ticks_diff(now, last_redraw) > 200:
            oled_clear()
            big_centered(name)
            oled_show()
            last_redraw = now

        if time.ticks_diff(now, last_invert) > 80:
            inv = not inv
            try:
                oled_invert(inv)
            except Exception:
                pass
            matrix_fill(255 if inv else 0)
            last_invert = now

        time.sleep_ms(20)


def effect_pulse(name, deadline_ticks):
    """Slow breathing brightness on matrix; OLED static + occasional invert."""
    oled_clear()
    big_centered(name)
    oled_show()

    t = 0
    last_invert_state = False
    while True:
        now = time.ticks_ms()
        if button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM):
            try:
                oled_invert(False)
            except Exception:
                pass
            return
        if deadline_ticks is not None and time.ticks_diff(deadline_ticks, now) <= 0:
            try:
                oled_invert(False)
            except Exception:
                pass
            return

        # Sine pulse 0..255.
        b = int(128 + 127 * math.sin(t * 0.18))
        matrix_fill(b)

        # OLED inverts at peaks.
        invert_now = b > 240
        if invert_now != last_invert_state:
            try:
                oled_invert(invert_now)
            except Exception:
                pass
            last_invert_state = invert_now

        t += 1
        time.sleep_ms(50)


def effect_marquee(name, deadline_ticks):
    """Static centered name + chase-light border on matrix."""
    oled_clear()
    big_centered(name)
    oled_show()

    phase = 0
    while True:
        if button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM):
            return
        if deadline_ticks is not None and time.ticks_diff(deadline_ticks, time.ticks_ms()) <= 0:
            return
        matrix_border(phase)
        phase += 1
        time.sleep_ms(80)


def effect_sparkle(name, deadline_ticks):
    """Static name + random sparkle dots on the matrix."""
    oled_clear()
    big_centered(name)
    oled_show()

    buf = [0] * 64
    DECAY = 30
    while True:
        if button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM):
            return
        if deadline_ticks is not None and time.ticks_diff(deadline_ticks, time.ticks_ms()) <= 0:
            return
        # Decay all cells.
        for i in range(64):
            v = buf[i] - DECAY
            buf[i] = v if v > 0 else 0
        # Spark a few new cells.
        for _ in range(3):
            i = random.randint(0, 63)
            buf[i] = 255
        for y in range(8):
            for x in range(8):
                led_set_pixel(x, y, buf[y * 8 + x])
        time.sleep_ms(60)


# ── mode selection ───────────────────────────────────────────────────────────

EFFECTS = (
    ("Scroll",   effect_scroll),
    ("Strobe",   effect_strobe),
    ("Pulse",    effect_pulse),
    ("Marquee",  effect_marquee),
    ("Sparkle",  effect_sparkle),
    ("Cycle",    None),  # special: rotates through all effects
)
CYCLE_INDEX = len(EFFECTS) - 1
CYCLE_INTERVAL_MS = 5000


def pick_effect():
    selected = 0
    last_move = 0
    settle_start = time.ticks_ms()

    def _draw():
        oled_clear()
        led_clear()
        oled_set_cursor(0, 0)
        oled_print("Pick effect:")
        for i, (label, _) in enumerate(EFFECTS):
            y = 12 + i * 9
            prefix = "> " if i == selected else "  "
            oled_set_cursor(0, y)
            oled_print(prefix + label)
        oled_set_cursor(0, 56)
        oled_print("OK=run BACK=exit")
        oled_show()

    _draw()
    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, settle_start) < 250:
            time.sleep_ms(20)
            continue
        if button_pressed(BTN_BACK):
            return None
        if button_pressed(BTN_CONFIRM):
            return selected
        if time.ticks_diff(now, last_move) >= 180:
            _, dy = read_stick_4way()
            if button_pressed(BTN_UP):
                dy = -1
            elif button_pressed(BTN_DOWN):
                dy = 1
            if dy != 0:
                selected = (selected + dy) % len(EFFECTS)
                last_move = now
                _draw()
        time.sleep_ms(40)


def run_effect(name, idx):
    """Run a single effect indefinitely (until BACK or CONFIRM)."""
    label, fn = EFFECTS[idx]
    fn(name, None)


def run_cycle(name):
    """Auto-rotate through every effect every CYCLE_INTERVAL_MS."""
    i = 0
    while True:
        label, fn = EFFECTS[i]
        if fn is None:
            i = (i + 1) % len(EFFECTS)
            continue
        deadline = ticks_add(time.ticks_ms(), CYCLE_INTERVAL_MS)
        fn(name, deadline)
        # If user pressed BACK, the effect returns; check globally.
        if button_pressed(BTN_BACK):
            return
        i = (i + 1) % len(EFFECTS)


def main():
    led_override_begin()
    name = load_name()

    try:
        while True:
            idx = pick_effect()
            if idx is None:
                break
            try:
                if idx == CYCLE_INDEX:
                    run_cycle(name)
                else:
                    # CONFIRM during single-mode advances to next effect; loop here
                    # so you can mash CONFIRM to walk the list without going back to
                    # the picker every time.
                    while True:
                        EFFECTS[idx][1](name, None)
                        # Returning from an effect means BACK or CONFIRM was pressed.
                        # If BACK: bail to picker. If CONFIRM: advance.
                        if button_pressed(BTN_BACK):
                            break
                        idx = (idx + 1) % len(EFFECTS)
                        if idx == CYCLE_INDEX:
                            idx = 0
                        # Brief debounce so the CONFIRM that advanced doesn't
                        # also instantly trigger inside the next effect.
                        time.sleep_ms(180)
            finally:
                try:
                    oled_invert(False)
                except Exception:
                    pass
                led_clear()
    finally:
        led_clear()
        try:
            led_override_end()
        except Exception:
            pass
        oled_clear(True)


main()
exit()
