# Pocket Scanner — Design

**Date:** 2026-05-11
**Status:** Draft, pending user review
**Hardware:** Temporal Replay 26 conference badge (one of two units; the other stays factory)

## Goal

Fork the Temporal Replay 26 badge firmware into a minimal hardware platform we can build on. Phase 1 ships a stripped-down firmware where joystick, buttons, tilt switch, OLED, and NeoPixel matrix all work, with a small demo app proving it end-to-end. Phase 2 layers BLE / WiFi / IR scanning on top, turning the badge into a portable multi-band scanner.

This spec covers Phase 1 only. Phase 2 and Phase 3 are sketched at the end so the platform doesn't paint us into a corner.

## Hardware (recap)

- ESP32-S3-WROOM-1, 16 MB flash, 8 MB octal PSRAM, 240 MHz dual-core
- WiFi 2.4 GHz, Bluetooth 5 LE, native USB Serial/JTAG
- 1.3" SSD1309 128×64 monochrome OLED over I²C (SDA=GPIO5, SCL=GPIO6)
- **8×8 IS31FL3731 monochrome LED matrix** (64 LEDs, brightness only — not RGB)
- 2-axis analog joystick (GPIO1/2), 4 directional buttons (UP=44, DOWN=7, LEFT=8, RIGHT=9)
- **LIS2DH12 3-axis IMU** (tilt/face detection — not a simple switch)
- IR TX/RX (GPIO3/4, NEC protocol)
- 1000 mAh LiPo, USB-C charging
- Upstream firmware pin: `0.2.4` (https://github.com/Architeuthis-Flux/Temporal-Replay-26-Badge)

> **Spec correction (logged during implementation):** Earlier drafts described a "7×7 NeoPixel matrix" and "tilt switch" based on the upstream README. The canonical `API_REFERENCE.md` (and the actual hardware) reveal an 8×8 IS31FL3731 monochrome matrix and a LIS2DH12 accelerometer. Phase 2 scanner UI ideas that assumed RGB output (e.g., red-flash stalker alert) will need rethinking — brightness/blink patterns instead of color.

## Non-goals (Phase 1)

- No conference features (Boop, Messages, Contacts, schedule sync, QR pair)
- No DOOM
- No WiFi backend connectivity (the conference API is out of reach without the real server)
- No radio scanning yet (Phase 2)
- No PN532/RC522/CC1101 hardware additions (Phase 3)
- No second badge involvement — board #2 remains factory

## Architecture

**Hybrid C firmware + MicroPython demo app.**

The firmware fork is intentionally minimal: keep all upstream hardware drivers and platform code, strip every conference-specific feature, and expose a clean entry point that hands off to a MicroPython app. The app itself — and all future scanner features — live in MicroPython for fast iteration without re-flashing firmware.

**Rationale:** Upstream already has solid C drivers for OLED, NeoPixels, joystick, buttons, IR, NVS, FatFS, and the radio stacks. Re-implementing them in our fork would be wasted effort. Conversely, the conference UI, Boop API, and message-handling code are large, network-dependent, and useless to us. The cut is "platform = keep, application = replace."

```
┌──────────────────────────────────────────┐
│   MicroPython app (Python)               │
│   /apps/scanner/main.py                  │
│   - input loop, screen rendering         │
│   - Phase 2: scanner screens             │
└──────────────────────────────────────────┘
            ↕  MicroPython runtime
┌──────────────────────────────────────────┐
│   C firmware (forked from upstream)      │
│   - hardware drivers (kept)              │
│   - MicroPython integration (kept)       │
│   - NVS / FatFS (kept)                   │
│   - WiFi / BT stacks (kept, idle in P1)  │
│   - conference UI/API/Boop (REMOVED)     │
│   - DOOM (REMOVED)                       │
└──────────────────────────────────────────┘
            ↕
        ESP32-S3 hardware
```

## Phase 1 MVP — what we actually build

A vertical slice that proves every layer works:

1. **Fork upstream** at tag `v0.2.4` into `temporal-badge-scanner/upstream/` as a git remote-tracked clone.
2. **Build with zero changes** and flash to board #1. Confirms the build environment works end-to-end.
3. **Strip the WiFi build-secret requirement.** Upstream refuses to build without `BADGE_WIFI_SSID`, `BADGE_WIFI_PASS`, `BADGE_SERVER_URL`. Rip out the conference API code that depends on them, so the requirement disappears.
4. **Remove conference UI.** Delete or stub the Boop, Messages, Contacts, schedule, QR-pair, and MAP/SCHEDULE/LED/DRAW menu entries. The root menu becomes a single entry: "Scanner" (which in Phase 1 just launches our demo app).
5. **Remove DOOM.** Delete `doom1.wad` from `initial_filesystem/`. Disable the `BADGE_HAS_DOOM` build flag.
6. **Write the demo MicroPython app** at `initial_filesystem/apps/scanner/main.py`. The demo proves all I/O works:
   - **Input:** joystick moves a cursor; buttons trigger actions; tilt switch toggles a flag
   - **OLED:** renders the cursor, button states, and tilt flag
   - **NeoPixel matrix:** shows a 7×7 pattern that responds to joystick position (e.g., lights up the LED under the cursor)
   - Press-and-hold a designated button to exit cleanly
7. **Flash and verify** end-to-end on board #1.

**Definition of done for Phase 1:** firmware flashes cleanly, demo app launches automatically from the badge menu, all five I/O channels (joystick, buttons, tilt, OLED, NeoPixels) respond correctly to user input.

## What we keep, strip, and add

**Keep (from upstream):**
- Bootloader, partition table, build system (PlatformIO + esp-idf)
- All hardware drivers: SSD1309 OLED, WS2812 NeoPixel matrix, joystick ADC, button GPIO, tilt switch, IR TX/RX
- MicroPython runtime and bindings
- NVS (settings storage) and FatFS (app filesystem)
- WiFi and BT stacks (idle in Phase 1, used in Phase 2)
- Power management (deep sleep, motion wake)
- USB Serial/JTAG support
- File manager interface for pushing app updates over USB

**Strip:**
- Boop / Messages / Contacts / Pair / QR menus and all backing code
- Schedule sync and ETag caching
- WiFi build-secret requirement (cascades from removing the conference API)
- DOOM and `doom1.wad` (~4 MB of FatFS reclaimed)
- MAP / SCHEDULE / LED / DRAW menu entries (the original conference UI)
- Settings related to conference features

**Add:**
- A "Scanner" entry in the root menu (Phase 1: launches the demo; Phase 2: a sub-menu of scanner screens)
- MicroPython app at `initial_filesystem/apps/scanner/main.py`
- Project README in `temporal-badge-scanner/` explaining build/flash/restore

## Repo layout

```
~/
├── backups/firmware-v0.2.4/             # already have: factory bins
├── blink/                                # leftover; delete during cleanup
└── temporal-badge-scanner/               # this project (git-tracked)
    ├── .git/
    ├── README.md                         # build/flash/restore quick reference
    ├── docs/superpowers/specs/
    │   └── 2026-05-11-pocket-scanner-design.md   # this file
    └── upstream/                         # cloned from Architeuthis-Flux/Temporal-Replay-26-Badge
        └── firmware/
            ├── src/                      # C platform (we edit menus here)
            └── initial_filesystem/apps/
                └── scanner/main.py       # our MicroPython app
```

Upstream is tracked as a Git remote in `temporal-badge-scanner/upstream/`. The outer `temporal-badge-scanner/` repo holds our spec, docs, and any project-level files. Our changes to upstream code live in the cloned `upstream/` subdirectory and are committed there with reference to our spec.

`pi-arduino/` is not renamed — the subfolder name reflects the actual project.

## Build / flash / restore workflow

**First-time setup (one-off):**
```
cd upstream/ignition && ./setup.sh
```
Installs PlatformIO + esp-idf toolchain to `~/.platformio/`. Disk ~500 MB. Independent of the `arduino-cli` installation already present.

**Firmware rebuild + flash:**
```
cd upstream/firmware
pio run -e echo -t upload --upload-port /dev/cu.usbmodem2101
```

**MicroPython app update (fast loop):**
Push the `.py` file directly to the badge's FatFS over the file-manager interface — no firmware reflash needed. (Upstream documents this in `docs/08-file-manager`; exact command captured during implementation.)

**Serial debugging:**
```
stty -f /dev/cu.usbmodem2101 115200 cs8 -cstopb -parenb
cat /dev/cu.usbmodem2101
```
Or: `upstream/firmware/serial_log.py`.

**Factory restore (anytime):**
```
~/Library/Arduino15/packages/esp32/tools/esptool_py/5.2.0/esptool \
  --port /dev/cu.usbmodem2101 --baud 921600 \
  write-flash 0x0 backups/firmware-v0.2.4/factory_echo_16MB.bin
```
Path already verified working today.

## Data persistence (forward-looking, Phase 2)

When the scanner screens land, on-device data lives in FatFS:
- `/apps/scanner/known.json` — BLE devices marked "known"
- `/apps/scanner/ir-codes.json` — saved IR captures
- `/apps/scanner/log.jsonl` — optional rolling scan log

No remote sync, no backend. Off-device backups happen by reading FatFS over USB if the user wants.

## LED matrix usage (forward-looking, Phase 2)

The matrix is monochrome — brightness only — so signals encode via intensity, position, and blink rather than color.

- Idle: dim breathing pattern
- BLE/WiFi scan: 8×8 RSSI heatmap (top 64 devices/APs by signal, brightness ∝ RSSI)
- Stalker alert: fast all-on blink
- IR replay: brief all-on pulse
- Phase 1 demo: cursor follows joystick; whatever LED the cursor sits on lights up (verified working)

## Open questions / risks

1. **MicroPython API coverage.** Confirmed unknown. We need `bluetooth`, `network.WLAN`, FatFS, and GPIO/driver access exposed to MicroPython for Phase 2. If `bluetooth` is missing, Phase 2 grows by one session (add the C binding). For Phase 1 the demo only needs OLED, NeoPixel, joystick, and button bindings — almost certainly present since upstream's existing apps use them.

2. **Build-secret rip vs. stub.** Two ways to handle the missing WiFi credentials:
   - **Rip:** delete the conference API code entirely. Cleaner long-term but a larger initial diff.
   - **Stub:** feed bogus values and dead-code the network calls behind a flag. Smaller diff but leaves dead code in the tree.
   - **Decision:** rip. Phase 1 has no use for the conference API and Phase 2 will use raw WiFi/BT directly.

3. **Menu surgery scope.** The conference UI is likely interwoven with the badge state machine. We may discover that "remove Boop" cascades into removing identity, pairing, and contacts code — fine, since we want all of that gone — but the diff could be larger than expected. Budget extra time for the strip step.

4. **MicroPython app launcher.** Upstream's production firmware hides the generic Apps menu (per its README) and requires a native `GUI.cpp` launcher + icon to surface an attendee-facing MicroPython app. We need to either add a launcher entry for our scanner app or enable the dev menu's generic Apps browser. Implementation detail — picked during build.

5. **Upstream drift.** Upstream pushes daily. We pin to `v0.2.4` and do not chase newer releases. Upstream is tracked as a remote so we can pull selectively later if needed.

## Phase 2 — sketch (not in scope for this spec)

After Phase 1 is stable, add scanner screens one at a time. Each is a self-contained MicroPython module the main app navigates into:

- **BLE Scan** — live list of nearby BLE devices (name, MAC, RSSI), joystick scrolls
- **Stalker Watch** — persistence tracking; alert on unknowns following >X minutes
- **WiFi Bands** — AP inventory with NeoPixel RSSI heatmap
- **IR Capture / Replay** — sniff and save NEC codes, replay from saved slots

## Phase 3 — sketch

Add a PN532 NFC reader (~$3, I²C) wired to the GPIO breakout pads on the back. Adds an "NFC" screen for reading 13.56 MHz cards (UID always, full-clone where the system allows).

## Restore path (always available)

Board #1's factory firmware is backed up at `backups/firmware-v0.2.4/factory_echo_16MB.bin` (16 MB full chip image). Flashing it via esptool restores the badge to as-shipped state in ~60 seconds. Verified working today. Board #2 remains untouched.
