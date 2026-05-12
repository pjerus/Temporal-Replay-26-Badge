"""BLE Scan screen — live list of nearby BLE devices.

Uses MicroPython's vendored `bluetooth` module (NimBLE on ESP32-S3) in
central scanning mode. Devices are keyed by (addr_type, addr); the most
recent advertisement wins. Devices not seen for STALE_MS are forgotten.

Controls:
  Joystick / UP / DOWN  scroll the list
  BACK                  return to launcher
  CONFIRM               (reserved for future "mark known")
"""

import time

import bluetooth

from badge_app import read_stick_4way, GCTicker

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

_AD_TYPE_NAME_SHORT = 0x08
_AD_TYPE_NAME_COMPLETE = 0x09

SCAN_INTERVAL_US = 30000
SCAN_WINDOW_US = 30000

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


def _parse_name(adv_bytes):
    i = 0
    n = len(adv_bytes)
    while i + 1 < n:
        length = adv_bytes[i]
        if length == 0:
            break
        if i + length >= n:
            break
        ad_type = adv_bytes[i + 1]
        if ad_type in (_AD_TYPE_NAME_SHORT, _AD_TYPE_NAME_COMPLETE):
            try:
                return bytes(adv_bytes[i + 2 : i + 1 + length]).decode("utf-8")
            except Exception:
                return None
        i += 1 + length
    return None


def _addr_tail(addr_bytes):
    if len(addr_bytes) < 2:
        return "??"
    return "{:02X}:{:02X}".format(addr_bytes[-2], addr_bytes[-1])


class _Devices:
    """Keyed by (addr_type, bytes(addr)). Value: [name, rssi, last_seen_ms]."""

    def __init__(self):
        self._d = {}

    def update(self, addr_type, addr_bytes, rssi, name):
        key = (addr_type, addr_bytes)
        existing = self._d.get(key)
        now = time.ticks_ms()
        if existing is None:
            self._d[key] = [name, rssi, now]
        else:
            if name and (not existing[0] or len(name) > len(existing[0])):
                existing[0] = name
            existing[1] = rssi
            existing[2] = now

    def prune(self):
        now = time.ticks_ms()
        dead = [k for k, v in self._d.items() if time.ticks_diff(now, v[2]) > STALE_MS]
        for k in dead:
            del self._d[k]

    def sorted_view(self):
        items = [(k, v[0], v[1]) for k, v in self._d.items()]
        items.sort(key=lambda t: t[2], reverse=True)
        return items

    def __len__(self):
        return len(self._d)


def _draw(devices, selected, scroll, status):
    items = devices.sorted_view()
    n = len(items)

    oled_clear()
    ui_header("BLE", "n=" + str(n))

    if n == 0:
        oled_set_cursor(0, LIST_TOP + ROW_H)
        oled_print("scanning...")
    else:
        end = min(scroll + ROWS_VISIBLE, n)
        for row, idx in enumerate(range(scroll, end)):
            key, name, rssi = items[idx]
            _, addr_bytes = key
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
    ble = bluetooth.BLE()
    ble.active(True)

    devices = _Devices()

    def _irq(event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_bytes = bytes(addr)
            adv_bytes = bytes(adv_data)
            name = _parse_name(adv_bytes)
            devices.update(addr_type, addr_bytes, rssi, name)

    ble.irq(_irq)
    ble.gap_scan(0, SCAN_INTERVAL_US, SCAN_WINDOW_US, True)

    selected = 0
    scroll = 0
    last_scroll = 0
    last_redraw = 0
    gc_ticker = GCTicker()

    try:
        _draw(devices, selected, scroll, "scan: on")
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
                if dy != 0:
                    n = len(devices)
                    if n > 0:
                        selected = max(0, min(n - 1, selected + dy))
                        if selected < scroll:
                            scroll = selected
                        elif selected >= scroll + ROWS_VISIBLE:
                            scroll = selected - ROWS_VISIBLE + 1
                        last_scroll = now
                        last_redraw = 0

            if time.ticks_diff(now, last_redraw) >= REDRAW_INTERVAL_MS:
                devices.prune()
                n = len(devices)
                if selected >= n:
                    selected = max(0, n - 1)
                if scroll > selected:
                    scroll = selected
                _draw(devices, selected, scroll, "scan: on")
                last_redraw = now

            gc_ticker.tick()
            time.sleep_ms(LOOP_MS)
    finally:
        try:
            ble.gap_scan(None)
        except Exception:
            pass
        try:
            ble.active(False)
        except Exception:
            pass
        oled_clear(True)
