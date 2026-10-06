#pragma once
#ifdef BADGE_ENABLE_DRIVE_BLE
#include <cstddef>
#include <cstdint>
#include "../emotion/EmotionBleService.h"

// Tread drive over BLE: a command characteristic and a status
// characteristic on the emotion channel's server. See
// docs/superpowers/specs/tread-drive-ble-design.html.
const EmotionBleExtension* driveBleExtension(const uint8_t secret[8]);
void driveBleTick(uint8_t batteryPct);       // call every main-loop pass
bool driveBleConnected();
// The on-badge Drive app: while active it owns the treads and BLE drive
// commands are dropped. Call every loop pass with the wanted speeds (tenths).
void driveLocalSet(bool active, int8_t leftTenths, int8_t rightTenths);
bool driveLocalActive();
void driveBleStatusLine(char* buf, size_t n);
#endif
