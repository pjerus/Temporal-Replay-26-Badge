# Pocket Scanner Phase 2 — BLE Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live BLE-device scanner screen to the pocket scanner app — name + MAC + RSSI for nearby devices, joystick scrolls — with the existing Phase 1 hardware demo preserved as a second selectable screen behind a small launcher menu.

**Architecture:** Refactor `apps/scanner/main.py` into a tiny launcher menu that picks between sub-screens. Move the Phase 1 demo body into `apps/scanner/demo.py`. Add `apps/scanner/ble.py` that drives MicroPython's vendored `bluetooth` module (NimBLE on ESP32-S3) in central scanning mode and renders a scrollable device list on the OLED. All changes stay MicroPython-side; no C firmware edits.

**Tech Stack:** MicroPython on ESP32-S3, `bluetooth` extmod (NimBLE), `badge` / `badge_ui` / `badge_app` helper modules already on the badge filesystem.

---

## File Structure

```
~/temporal-badge-scanner/
├── docs/superpowers/plans/
│   └── 2026-05-11-pocket-scanner-phase2-ble-scan.md   # this file
└── upstream/                                          # inner git repo, branch pocket-scanner-phase2
    └── firmware/initial_filesystem/apps/scanner/
        ├── __init__.py                                # unchanged (empty)
        ├── main.py                                    # MODIFY: launcher menu (was Phase 1 demo)
        ├── demo.py                                    # NEW: Phase 1 demo body, callable from launcher
        └── ble.py                                     # NEW: BLE scan screen
```

**Boundary discipline:**
- Outer repo (`temporal-badge-scanner/`) gets only this plan file.
- Inner repo (`upstream/`) gets all firmware-side changes on a new branch `pocket-scanner-phase2` cut from `pocket-scanner-phase1`.
- Do not touch `firmware/initial_filesystem/manifest.json` — it's regenerated pre-build and currently shows as modified in the working tree (expected, see Phase 1 checkpoint).

---

## Open question resolved up-front

**Is `bluetooth` actually importable on the device?** The vendored `mpconfigport.h` defines `MICROPY_PY_BLUETOOTH=1` and `MICROPY_PY_BLUETOOTH_ENABLE_CENTRAL_MODE=1`, and `firmware/lib/micropython_embed/src/extmod/modbluetooth.c` plus the esp32 NimBLE port are present in the build tree. Upstream's user-facing `MicroPythonDeveloperGuide.md` "Available Modules" table doesn't list it (the doc is incomplete), but the C wiring is there. We verify on hardware in Task 4. If `import bluetooth` fails at runtime, the BLE screen catches the `ImportError` and shows a friendly error — we do **not** silently swallow it; we surface it on the OLED so we know to investigate the native build.

---

## Task 1: Cut Phase 2 branch in the inner repo

**Files:** none (git only)

- [ ] **Step 1: Confirm we're sitting on Phase 1 head with a clean tree**

```bash
cd ~/temporal-badge-scanner/upstream
git status
git log --oneline -5
```

Expected: `On branch pocket-scanner-phase1`. Working tree may show `firmware/initial_filesystem/manifest.json` as modified — that's the known regenerator drift; ignore it. Last commit should be `00a76a5 feat: strip game menu entries`.

- [ ] **Step 2: Create the Phase 2 branch from Phase 1 head**

```bash
git switch -c pocket-scanner-phase2
git log --oneline -1
```

Expected: still at `00a76a5 …` but now on branch `pocket-scanner-phase2`.

- [ ] **Step 3: Commit this plan in the OUTER repo**

```bash
cd ~/temporal-badge-scanner
git add docs/superpowers/plans/2026-05-11-pocket-scanner-phase2-ble-scan.md
git commit -m "plan: phase 2 BLE scan"
git log --oneline -3
```

Expected: a new outer-repo commit with this plan file.

---

## Task 2: Move Phase 1 demo body into `apps/scanner/demo.py`

**Files:**
- Create: `upstream/firmware/initial_filesystem/apps/scanner/demo.py`
- Modify: `upstream/firmware/initial_filesystem/apps/scanner/main.py` (gut for now — full launcher comes in Task 3)

The current `main.py` is the Phase 1 demo with module-level code that runs on import. We need that demo loop wrapped in a `run()` function so the launcher can call it. We extract first, then in Task 3 we replace `main.py` with the launcher.

- [ ] **Step 1: Create `demo.py` with the Phase 1 demo wrapped in `run()`**

Write `~/temporal-badge-scanner/upstream/firmware/initial_filesystem/apps/scanner/demo.py`:

```python
"""Phase 1 hardware demo, packaged as a callable screen.

Same behavior as the original /apps/scanner/main.py through Phase 1:
joystick + buttons move a cursor on the 8x8 LED matrix, CONFIRM cycles
brightness, IMU face-down dims output, BACK exits cleanly.
"""

import time

from badge_app import read_stick_4way, GCTicker

BRIGHTNESS_LEVELS = (80, 160, 40)
BRIGHTNESS_LABELS = ("med", "hi", "lo")
LOOP_MS = 80
JOY_COOLDOWN_MS = 120


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _render_oled(cx, cy, brt_label, jx, jy, tilt_x, tilt_y, face_down, imu_ok):
    oled_clear()
    ui_header("Scanner", "Demo")
    oled_set_cursor(0, 14)
    oled_print("Cur:" + str(cx) + "," + str(cy) + "  Brt:" + brt_label)
    oled_set_cursor(0, 26)
    oled_print("Joy:" + str(jx) + "/" + str(jy))
    if imu_ok:
        oled_set_cursor(0, 38)
        oled_print("Tilt " + str(int(tilt_x)) + "/" + str(int(tilt_y)))
        oled_set_cursor(0, 50)
        oled_print("Face:" + ("down" if face_down else "up  "))
    else:
        oled_set_cursor(0, 38)
        oled_print("IMU: not ready")
    oled_show()


def _render_matrix(cx, cy, brightness):
    led_clear()
    led_set_pixel(cx, cy, brightness)


def run():
    cursor_x = 3
    cursor_y = 3
    bright_index = 0
    last_joy_move = 0
    imu_ok = imu_ready()

    led_override_begin()
    led_clear()
    led_brightness(80)

    gc_ticker = GCTicker()

    try:
        while True:
            now = time.ticks_ms()

            if button_pressed(BTN_BACK):
                break

            if button_pressed(BTN_CONFIRM):
                bright_index = (bright_index + 1) % len(BRIGHTNESS_LEVELS)
                haptic_pulse(80, 20)

            brightness = BRIGHTNESS_LEVELS[bright_index]
            brt_label = BRIGHTNESS_LABELS[bright_index]

            face_down = imu_face_down() if imu_ok else False
            active_brightness = brightness // 4 if face_down else brightness

            if time.ticks_diff(now, last_joy_move) >= JOY_COOLDOWN_MS:
                jx_dir, jy_dir = read_stick_4way()
                if jx_dir != 0 or jy_dir != 0:
                    cursor_x = _clamp(cursor_x + jx_dir, 0, 7)
                    cursor_y = _clamp(cursor_y + jy_dir, 0, 7)
                    last_joy_move = now

            if button_pressed(BTN_UP):
                cursor_y = _clamp(cursor_y - 1, 0, 7)
            if button_pressed(BTN_DOWN):
                cursor_y = _clamp(cursor_y + 1, 0, 7)
            if button_pressed(BTN_LEFT):
                cursor_x = _clamp(cursor_x - 1, 0, 7)
            if button_pressed(BTN_RIGHT):
                cursor_x = _clamp(cursor_x + 1, 0, 7)

            jx = joy_x()
            jy = joy_y()
            tilt_x = imu_tilt_x() if imu_ok else 0
            tilt_y = imu_tilt_y() if imu_ok else 0

            _render_matrix(cursor_x, cursor_y, active_brightness)
            _render_oled(cursor_x, cursor_y, brt_label, jx, jy, tilt_x, tilt_y, face_down, imu_ok)

            gc_ticker.tick()
            time.sleep_ms(LOOP_MS)
    finally:
        led_clear()
        try:
            matrix_app_stop()
        except Exception:
            pass
        try:
            led_override_end()
        except Exception:
            pass
        oled_clear(True)
```

Notes on the wrapping:
- All module-level state from the old `main.py` becomes `run()`-local.
- The `try/finally` ensures the matrix/OLED are released even if an unexpected exception leaks (defensive at a system boundary — the launcher needs to keep working).
- `matrix_app_stop()` and `led_override_end()` are wrapped in `try/except` because they may raise if matrix override was never engaged (shouldn't happen here, but cheap insurance at the boundary).

- [ ] **Step 2: Don't yet rewrite `main.py`** — Task 3 replaces it with the launcher in one shot. Leaving the old `main.py` in place means the badge still launches the demo if someone flashes after Task 2 alone (a defensive checkpoint).

- [ ] **Step 3: Commit**

```bash
cd ~/temporal-badge-scanner/upstream
git add firmware/initial_filesystem/apps/scanner/demo.py
git commit -m "feat(scanner): extract phase-1 demo into demo.py with run() entry"
git log --oneline -3
```

---

## Task 3: Replace `main.py` with the launcher menu

**Files:**
- Modify (rewrite): `upstream/firmware/initial_filesystem/apps/scanner/main.py`

The launcher is a tiny picker with two entries: "BLE Scan" and "Demo". Joystick / UP+DOWN buttons move selection, CONFIRM enters the screen, BACK exits the app entirely.

- [ ] **Step 1: Rewrite `main.py`**

Write `~/temporal-badge-scanner/upstream/firmware/initial_filesystem/apps/scanner/main.py`:

```python
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
    # Lazy import so a parse error in one screen doesn't break the others.
    if name == "ble":
        import ble
        ble.run()
    elif name == "demo":
        import demo
        demo.run()


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
                # Surface load/runtime errors instead of bouncing to a blank menu.
                oled_clear()
                ui_header("Scanner", "Error")
                oled_set_cursor(0, 18)
                oled_print(ENTRIES[selected][0] + " failed:")
                msg = str(e)
                oled_set_cursor(0, 30)
                oled_print(msg[:21])
                if len(msg) > 21:
                    oled_set_cursor(0, 42)
                    oled_print(msg[21:42])
                oled_set_cursor(0, 54)
                oled_print("Any button to dismiss")
                oled_show()
                # Block until any button release/press cycle.
                time.sleep_ms(400)
                while not (button_pressed(BTN_BACK) or button_pressed(BTN_CONFIRM)
                           or button_pressed(BTN_UP) or button_pressed(BTN_DOWN)):
                    time.sleep_ms(50)
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
```

Why this shape:
- Lazy imports of `ble` / `demo` keep startup fast and isolate parse errors per-screen.
- The error-display branch is the one place we *do* catch a broad exception, because it's a system boundary — the launcher must stay usable if a sub-screen blows up. We surface the message on the OLED rather than swallowing it.
- The launcher has zero matrix/IMU state so cleanup on BACK is just `oled_clear(True)`.

- [ ] **Step 2: Commit**

```bash
cd ~/temporal-badge-scanner/upstream
git add firmware/initial_filesystem/apps/scanner/main.py
git commit -m "feat(scanner): launcher menu picks BLE Scan or Demo"
git log --oneline -3
```

---

## Task 4: Build, flash, and verify the launcher (without ble.py yet)

This is the architecture-validation checkpoint before we write the BLE screen. If the launcher boots and Demo runs, the menu shape works. The "BLE Scan" entry will fail to load (no `ble.py` yet) and the launcher should display the error gracefully — that proves the error-surface branch we wrote in Task 3.

- [ ] **Step 1: Build**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
~/.platformio/penv/bin/pio run -e echo-dev 2>&1 | tail -10
```

Expected: SUCCESS.

- [ ] **Step 2: Flash firmware + filesystem**

```bash
~/.platformio/penv/bin/pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
~/.platformio/penv/bin/pio run -e echo-dev -t uploadfs --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
```

`uploadfs` is required because we changed `initial_filesystem/`. If port is busy: `lsof /dev/cu.usbmodem2101` and close the holder (Chrome tab, stray `cat`, file manager).

- [ ] **Step 3: Verify on the badge**

1. Boot, navigate to Apps → Scanner.
2. Menu shows "BLE Scan" and "Demo" with `>` indicating selection.
3. Joystick down moves selection to "Demo"; up moves it back.
4. CONFIRM on "Demo" opens the Phase 1 demo. Joystick moves cursor on matrix; CONFIRM cycles brightness; BACK returns to launcher.
5. CONFIRM on "BLE Scan" shows an error screen ("BLE Scan failed: …") — likely `ImportError: no module named 'ble'`. Press any button; it returns to the launcher.
6. BACK from the launcher exits cleanly.

If any step fails, fix it before proceeding to Task 5.

- [ ] **Step 4: No commit needed** — this task only verifies the prior commits work end-to-end.

---

## Task 5: Implement `apps/scanner/ble.py` — BLE scan screen

**Files:**
- Create: `upstream/firmware/initial_filesystem/apps/scanner/ble.py`

The screen runs continuous active BLE scanning, keeps a dict keyed by `(addr_type, addr)` of the most recent observation, sorts by RSSI desc, and shows a scrollable list on the OLED. Joystick or UP/DOWN scrolls the list one row at a time. CONFIRM is reserved for "tag as known" in a follow-up; in this task it's a no-op (we don't add persistence yet — strict YAGNI for the MVP). BACK exits the screen.

- [ ] **Step 1: Write `ble.py`**

Write `~/temporal-badge-scanner/upstream/firmware/initial_filesystem/apps/scanner/ble.py`:

```python
"""BLE Scan screen — live list of nearby BLE devices.

Uses MicroPython's vendored `bluetooth` module (NimBLE on ESP32-S3) in
central scanning mode. Devices are keyed by (addr_type, addr); the most
recent advertisement wins. Devices not seen for STALE_MS are forgotten.

Controls:
  Joystick / UP / DOWN  scroll the list
  BACK                  return to launcher
  CONFIRM               (reserved for future "mark known")
"""

import binascii
import time

import bluetooth

from badge_app import read_stick_4way, GCTicker

# IRQ event constants (from MicroPython docs; not exposed on bluetooth module).
_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

# Adv data types we care about for name parsing.
_AD_TYPE_NAME_SHORT = 0x08
_AD_TYPE_NAME_COMPLETE = 0x09

# Scan parameters: continuous (duration_ms=0), 30 ms interval/window, active scan.
SCAN_INTERVAL_US = 30000
SCAN_WINDOW_US = 30000

# UI parameters tuned for the SSD1309 128x64 + Smallsimple font (~9 px row).
ROW_H = 9
HEADER_H = 12
FOOTER_H = 10
LIST_TOP = HEADER_H + 2          # 14
LIST_BOTTOM = 64 - FOOTER_H      # 54
ROWS_VISIBLE = (LIST_BOTTOM - LIST_TOP) // ROW_H  # 4

STALE_MS = 8000
LOOP_MS = 80
SCROLL_COOLDOWN_MS = 140
REDRAW_INTERVAL_MS = 250


def _parse_name(adv_bytes):
    """Return the device's local name from raw adv data, or None."""
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
                # Some devices put non-UTF-8 bytes here. Skip the name rather than crash.
                return None
        i += 1 + length
    return None


def _addr_tail(addr_bytes):
    """Last 2 bytes of MAC as 'AA:BB' for compact display."""
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
            # Keep the better name (prefer longer / non-None).
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
        """Return list of (key, name, rssi) sorted by rssi desc."""
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
            addr_type, addr_bytes = key
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
            # `addr` and `adv_data` are memoryviews into a shared buffer; copy.
            addr_bytes = bytes(addr)
            adv_bytes = bytes(adv_data)
            name = _parse_name(adv_bytes)
            devices.update(addr_type, addr_bytes, rssi, name)
        # _IRQ_SCAN_DONE: ignored — we run continuous (duration_ms=0).

    ble.irq(_irq)
    # duration_ms=0 → indefinite scan. interval/window in microseconds.
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

            # CONFIRM is reserved for a future "mark known" action.
            # No-op for now — intentional, MVP scope.

            # Scrolling input.
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
                        # Keep selected in the visible window.
                        if selected < scroll:
                            scroll = selected
                        elif selected >= scroll + ROWS_VISIBLE:
                            scroll = selected - ROWS_VISIBLE + 1
                        last_scroll = now
                        last_redraw = 0  # force immediate redraw

            # Periodic prune + redraw, regardless of input, so RSSI/list stays live.
            if time.ticks_diff(now, last_redraw) >= REDRAW_INTERVAL_MS:
                devices.prune()
                # Clamp selected if devices were pruned.
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
            ble.gap_scan(None)  # stop scanning
        except Exception:
            pass
        try:
            ble.active(False)
        except Exception:
            pass
        oled_clear(True)
```

Design notes for the reviewer:
- `ble.gap_scan(0, ...)` runs indefinitely; we stop it in `finally`.
- IRQ data buffers are shared and reused by NimBLE — copying `addr`/`adv_data` to `bytes` before storing is mandatory.
- Sorting on every redraw (every 250 ms) is fine for tens of devices; if we ever see thousands we can keep a sorted side-structure, but YAGNI for now.
- The two `try/except` calls in `finally` are at a real system boundary (radio shutdown on app exit). Not defensive overkill — if we leave the radio scanning after exit, every subsequent app pays for it.
- CONFIRM is a documented no-op. A no-op with intent is preferable to inventing a feature we haven't designed yet.

- [ ] **Step 2: Commit**

```bash
cd ~/temporal-badge-scanner/upstream
git add firmware/initial_filesystem/apps/scanner/ble.py
git commit -m "feat(scanner): BLE scan screen (live device list, RSSI sort)"
git log --oneline -3
```

---

## Task 6: Build, flash, and verify the BLE screen on hardware

- [ ] **Step 1: Build + uploadfs**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
~/.platformio/penv/bin/pio run -e echo-dev 2>&1 | tail -5
~/.platformio/penv/bin/pio run -e echo-dev -t uploadfs --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
```

We don't need to reflash firmware (`-t upload`) since only `.py` files under `initial_filesystem/` changed. `uploadfs` is sufficient.

- [ ] **Step 2: Verify on the badge**

1. Boot, navigate to Apps → Scanner.
2. Select "BLE Scan" → CONFIRM.
3. Header reads "BLE  n=N". Within ~2–3 seconds, N becomes non-zero in any urban/office environment (your phone, AirPods, neighbours).
4. List shows rows of `<rssi> <name-or-MAC>`, sorted by RSSI (closest first).
5. Joystick down or DOWN button selects the next row; selection marker `>` moves; once selection passes the visible window the list scrolls.
6. RSSI values jitter every ~250 ms (expected — that's the redraw cadence).
7. Stale entries (a device leaving range) disappear within ~8 s.
8. BACK returns to the launcher; the launcher menu redraws cleanly.
9. Re-enter BLE Scan a second time — should still work (radio shutdown on previous exit was clean).

- [ ] **Step 3: If `import bluetooth` fails**

Failure would surface in the launcher's error screen as `ImportError: no module named 'bluetooth'` (or similar). That means the C-side build did not actually wire NimBLE in despite `MICROPY_PY_BLUETOOTH=1`. In that case:

```bash
grep -rn "modbluetooth\|nimble" firmware/src firmware/platformio.ini | head
```

…and check whether the esp32 NimBLE port is included in the build. Likely missing entries in `platformio.ini` or a build-flag gate. Stop here, surface the finding, and re-plan; don't try to silently work around a missing module.

- [ ] **Step 4: No commit needed** — verification only.

---

## Task 7: Phase 2 MVP done — outer-repo status update

- [ ] **Step 1: Update outer README to mention Phase 2 status (one-line addition)**

Edit `~/temporal-badge-scanner/README.md`. Find the section that lists phases and add (or update) a "Phase 2: BLE scan screen — done" line. Keep edits surgical; do not rewrite the README.

- [ ] **Step 2: Commit outer-repo update**

```bash
cd ~/temporal-badge-scanner
git status
git add README.md
git commit -m "docs: phase 2 MVP — BLE scan screen working"
git log --oneline -5
```

- [ ] **Step 3: Pause for review before extending**

Don't roll into RSSI heatmap, persistence, or "mark known" without revisiting the spec and writing a new plan for those. They are deliberately out of scope here.

---

## Out of scope for this plan (deferred follow-ups)

- 8×8 RSSI heatmap on the LED matrix (spec line 176).
- Persistence of "known" devices to `/apps/scanner/known.json` (spec line 165).
- Pause / clear controls on the BLE screen.
- WiFi scan screen, IR capture screen — separate Phase 2 plans.

---

## Risks and "if something blows up" notes

- **`uploadfs` errors with port busy:** same fix as upload — `lsof /dev/cu.usbmodem2101`, close the holder.
- **NimBLE init panics on boot:** check serial (`stty -f /dev/cu.usbmodem2101 115200 cs8 -cstopb -parenb; timeout 8 cat /dev/cu.usbmodem2101 | head -40`). NimBLE wants ~30 KB heap; if PSRAM allocator is wedged, `gc.collect()` before `bluetooth.BLE()` may help — but first surface the panic, don't paper over it.
- **List redraw flicker:** if the OLED flickers visibly at 250 ms cadence, raise `REDRAW_INTERVAL_MS` to 400. The current value is a guess; tune on real hardware.
- **Manifest.json shows modified after build:** known regenerator drift carried over from Phase 1. Do not commit. If git status shows other unexpected modifications, investigate before continuing.
- **`badge_ui` / `badge_app` import failure:** these live on the badge filesystem under `/lib/`. If a fresh chip flash didn't include them, run `~/.platformio/penv/bin/pio run -e echo-dev -t uploadfs ...` to push the full filesystem.
