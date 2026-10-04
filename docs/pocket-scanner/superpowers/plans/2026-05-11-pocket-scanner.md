# Pocket Scanner — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a stripped-down fork of the Temporal Replay 26 badge firmware where joystick + buttons + tilt + OLED + NeoPixel matrix all work, demonstrated by a MicroPython demo app launched from the badge menu.

**Architecture:** Fork upstream at tag `v0.2.4`. Build with PlatformIO `echo-dev` env (exposes generic Apps menu). Add a MicroPython demo app at `/apps/scanner/main.py` — it auto-registers via dunders. Strip conference UI screens and DOOM. Flash via the bundled esptool. Outer git repo tracks our project docs; inner upstream clone has its own git history we don't push.

**Tech Stack:** ESP32-S3-WROOM-1, PlatformIO + ESP-IDF, C++ (firmware mods), MicroPython (demo app).

---

## File Structure

```
~/temporal-badge-scanner/
├── README.md                                 # NEW: build/flash/restore quickref
├── .gitignore                                # NEW: ignore upstream/
├── docs/superpowers/
│   ├── specs/2026-05-11-pocket-scanner-design.md
│   └── plans/2026-05-11-pocket-scanner.md    # this file
└── upstream/                                 # NEW: cloned Architeuthis-Flux repo @ v0.2.4 (gitignored from outer)
    └── firmware/
        ├── wifi.local.env                    # NEW: placeholder build secrets
        ├── initial_filesystem/
        │   ├── apps/scanner/
        │   │   ├── __init__.py               # NEW: empty
        │   │   └── main.py                   # NEW: demo app
        │   └── doom1.wad                     # DELETE
        ├── src/
        │   ├── main.cpp                      # MODIFY: remove conference menu entries
        │   └── screens/
        │       ├── BoopScreen.{cpp,h}        # DELETE (and from build)
        │       ├── ContactsScreen.{cpp,h}    # DELETE
        │       ├── ContactDetailScreen.{cpp,h} # DELETE
        │       └── (other conference screens)  # DELETE as identified
        └── platformio.ini                    # MODIFY: drop BADGE_HAS_DOOM
```

**Boundary discipline:**
- Outer repo (`temporal-badge-scanner/`) holds our spec, plan, project README, .gitignore
- Inner repo (`temporal-badge-scanner/upstream/`) is a git clone of upstream with our changes on a local branch `pocket-scanner-phase1`
- Outer repo never tracks `upstream/` — see .gitignore in Task 2

---

## Task 1: Clone upstream at tag v0.2.4

**Files:**
- Create: `~/temporal-badge-scanner/upstream/` (git clone)

- [ ] **Step 1: Clone the upstream repo**

```bash
cd ~/temporal-badge-scanner
git clone https://github.com/Architeuthis-Flux/Temporal-Replay-26-Badge.git upstream
```

- [ ] **Step 2: Check out v0.2.4 tag and create a working branch**

```bash
cd upstream
git fetch --tags
git checkout 0.2.4
git switch -c pocket-scanner-phase1
git log --oneline -1
```

Expected output: a single commit line for tag `0.2.4`, branch is now `pocket-scanner-phase1`.

- [ ] **Step 3: Configure local git user inside upstream/ (so commits to our branch are attributable)**

```bash
git config user.email "pat.jerus@gmail.com"
git config user.name "Pat"
```

- [ ] **Step 4: Verify the factory binary in our backups matches upstream's**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
shasum -a 256 factory_echo_16MB.bin
shasum -a 256 ~/backups/firmware-v0.2.4/factory_echo_16MB.bin
```

Expected: both SHAs match. (The backup we flashed earlier is the same file the repo ships.)

---

## Task 2: Outer repo housekeeping

**Files:**
- Create: `~/temporal-badge-scanner/.gitignore`
- Create: `~/temporal-badge-scanner/README.md`

- [ ] **Step 1: Write `.gitignore`**

```bash
cat > ~/temporal-badge-scanner/.gitignore <<'EOF'
upstream/
*.log
.DS_Store
EOF
```

- [ ] **Step 2: Write project README (build/flash/restore quickref)**

```bash
cat > ~/temporal-badge-scanner/README.md <<'EOF'
# Pocket Scanner

A stripped-down fork of the Temporal Replay 26 badge firmware. Phase 1 ships
a hardware-exercise demo (joystick, buttons, tilt, OLED, NeoPixel matrix).
Phase 2 layers BLE / WiFi / IR scanning on top.

- **Spec:** `docs/superpowers/specs/2026-05-11-pocket-scanner-design.md`
- **Plan:** `docs/superpowers/plans/2026-05-11-pocket-scanner.md`
- **Upstream:** https://github.com/Architeuthis-Flux/Temporal-Replay-26-Badge (pinned to `0.2.4`)

## Build & flash

First-time setup:
```
cd upstream/ignition && ./setup.sh
```

Rebuild + flash:
```
cd upstream/firmware
pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101
```

## Push a MicroPython app update (fast loop)

After the firmware is flashed, app `.py` files can be pushed without reflashing.
See `upstream/docs/08-file-manager.md` for the exact command.

## Restore to factory v0.2.4

```
~/Library/Arduino15/packages/esp32/tools/esptool_py/5.2.0/esptool \
  --port /dev/cu.usbmodem2101 --baud 921600 \
  write-flash 0x0 ../backups/firmware-v0.2.4/factory_echo_16MB.bin
```
EOF
```

- [ ] **Step 3: Commit outer-repo housekeeping**

```bash
cd ~/temporal-badge-scanner
git add .gitignore README.md
git commit -m "project: README + gitignore"
git log --oneline
```

Expected: two commits in outer repo (the design spec from earlier, plus this one).

---

## Task 3: Install PlatformIO toolchain

**Files:** none (modifies `~/.platformio/`)

- [ ] **Step 1: Read the setup script first to know what it'll do**

```bash
cd ~/temporal-badge-scanner/upstream/ignition
cat setup.sh | head -40
```

Expected: script installs PlatformIO core, pulls toolchain, may install Temporal CLI and esptool. ~500 MB.

- [ ] **Step 2: Run the setup script**

```bash
cd ~/temporal-badge-scanner/upstream/ignition
./setup.sh
```

Watch for errors. If it asks about Temporal CLI install and you don't want it, skip; PlatformIO is the load-bearing piece.

- [ ] **Step 3: Verify `pio` works**

```bash
~/.platformio/penv/bin/pio --version
```

Expected: prints a version like `PlatformIO Core, version 6.x.x`.

- [ ] **Step 4: Add `pio` to current shell PATH for convenience**

```bash
export PATH="$HOME/.platformio/penv/bin:$PATH"
which pio
```

Expected: `~/.platformio/penv/bin/pio`.

---

## Task 4: Make the vanilla build succeed (placeholder WiFi secrets)

**Files:**
- Create: `upstream/firmware/wifi.local.env`

The upstream build refuses to start without `BADGE_WIFI_SSID`, `BADGE_WIFI_PASS`, `BADGE_SERVER_URL`. Feed it placeholder values so we can build. The network-dependent code paths won't matter for Phase 1 (we don't connect to anything).

> **Trade-off vs. spec:** the spec's open question 2 said "rip the conference API code entirely (cleaner long-term) rather than stub with placeholders." We're deliberately doing placeholders here. The full rip touches identity/pairing/boops/messaging/schedule code across many files and is bigger than Phase 1's MVP needs. Phase 1's win condition is "demo app on stripped firmware"; the rip can be done as a separate cleanup pass once we have the demo working and know exactly which code paths are reached. The placeholder approach has zero risk of breaking the vanilla build.

- [ ] **Step 1: Read the example file**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
cat wifi.local.env.example
```

- [ ] **Step 2: Write placeholder env file**

```bash
cat > wifi.local.env <<'EOF'
BADGE_WIFI_SSID=pocket-scanner-dev
BADGE_WIFI_PASS=unused-in-phase-1
BADGE_SERVER_URL=http://127.0.0.1:1
EOF
```

The SSID is something the badge will never connect to; the URL points to a port nothing listens on. Both are intentional dead-ends.

- [ ] **Step 3: Verify .gitignore in upstream firmware ignores this file**

```bash
grep -F "wifi.local.env" .gitignore
```

Expected output: `wifi.local.env` (it's listed). If not, our placeholder won't accidentally get committed.

---

## Task 5: Build vanilla v0.2.4 firmware (no code changes)

This is the architecture-validation step. If the unchanged upstream builds, our environment is good and we can iterate. If it fails, we surface that before making any changes.

- [ ] **Step 1: Build the `echo-dev` env**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
pio run -e echo-dev 2>&1 | tail -20
```

Expected: lines ending with `========= [SUCCESS] Took N.NN seconds =========`. May take 5–10 minutes the first time (toolchain caches need to populate).

- [ ] **Step 2: Locate the built firmware**

```bash
ls -lh .pio/build/echo-dev/firmware.bin
```

Expected: a file in the ~2–3 MB range.

- [ ] **Step 3: Flash the vanilla build (overwrites our earlier blink and the factory restore)**

```bash
pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101 2>&1 | tail -10
```

Expected: a successful upload ending with `Hard resetting via RTS pin...`.

If port-busy error: close any Chrome tab holding `/dev/cu.usbmodem2101` (we hit this before).

- [ ] **Step 4: Verify the badge boots**

Look at the OLED. It should show the boot animation and land in the badge menu (similar to the factory image — `echo-dev` is the dev-menu variant of `echo`, same UX plus extra debug screens).

Also check serial:
```bash
stty -f /dev/cu.usbmodem2101 115200 cs8 -cstopb -parenb
timeout 8 cat /dev/cu.usbmodem2101 | head -30
```

Expected: boot-log lines, ending in the badge running normally (no panic loops). Confirm with eye on OLED.

- [ ] **Step 5: Commit a checkpoint inside upstream/**

```bash
git status
```

Should be clean (we only added `wifi.local.env` which is gitignored). If anything else is modified, investigate before continuing.

```bash
git log --oneline -3
```

Should show we're sitting at the v0.2.4 tag commit. No new commit needed yet.

---

## Task 6: Add the scanner demo MicroPython app

**Files:**
- Create: `upstream/firmware/initial_filesystem/apps/scanner/main.py`
- Create: `upstream/firmware/initial_filesystem/apps/scanner/__init__.py` (empty marker)

This is the value step — we get our own app showing in the badge menu.

- [ ] **Step 1: Read the API_REFERENCE to confirm function names for OLED, joystick, buttons, NeoPixel matrix, tilt**

```bash
cd ~/temporal-badge-scanner/upstream
find . -name "API_REFERENCE*" -type f
cat firmware/initial_filesystem/docs/API_REFERENCE.md 2>/dev/null | head -200 || cat docs/API_REFERENCE.md 2>/dev/null | head -200
```

Note exact names of: OLED draw + flush, joystick read (x/y), button read (state and "just pressed"), tilt-switch read, NeoPixel matrix set-pixel and flush, and the `exit()` semantics for returning to menu.

If function names differ from what's used in Step 2, update the demo app code to match before flashing.

- [ ] **Step 2: Write the demo app**

```bash
mkdir -p ~/temporal-badge-scanner/upstream/firmware/initial_filesystem/apps/scanner
touch ~/temporal-badge-scanner/upstream/firmware/initial_filesystem/apps/scanner/__init__.py
```

```python
# /apps/scanner/main.py
__title__ = "Scanner"
__description__ = "Phase 1 hardware demo"
__order__ = 0

import time

# Demo state — cursor on the 7x7 NeoPixel matrix moves with the joystick.
# Buttons set color; tilt switch toggles output brightness.
cursor_x = 3
cursor_y = 3
color_index = 0
bright = True

COLORS = [
    (32, 0, 0),   # red
    (0, 32, 0),   # green
    (0, 0, 32),   # blue
    (24, 24, 0),  # yellow
]
DIM_DIVISOR = 4  # when not bright

JOY_DEADZONE = 200   # adjust after testing — values seen ±2048
MATRIX_W = 7
MATRIX_H = 7
MATRIX_LEN = MATRIX_W * MATRIX_H

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def matrix_index(x, y):
    # Layout assumed row-major; if upstream uses serpentine, swap odd rows.
    return y * MATRIX_W + x

def render_oled():
    oled_clear()
    oled_set_cursor(0, 0)
    oled_print("Scanner — Phase 1")
    oled_set_cursor(0, 12)
    oled_print("X{:d} Y{:d}".format(cursor_x, cursor_y))
    oled_set_cursor(0, 24)
    oled_print("Color " + ("RGBY"[color_index]))
    oled_set_cursor(0, 36)
    oled_print("Tilt: " + ("HI" if bright else "LO"))
    oled_set_cursor(0, 52)
    oled_print("BACK=quit")
    oled_show()

def render_matrix():
    # Clear the matrix, then light only the cursor cell.
    matrix_clear()
    r, g, b = COLORS[color_index]
    if not bright:
        r, g, b = r // DIM_DIVISOR, g // DIM_DIVISOR, b // DIM_DIVISOR
    matrix_set_pixel(matrix_index(cursor_x, cursor_y), r, g, b)
    matrix_show()

def read_joystick_dxdy():
    # Returns (-1, 0, +1) per axis based on deadzone.
    jx = joystick_x()
    jy = joystick_y()
    dx = 0 if abs(jx) < JOY_DEADZONE else (1 if jx > 0 else -1)
    dy = 0 if abs(jy) < JOY_DEADZONE else (1 if jy > 0 else -1)
    return dx, dy

def loop():
    global cursor_x, cursor_y, color_index, bright
    last_move = 0
    render_oled()
    render_matrix()
    while True:
        now = time.ticks_ms()

        # Movement on a short cooldown so the cursor doesn't fly across.
        if time.ticks_diff(now, last_move) > 120:
            dx, dy = read_joystick_dxdy()
            if dx or dy:
                cursor_x = clamp(cursor_x + dx, 0, MATRIX_W - 1)
                cursor_y = clamp(cursor_y + dy, 0, MATRIX_H - 1)
                last_move = now
                render_oled()
                render_matrix()

        # A button cycles color.
        if button_just_pressed("A"):
            color_index = (color_index + 1) % len(COLORS)
            render_oled()
            render_matrix()

        # B button toggles brightness as a software-side proxy for the tilt switch.
        if button_just_pressed("B"):
            bright = not bright
            render_oled()
            render_matrix()

        # Real tilt switch also toggles brightness — proves the input wire works.
        if tilt_just_changed():
            bright = not bright
            render_oled()
            render_matrix()

        # BACK quits.
        if button_just_pressed("BACK"):
            matrix_clear()
            matrix_show()
            oled_clear()
            oled_show()
            return

        time.sleep_ms(20)

try:
    loop()
finally:
    exit()
```

Write that file to `~/temporal-badge-scanner/upstream/firmware/initial_filesystem/apps/scanner/main.py`.

**Note:** the function names above (`oled_print`, `button_just_pressed("A")`, `joystick_x()`, `matrix_set_pixel`, `tilt_just_changed`) are best-effort guesses based on the README's API style. Confirm exact names against the API reference read in Step 1 and rename before flashing. The structural pattern (poll loop, render-on-change, exit on BACK) is the part that matters.

- [ ] **Step 3: Build with the new app embedded**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
pio run -e echo-dev 2>&1 | tail -10
```

Expected: SUCCESS. The build embeds files under `initial_filesystem/` via `firmware/scripts/generate_startup_files.py`.

- [ ] **Step 4: Flash and test**

```bash
pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
```

Then on the badge:
1. Navigate to the dev Apps menu
2. Find "Scanner" — it should appear with the title from `__title__`
3. Open it
4. Joystick moves a single lit pixel on the NeoPixel matrix
5. Button A cycles the color (red → green → blue → yellow)
6. Button B or physical tilt toggles brightness
7. BACK returns to the menu

If any of the five I/O channels fails (joystick, A button, B button, tilt, OLED, matrix), fix only that channel before continuing. If function names were wrong, rename in `main.py`, rebuild, reflash.

- [ ] **Step 5: Commit the demo app to the upstream working branch**

```bash
cd ~/temporal-badge-scanner/upstream
git add firmware/initial_filesystem/apps/scanner/
git commit -m "feat(scanner): phase-1 demo app exercising joystick, buttons, tilt, OLED, matrix"
git log --oneline -3
```

---

## Task 7: Remove DOOM

**Files:**
- Delete: `upstream/firmware/initial_filesystem/doom1.wad` (if present)
- Modify: `upstream/firmware/platformio.ini` (remove `BADGE_HAS_DOOM` from the `echo-dev` build flags)

- [ ] **Step 1: Check if doom1.wad is present in the build tree**

```bash
cd ~/temporal-badge-scanner/upstream
ls -lh firmware/initial_filesystem/doom1.wad 2>&1
```

If absent (recall it's ignored from git and CI-fetched during release), nothing to delete locally. If present, delete it:

```bash
rm firmware/initial_filesystem/doom1.wad
```

- [ ] **Step 2: Find the `BADGE_HAS_DOOM` flag in `platformio.ini`**

```bash
grep -n "BADGE_HAS_DOOM" firmware/platformio.ini
```

Note the line numbers. Expected: at least one occurrence in the `[env:echo]` section.

- [ ] **Step 3: Remove the flag**

Edit `firmware/platformio.ini`. For each line that adds `-DBADGE_HAS_DOOM` to `build_flags`, delete just that flag (not the whole line if it contains other flags). If a line is *only* `-DBADGE_HAS_DOOM` in a continuation, delete the line entirely.

After editing:

```bash
grep -n "BADGE_HAS_DOOM" firmware/platformio.ini
```

Expected: no matches.

- [ ] **Step 4: Find any C++ code that checks `BADGE_HAS_DOOM`**

```bash
grep -rn "BADGE_HAS_DOOM" firmware/src firmware/include 2>&1 | head -20
```

For each `#ifdef BADGE_HAS_DOOM` … `#endif` block, the code inside will simply not compile (which is what we want). For `#if defined(BADGE_HAS_DOOM)` likewise. We don't need to delete the source — it'll be dead code, which is fine for Phase 1.

- [ ] **Step 5: Build without DOOM**

```bash
pio run -e echo-dev 2>&1 | tail -10
```

Expected: SUCCESS. Sketch size may shrink slightly.

- [ ] **Step 6: Flash and verify the badge still boots; check the menu**

```bash
pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
```

On the badge: navigate to where DOOM used to live (likely under the dev menu's Apps or a dedicated entry). Confirm it's gone or its launcher errors gracefully.

If there's a dangling DOOM menu entry that crashes on launch, note its location for Task 8 (we'll strip it along with the conference entries).

- [ ] **Step 7: Commit**

```bash
git add firmware/platformio.ini
git commit -m "chore: remove BADGE_HAS_DOOM build flag"
git log --oneline -5
```

---

## Task 8: Strip conference menu entries

**Files:**
- Modify: `upstream/firmware/src/main.cpp` (and possibly `GUI.cpp` / `GridMenuScreen.cpp` / similar)
- Possibly delete: `upstream/firmware/src/screens/BoopScreen.{cpp,h}`, `ContactsScreen.{cpp,h}`, `ContactDetailScreen.{cpp,h}`, and friends

This task involves code archaeology. Do it in steps: find first, decide second, edit third.

- [ ] **Step 1: Identify the production menu entries to remove**

The conference menu shows: Boop, Messages, Contacts, New Msg, Settings, QR / Pair (per upstream README), plus the MAP / SCHEDULE / LED / DRAW entries we saw in the photo. Find where each is wired into the menu.

```bash
cd ~/temporal-badge-scanner/upstream/firmware
grep -rn "BoopScreen\|ContactsScreen\|ContactDetail\|QRPairScreen" src/ | head -40
grep -rn "\"Boop\"\|\"Contacts\"\|\"Messages\"\|\"New Msg\"\|\"QR\"\|\"Pair\"" src/ | head -40
```

Note the file + line numbers where these names appear in tables/arrays/switch statements.

- [ ] **Step 2: Identify the menu table or registration function**

Most badge firmware uses one of:
- A constant array of menu entries (e.g., `static const MenuEntry MAIN_MENU[]`)
- A series of `menu.add(...)` calls in a setup function

Find it. The most likely locations are `src/main.cpp` or `src/ui/GUI.cpp`. The Architeuthis README mentioned a Grid menu — `src/screens/GridMenuScreen.cpp` is also a candidate.

```bash
grep -rn "MAIN_MENU\|main_menu\|registerMenuItems\|buildMainMenu" src/ | head -20
```

- [ ] **Step 3: Delete the conference entries from the menu**

Edit the menu file. Remove the rows/calls for: Boop, Messages, Contacts, New Msg, QR/Pair. Keep: Settings (some sub-options may still be useful), Apps, Diagnostics (dev-menu only), Files (dev-menu only).

After editing, the menu should be small: roughly Apps + Settings + Diagnostics + Files + Help.

- [ ] **Step 4: Rebuild and check link errors**

```bash
pio run -e echo-dev 2>&1 | tail -30
```

If the linker complains about undefined references to deleted screens, that means other code (besides the menu) instantiates them. Leave the screen source files in place for now (they're dead code) and just remove the menu entries — the link will succeed because the screens still exist as classes, just unreachable. Only delete the screen source files in a later cleanup pass.

If a build error is about a missing menu entry constant, restore that entry temporarily and find what else references it.

- [ ] **Step 5: Flash and verify the minimal menu**

```bash
pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
```

On the badge: confirm the main menu now shows only the non-conference entries, our Scanner app is still reachable via Apps, and nothing crashes when navigating.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: strip conference menu entries (Boop, Messages, Contacts, Pair, QR, etc.)"
git log --oneline -5
```

---

## Task 9: Optional — delete dead conference screen source files

This is cleanup, not blocking. Do it if Task 8's link succeeded without dead references.

**Files:**
- Delete: `upstream/firmware/src/screens/BoopScreen.{cpp,h}`
- Delete: `upstream/firmware/src/screens/ContactsScreen.{cpp,h}`
- Delete: `upstream/firmware/src/screens/ContactDetailScreen.{cpp,h}`
- Delete: any other unreferenced conference screen files identified in Task 8
- Modify: any `.cpp` file that `#include`s a deleted header

- [ ] **Step 1: For each candidate file, grep for remaining references**

```bash
cd ~/temporal-badge-scanner/upstream/firmware
for f in BoopScreen ContactsScreen ContactDetailScreen; do
  echo "--- $f ---"
  grep -rln "$f" src/ | grep -v "/$f\."
done
```

A file is safe to delete only if the result for that file is empty (no callers remain).

- [ ] **Step 2: Delete safe files**

```bash
rm src/screens/BoopScreen.cpp src/screens/BoopScreen.h
# repeat for other safe files
```

- [ ] **Step 3: Build to confirm no broken includes**

```bash
pio run -e echo-dev 2>&1 | tail -10
```

Expected: SUCCESS. If a `.cpp` file `#include`d a header you deleted, fix that include (remove it) and rebuild.

- [ ] **Step 4: Flash and re-verify the menu still works**

```bash
pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: delete dead conference screen source files"
git log --oneline -5
```

---

## Task 10: Final verification + outer-repo commit

- [ ] **Step 1: Walk through the demo app's behavior end-to-end one more time**

Flash is current. On the badge:
1. Boot → main menu has Apps, Settings, Diagnostics, etc. — no Boop/Messages/Contacts/Pair
2. Apps → Scanner — launches our demo
3. Joystick → cursor moves on the matrix
4. A → color cycles
5. B → brightness toggles
6. Physical tilt → brightness toggles (proves tilt-switch input)
7. BACK → returns to Apps menu cleanly

If any of these fail, fix the specific failure before declaring Phase 1 done.

- [ ] **Step 2: Capture the final demo state for the README**

```bash
cd ~/temporal-badge-scanner/upstream
git log --oneline pocket-scanner-phase1 ^0.2.4
```

Expected: a small list (4–6) of focused commits — `wifi.local.env`/build verification (if committed), demo app, remove DOOM, strip conference menus, optional cleanup.

- [ ] **Step 3: Update outer-repo README with the final command set**

Edit `~/temporal-badge-scanner/README.md` and replace the placeholder `pio run -e echo` with whatever final env we landed on (likely `echo-dev`). Add a "Phase 1 status: complete" line at top.

- [ ] **Step 4: Commit outer README update**

```bash
cd ~/temporal-badge-scanner
git add README.md
git commit -m "docs: phase 1 complete — demo app working"
git log --oneline
```

- [ ] **Step 5: Clean up `pi-arduino/blink/`**

That sketch is leftover and obsolete now.

```bash
rm -rf ~/blink
```

- [ ] **Step 6: Phase 1 done — pause for review before any Phase 2 work**

Sit down with the spec's Phase 2 sketch and decide whether to keep going on the same branch or cut a new spec. Do not start radio scanning work without that decision.

---

## Risks and "if something blows up" notes

- **PlatformIO setup fails:** Check `~/.platformio/penv/` exists. If `ignition/setup.sh` was killed mid-install, delete `~/.platformio/` and rerun. Disk needs ~500 MB free.
- **Vanilla build fails:** Most common reason is missing `wifi.local.env`. Second-most-common is toolchain not yet installed (PlatformIO downloads on first run; takes several minutes). Don't start stripping code while the vanilla build is broken.
- **Flash fails with "port busy":** A Chrome tab or `cat` process is holding `/dev/cu.usbmodem2101`. Run `lsof /dev/cu.usbmodem2101` to find the owner. Close that program (don't quit Chrome — close the tab).
- **Badge crashes / boot loops after a flash:** Pull serial logs (`cat /dev/cu.usbmodem2101`) to find the panic. Most likely cause: a menu reference to a deleted screen. If unsalvageable, restore factory firmware (procedure in our README) and re-do the offending task more carefully.
- **MicroPython API names don't match:** Read `firmware/docs/MicroPythonDeveloperGuide.md` or `firmware/initial_filesystem/docs/API_REFERENCE.md` for canonical names. Rename in `main.py`. Common renames: `oled_text` vs `oled_print`, `btn_down("A")` vs `button_just_pressed("A")`.
- **Joystick deadzone wrong:** Print `joystick_x()`/`joystick_y()` values via the OLED during the demo. Adjust `JOY_DEADZONE` so resting state reads zero.

---

## What this plan does NOT do

- Does not strip every conference-related C++ class (only the menu entries that surface them). Full deletion is Task 9, marked optional.
- Does not add BLE / WiFi / IR scanning — that's Phase 2, separate plan.
- Does not add hardware modules (PN532 etc.) — that's Phase 3, separate plan.
- Does not modify board #2. It stays factory throughout.
