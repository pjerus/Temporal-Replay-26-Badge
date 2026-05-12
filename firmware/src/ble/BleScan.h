#pragma once

#include <stdint.h>
#include <stddef.h>

// Lightweight BLE scanner for the pocket-scanner app. Distinct from
// BleBeaconScanner (which is iBeacon-only and gated on
// BADGE_ENABLE_BLE_PROXIMITY). This one keeps a fixed-size table of every
// device seen, exposed through the badge MicroPython module.
//
// Lifecycle: start() lazily initialises the BLE controller and arms an
// active scan. stop() halts the scan but leaves the controller up
// (Arduino-ESP32's BLEDevice::deinit/init cycles have known
// use-after-free hazards — same lesson as BleBeaconScanner).

namespace BleScan {

bool start();
void stop();
bool isScanning();

// Snapshot one entry from the device table. addr is 6 bytes (BD_ADDR).
// name_out is filled up to name_buf_len bytes (NUL-terminated; truncated
// if longer). Returns false if idx is out of range.
//
// idx ordering: insertion order in the table (caller sorts by RSSI etc.).
bool getEntry(int idx,
              uint8_t addr_out[6],
              int *addr_type_out,
              int *rssi_out,
              uint32_t *last_seen_ms_out,
              char *name_out,
              size_t name_buf_len);

int count();

// Drop entries not seen in the last `stale_ms` milliseconds. Safe to call
// while scanning. Returns the number of entries removed.
int prune(uint32_t stale_ms);

}  // namespace BleScan
