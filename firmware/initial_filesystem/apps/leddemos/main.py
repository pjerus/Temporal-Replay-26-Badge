"""LED Demos — small launcher for ambient 8x8 matrix effects.

Each effect runs full-screen on the LED matrix until BACK.
"""

__title__ = "LED Demos"
__description__ = "Fire / Plasma / Matrix rain"
__order__ = 1

import sys
import time

APP_DIR = "/apps/leddemos"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from badge import *
from badge_app import read_stick_4way

ENTRIES = (
    ("Fire",        "fire"),
    ("Plasma",      "plasma"),
    ("Matrix Rain", "rain"),
)

MOVE_COOLDOWN_MS = 180


def _draw(selected):
    oled_clear()
    led_clear()
    ui_header("LED Demos", "")
    for i, (label, _) in enumerate(ENTRIES):
        y = 16 + i * 11
        prefix = "> " if i == selected else "  "
        oled_set_cursor(0, y)
        oled_print(prefix + label)
    oled_set_cursor(0, 54)
    oled_print("OK=run  BACK=exit")
    oled_show()


def _launch(name):
    if name == "fire":
        import fire
        fire.run()
    elif name == "plasma":
        import plasma
        plasma.run()
    elif name == "rain":
        import rain
        rain.run()


def _show_error(label, err):
    oled_clear()
    ui_header("LED Demos", "Error")
    oled_set_cursor(0, 18)
    oled_print(label + " failed:")
    msg = str(err)
    oled_set_cursor(0, 30)
    oled_print(msg[:21])
    if len(msg) > 21:
        oled_set_cursor(0, 42)
        oled_print(msg[21:42])
    oled_set_cursor(0, 54)
    oled_print("Any button to dismiss")
    oled_show()
    time.sleep_ms(400)
    while not (button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM)
               or button_pressed(BTN_UP) or button_pressed(BTN_DOWN)):
        time.sleep_ms(50)


def main():
    selected = 0
    last_move = 0
    _draw(selected)

    while True:
        now = time.ticks_ms()

        if button_pressed(BTN_BACK):
            break

        if button_pressed(BTN_CONFIRM):
            haptic_pulse(60, 20)
            try:
                _launch(ENTRIES[selected][1])
            except Exception as e:
                _show_error(ENTRIES[selected][0], e)
            _draw(selected)
            continue

        if time.ticks_diff(now, last_move) >= MOVE_COOLDOWN_MS:
            _, dy = read_stick_4way()
            if button_pressed(BTN_UP):
                dy = -1
            elif button_pressed(BTN_DOWN):
                dy = 1
            if dy != 0:
                selected = (selected + dy) % len(ENTRIES)
                last_move = now
                _draw(selected)

        time.sleep_ms(40)

    led_clear()
    oled_clear(True)


main()
exit()
