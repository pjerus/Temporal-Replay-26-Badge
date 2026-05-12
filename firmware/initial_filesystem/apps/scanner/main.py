"""/apps/scanner/main.py — launcher menu.

Phase 2: pick a sub-screen (BLE Scan or Demo). BACK from a sub-screen
returns here; BACK from the menu exits the app.
"""

__title__ = "Scanner"
__description__ = "Multi-band scanner (Phase 2)"
__order__ = 0

import time

from badge_app import read_stick_4way

ENTRIES = (
    ("BLE Scan", "ble"),
    ("Demo",     "demo"),
)

MOVE_COOLDOWN_MS = 180


def _draw(selected):
    oled_clear()
    ui_header("Scanner", "")
    for i, (label, _) in enumerate(ENTRIES):
        y = 16 + i * 12
        prefix = "> " if i == selected else "  "
        oled_set_cursor(0, y)
        oled_print(prefix + label)
    oled_set_cursor(0, 54)
    oled_print("CONFIRM=open BACK=exit")
    oled_show()


def _launch(name):
    if name == "ble":
        import ble
        ble.run()
    elif name == "demo":
        import demo
        demo.run()


def _show_error(label, err):
    oled_clear()
    ui_header("Scanner", "Error")
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

    oled_clear(True)


main()
exit()
