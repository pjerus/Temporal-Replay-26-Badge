"""BLE Scan screen — live list of nearby BLE devices.

Uses the badge's C-side BLE scanner (Arduino-ESP32 BLE library, NimBLE).
Devices are stored in a fixed-size table on the C side keyed by MAC.

Controls:
  Joystick / UP / DOWN  scroll the list
  BACK                  return to launcher
  CONFIRM               (reserved for future "mark known")
"""

import time

from badge_app import read_stick_4way, GCTicker

ROW_H = 9
HEADER_H = 12
FOOTER_H = 10
LIST_TOP = HEADER_H + 2
LIST_BOTTOM = 64 - FOOTER_H
ROWS_VISIBLE = (LIST_BOTTOM - LIST_TOP) // ROW_H

STALE_MS = 8000
LOOP_MS = 80
SCROLL_COOLDOWN_MS = 140
REDRAW_INTERVAL_MS = 250


def _addr_tail(addr_bytes):
    if len(addr_bytes) < 2:
        return "??"
    return "{:02X}:{:02X}".format(addr_bytes[-2], addr_bytes[-1])


def _snapshot():
    """Return list of (addr_bytes, addr_type, rssi, age_ms, name) sorted by RSSI desc."""
    n = ble_scan_count()
    out = []
    for i in range(n):
        e = ble_scan_get(i)
        if e is None:
            continue
        out.append(e)
    out.sort(key=lambda t: t[2], reverse=True)
    return out


def _draw(snap, selected, scroll, status):
    n = len(snap)

    oled_clear()
    ui_header("BLE", "n=" + str(n))

    if n == 0:
        oled_set_cursor(0, LIST_TOP + ROW_H)
        oled_print("scanning...")
    else:
        end = min(scroll + ROWS_VISIBLE, n)
        for row, idx in enumerate(range(scroll, end)):
            addr_bytes, _, rssi, _, name = snap[idx]
            label = name if name else _addr_tail(addr_bytes)
            line = "{:>4} {}".format(rssi, label)
            y = LIST_TOP + row * ROW_H
            prefix = ">" if idx == selected else " "
            oled_set_cursor(0, y)
            oled_print(prefix + line[:20])

    oled_set_cursor(0, 55)
    oled_print(status)
    oled_show()


def run():
    rc = ble_scan_start()
    if rc != 0:
        oled_clear()
        ui_header("BLE", "Error")
        oled_set_cursor(0, 18)
        oled_print("ble_scan_start rc=" + str(rc))
        oled_set_cursor(0, 30)
        oled_print("Likely BT init OOM.")
        oled_set_cursor(0, 54)
        oled_print("Any button to exit")
        oled_show()
        time.sleep_ms(400)
        while not (button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM)
                   or button_pressed(BTN_UP) or button_pressed(BTN_DOWN)):
            time.sleep_ms(50)
        return

    selected = 0
    scroll = 0
    last_scroll = 0
    last_redraw = 0
    gc_ticker = GCTicker()
    snap = _snapshot()

    try:
        _draw(snap, selected, scroll, "scan: on")
        while True:
            now = time.ticks_ms()

            if button_pressed(BTN_BACK):
                break

            if time.ticks_diff(now, last_scroll) >= SCROLL_COOLDOWN_MS:
                _, dy = read_stick_4way()
                if button_pressed(BTN_UP):
                    dy = -1
                elif button_pressed(BTN_DOWN):
                    dy = 1
                if dy != 0 and len(snap) > 0:
                    selected = max(0, min(len(snap) - 1, selected + dy))
                    if selected < scroll:
                        scroll = selected
                    elif selected >= scroll + ROWS_VISIBLE:
                        scroll = selected - ROWS_VISIBLE + 1
                    last_scroll = now
                    last_redraw = 0

            if time.ticks_diff(now, last_redraw) >= REDRAW_INTERVAL_MS:
                ble_scan_prune(STALE_MS)
                snap = _snapshot()
                n = len(snap)
                if selected >= n:
                    selected = max(0, n - 1)
                if scroll > selected:
                    scroll = selected
                _draw(snap, selected, scroll, "scan: on")
                last_redraw = now

            gc_ticker.tick()
            time.sleep_ms(LOOP_MS)
    finally:
        ble_scan_stop()
        oled_clear(True)
