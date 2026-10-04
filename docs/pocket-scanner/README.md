# Pocket Scanner

> Docs moved here from the retired `pjerus/temporal-badge-scanner` repo on 2026-10-04. Paths in the older specs, plans and checkpoints still say `upstream/firmware/...`; read that as `firmware/...` from the repo root.

A stripped-down fork of the Temporal Replay 26 badge firmware. Phase 1 ships a hardware-exercise demo that drives every I/O channel (joystick, buttons, IMU, OLED, 8×8 LED matrix). Phase 2 layers BLE / WiFi / IR scanning on top.

**Phase 1 status:** ✅ complete (4 commits on the `pocket-scanner-phase1` branch)

- **Spec:** `docs/pocket-scanner/superpowers/specs/2026-05-11-pocket-scanner-design.md`
- **Plan:** `docs/pocket-scanner/superpowers/plans/2026-05-11-pocket-scanner.md`
- **Upstream:** https://github.com/Architeuthis-Flux/Temporal-Replay-26-Badge (pinned to tag `0.2.4`)

## Hardware

ESP32-S3-WROOM-1 (16 MB flash, 8 MB octal PSRAM), 1.3" SSD1309 OLED on I²C, **8×8 IS31FL3731 monochrome LED matrix**, 2-axis analog joystick, 4 directional buttons, **LIS2DH12 3-axis IMU** (used as tilt/orientation sense), IR TX/RX (NEC), WiFi 2.4 GHz, Bluetooth 5 LE, 1000 mAh LiPo, USB-C.

## Build & flash

First-time setup (~5–10 min, ~500 MB):

```sh
cd ignition && ./setup.sh
```

Build + flash app partition:

```sh
cd firmware
~/.platformio/penv/bin/pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem2101
```

Flash FATFS data partition (required whenever `initial_filesystem/` changes — e.g. when adding or editing a MicroPython app):

```sh
~/.platformio/penv/bin/pio run -e echo-dev -t uploadfs --upload-port /dev/cu.usbmodem2101
```

Always use `~/.platformio/penv/bin/pio` directly — the system `pio` shim resolves to the wrong Python and fails with fatfs import errors.

## Restore to factory v0.2.4

```sh
~/Library/Arduino15/packages/esp32/tools/esptool_py/5.2.0/esptool \
  --port /dev/cu.usbmodem2101 --baud 921600 \
  write-flash 0x0 ../backups/firmware-v0.2.4/factory_echo_16MB.bin
```

This is a 16 MB full-chip image. Takes ~60 seconds. Wipes NVS-backed identity, so the badge boots as unpaired.

## What was changed from upstream

| Commit | Change |
|--------|--------|
| `feat(scanner)` | Added `/apps/scanner/main.py` — Phase 1 hardware demo |
| `chore: remove BADGE_HAS_DOOM` | Disabled DOOM build flag; deleted 4 MB `doom1.wad` |
| `feat: strip conference menu entries` | Removed Boop, Contacts, Badge Info, Map, Schedule, Sponsors, Credits |
| `feat: strip game menu entries` | Removed Draw, BreakSnake, Flappy, Synth, Tardigotchi |

Menu went from **24 curated + 6 dynamic** entries down to **12 curated + 6 dynamic**. Build size dropped from ~67.5% to ~60% of the OTA app slot (~290 KB saved on app + 4 MB on FATFS from the WAD).

Partition table is unchanged — upstream's CSV (`partitions_replay_16MB_doom.csv`) is OTA-frozen and must stay put for field-upgrade compatibility.
