"""Rave Billboard — name tag display with multiple animated effects.

Reads the display name from /apps/billboard/name.txt (first non-empty line,
stripped). Falls back to "BADGE" if the file is missing or empty.

Effects on entry → mode picker. CONFIRM cycles to next effect mid-run;
BACK exits the effect (back to picker, then back to apps menu).
"""

__title__ = "Billboard"
__description__ = "Rave name tag display"
__order__ = 2

import math
import random
import time

from badge import *
from badge_app import read_stick_4way, ticks_add

NAME_PATH = "/apps/billboard/name.txt"
DEFAULT_NAME = "BADGE"

OLED_W = 128
OLED_H = 64

# Fonts available on the badge, ordered largest → smallest. Each entry:
# (name, approximate cell width, approximate cell height). Width is used
# only as a fallback estimate; we always re-measure with oled_text_width()
# when picking a font for a given string.
BIG_FONTS = (
    ("Spleen 32x64", 32, 64),   # 1-2 chars max
    ("Spleen 16x32", 16, 32),   # ~6-7 chars
    ("Spleen 12x24", 12, 24),   # ~10 chars
    ("Spleen 8x16",   8, 16),   # ~14 chars
    ("10x20",        10, 20),
    ("Spleen 6x12",   6, 12),
    ("6x10",          6, 10),
)
FALLBACK_FONT = "6x10"


# Sentinel return codes from effects.
EXIT_BACK = "back"
EXIT_NEXT = "next"
EXIT_TIMEOUT = "timeout"


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


def measure(s, font_name):
    try:
        oled_set_font(font_name)
        return oled_text_width(s)
    except Exception:
        return len(s) * 6  # rough fallback


def pick_biggest_font(name):
    """Largest BIG_FONTS entry that fits the OLED width."""
    for font_name, _w, _h in BIG_FONTS:
        try:
            oled_set_font(font_name)
            if oled_text_width(name) <= OLED_W:
                return font_name
        except Exception:
            continue
    return FALLBACK_FONT


def big_centered(name, font_name=None):
    """Render `name` in the largest font that fits, centered on the OLED."""
    font_name = font_name or pick_biggest_font(name)
    try:
        oled_set_font(font_name)
        w = oled_text_width(name)
        h = oled_text_height(name)
    except Exception:
        w = len(name) * 6
        h = 8
    x = max(0, (OLED_W - w) // 2)
    y = max(0, (OLED_H - h) // 2)
    oled_set_cursor(x, y)
    oled_print(name)


# ── input helpers ────────────────────────────────────────────────────────────

def check_exit():
    """Single check that returns EXIT_BACK / EXIT_NEXT / None.
    Caller decides what to do."""
    if button_pressed(BTN_BACK):
        return EXIT_BACK
    if button_pressed(BTN_CONFIRM):
        return EXIT_NEXT
    return None


def check_or_timeout(deadline_ms):
    rc = check_exit()
    if rc:
        return rc
    if deadline_ms is not None and time.ticks_diff(deadline_ms, time.ticks_ms()) <= 0:
        return EXIT_TIMEOUT
    return None


# ── matrix helpers ───────────────────────────────────────────────────────────

def matrix_fill(b):
    for y in range(8):
        for x in range(8):
            led_set_pixel(x, y, b)


def matrix_clear():
    led_clear()


def matrix_column_sweep(col, lo=20, hi=255):
    for x in range(8):
        b = hi if x == col else lo
        for y in range(8):
            led_set_pixel(x, y, b)


def matrix_border(phase, dim=15, bright=255):
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

def effect_scroll(name, deadline_ms):
    """Name slides right→left across the OLED in the biggest font that fits
    vertically (Spleen 16x32 is usually right). Matrix sweeps in sync."""
    # For scroll, prefer Spleen 16x32 — taller, dramatic, fits any name length
    # since we scroll past the right edge anyway.
    font_name = "Spleen 16x32"
    try:
        oled_set_font(font_name)
        text_w = oled_text_width(name)
        text_h = oled_text_height(name)
    except Exception:
        text_w = len(name) * 16
        text_h = 32
    y = max(0, (OLED_H - text_h) // 2)

    x = OLED_W
    SPEED = 3
    last_col = -1
    while True:
        rc = check_or_timeout(deadline_ms)
        if rc:
            return rc
        oled_clear()
        try:
            oled_set_font(font_name)
        except Exception:
            pass
        oled_set_cursor(x, y)
        oled_print(name)
        oled_show()

        col = 7 - (((-x) // 4) % 8)
        if col != last_col:
            matrix_column_sweep(col)
            last_col = col

        x -= SPEED
        if x < -text_w:
            x = OLED_W
        time.sleep_ms(40)


def effect_strobe(name, deadline_ms):
    """Hard inversion every other frame, both displays."""
    inv = False
    last_redraw = 0
    last_invert = 0
    font_name = pick_biggest_font(name)
    while True:
        now = time.ticks_ms()
        rc = check_or_timeout(deadline_ms)
        if rc:
            try:
                oled_invert(False)
            except Exception:
                pass
            return rc

        if time.ticks_diff(now, last_redraw) > 200:
            oled_clear()
            big_centered(name, font_name)
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


def effect_pulse(name, deadline_ms):
    """Static OLED with the name; matrix breathes; OLED inverts at peaks."""
    oled_clear()
    big_centered(name)
    oled_show()

    t = 0
    last_invert_state = False
    while True:
        rc = check_or_timeout(deadline_ms)
        if rc:
            try:
                oled_invert(False)
            except Exception:
                pass
            return rc

        b = int(128 + 127 * math.sin(t * 0.18))
        matrix_fill(b)

        invert_now = b > 240
        if invert_now != last_invert_state:
            try:
                oled_invert(invert_now)
            except Exception:
                pass
            last_invert_state = invert_now

        t += 1
        time.sleep_ms(50)


def effect_marquee(name, deadline_ms):
    """Static centered name + chase-light border on matrix."""
    oled_clear()
    big_centered(name)
    oled_show()

    phase = 0
    while True:
        rc = check_or_timeout(deadline_ms)
        if rc:
            return rc
        matrix_border(phase)
        phase += 1
        time.sleep_ms(80)


def effect_sparkle(name, deadline_ms):
    """Static name + random sparkle dots on the matrix."""
    oled_clear()
    big_centered(name)
    oled_show()

    buf = [0] * 64
    DECAY = 30
    while True:
        rc = check_or_timeout(deadline_ms)
        if rc:
            return rc
        for i in range(64):
            v = buf[i] - DECAY
            buf[i] = v if v > 0 else 0
        for _ in range(3):
            buf[random.randint(0, 63)] = 255
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
)
CYCLE_LABEL = "Cycle"
CYCLE_INTERVAL_MS = 5000


def pick_effect():
    """Show picker. Returns effect index or 'cycle' or None (BACK)."""
    entries = [label for label, _ in EFFECTS] + [CYCLE_LABEL]
    selected = 0
    last_move = 0
    settle_start = time.ticks_ms()

    def _draw():
        oled_clear()
        try:
            oled_set_font(FALLBACK_FONT)
        except Exception:
            pass
        led_clear()
        oled_set_cursor(0, 0)
        oled_print("Pick effect:")
        for i, label in enumerate(entries):
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
            return "cycle" if selected == len(EFFECTS) else selected
        if time.ticks_diff(now, last_move) >= 180:
            _, dy = read_stick_4way()
            if button_pressed(BTN_UP):
                dy = -1
            elif button_pressed(BTN_DOWN):
                dy = 1
            if dy != 0:
                selected = (selected + dy) % len(entries)
                last_move = now
                _draw()
        time.sleep_ms(40)


def run_single(name, idx):
    """Run a single effect. CONFIRM advances to next effect; BACK returns to picker."""
    while True:
        rc = EFFECTS[idx][1](name, None)
        if rc == EXIT_BACK:
            return
        # EXIT_NEXT: advance to next effect, brief debounce so the same
        # CONFIRM doesn't immediately re-trigger inside the new effect.
        idx = (idx + 1) % len(EFFECTS)
        time.sleep_ms(220)


def run_cycle(name):
    """Auto-rotate every CYCLE_INTERVAL_MS until BACK or CONFIRM."""
    i = 0
    while True:
        deadline = ticks_add(time.ticks_ms(), CYCLE_INTERVAL_MS)
        rc = EFFECTS[i][1](name, deadline)
        if rc == EXIT_BACK or rc == EXIT_NEXT:
            return
        # rc == EXIT_TIMEOUT: advance.
        i = (i + 1) % len(EFFECTS)


def main():
    led_override_begin()
    name = load_name()

    try:
        while True:
            choice = pick_effect()
            if choice is None:
                break
            try:
                if choice == "cycle":
                    run_cycle(name)
                else:
                    run_single(name, choice)
            finally:
                try:
                    oled_invert(False)
                except Exception:
                    pass
                led_clear()
            # After returning from run_*, the caller already consumed BACK.
            # Loop back to picker.
    finally:
        led_clear()
        try:
            led_override_end()
        except Exception:
            pass
        try:
            oled_set_font(FALLBACK_FONT)
        except Exception:
            pass
        oled_clear(True)


main()
exit()
