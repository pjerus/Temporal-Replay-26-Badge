#ifdef BADGE_ENABLE_DRIVE_BLE
#include "DriveBleService.h"

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <esp_heap_caps.h>
#include <cstring>

#include "DriveCore.h"
#include "PfTreads.h"
#include "../infra/BadgeConfig.h"
#include "../ir/BadgeIR.h"

#define DRV_SVC_UUID    "80a239a9-d8c0-4b45-82eb-41fd7207df9b"
#define DRV_WRITE_UUID  "98b99101-ab97-48b5-a9c9-e666e456806c"
#define DRV_STATE_UUID  "1350f2e6-4bdf-4459-a813-4afaf1a8ffee"

namespace {
drive::Core s_core;
drive::IrLease s_lease;
pftreads::Dither s_dither;
BLECharacteristic* s_stateChar = nullptr;
uint8_t s_secret[8] = {0};

// BLE callbacks run on the BLE host task; the core runs on the main loop.
// Callbacks only park data here; driveBleTick() applies it.
portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
uint8_t s_pending[drive::kCmdLen];
uint8_t s_pendingLen = 0;       // 0 = nothing; 0xFF = malformed write
uint32_t s_pendingMs = 0;       // when the write arrived; its lifetime runs from here
bool s_connected = false;
bool s_dropPending = false;
uint32_t s_lastStateMs = 0;

class WriteCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    const uint8_t* data = c->getData();
    const size_t len = c->getLength();
    portENTER_CRITICAL(&s_mux);
    if (data && len == drive::kCmdLen) {
      memcpy(s_pending, data, drive::kCmdLen);
      s_pendingLen = drive::kCmdLen;
    } else {
      s_pendingLen = 0xFF;
    }
    s_pendingMs = millis();
    portEXIT_CRITICAL(&s_mux);
  }
};
WriteCb s_writeCb;

void addServices(BLEServer* server) {
  BLEService* svc = server->createService(DRV_SVC_UUID);
  BLECharacteristic* w =
      svc->createCharacteristic(DRV_WRITE_UUID, BLECharacteristic::PROPERTY_WRITE);
  w->setCallbacks(&s_writeCb);
  s_stateChar =
      svc->createCharacteristic(DRV_STATE_UUID, BLECharacteristic::PROPERTY_READ);
  uint8_t zero[drive::kStateLen] = {0};
  s_stateChar->setValue(zero, sizeof(zero));
  svc->start();
}
void onConnect() {
  portENTER_CRITICAL(&s_mux);
  s_connected = true;
  portEXIT_CRITICAL(&s_mux);
}
void onDisconnect() {
  portENTER_CRITICAL(&s_mux);
  s_connected = false;
  s_dropPending = true;
  s_pendingLen = 0;   // a command from a controller that has gone is void
  portEXIT_CRITICAL(&s_mux);
}

const EmotionBleExtension s_ext = {addServices, onConnect, onDisconnect};

pftreads::Tuning tuning() {
  return {(uint8_t)(badgeConfig.get(kTreadChannel) - 1),
          (int16_t)badgeConfig.get(kTreadTrimPct),
          badgeConfig.get(kTreadFlipRight) != 0};
}
}  // namespace

const EmotionBleExtension* driveBleExtension(const uint8_t secret[8]) {
  memcpy(s_secret, secret, 8);
  return &s_ext;
}

bool driveBleConnected() { return s_connected; }

void driveBleTick(uint8_t batteryPct) {
  const uint32_t now = millis();

  uint8_t buf[drive::kCmdLen];
  uint8_t len;
  uint32_t arrivedMs;
  bool dropped, connected;
  portENTER_CRITICAL(&s_mux);
  len = s_pendingLen; s_pendingLen = 0;
  arrivedMs = s_pendingMs;
  if (len == drive::kCmdLen) memcpy(buf, s_pending, drive::kCmdLen);
  dropped = s_dropPending; s_dropPending = false;
  connected = s_connected;
  portEXIT_CRITICAL(&s_mux);

  // A command's lifetime runs from when it arrived, not from when this
  // loop got to it. A disconnect is applied last, so the stop wins.
  if (len == drive::kCmdLen) s_core.onWrite(buf, len, s_secret, arrivedMs);
  else if (len == 0xFF) s_core.onWrite(nullptr, 0, s_secret, arrivedMs);
  if (dropped) s_core.onDisconnect();

  // Infrared is up while a controller is connected, and stays up until
  // the stop burst after a disconnect has gone out (see IrLease).
  const bool wantIr = s_lease.want(connected || !s_core.burstDone(), now);
  if (wantIr && !driveIrWanted) {
    // Hardware is down here (the lease's lockout outlasts its teardown),
    // so this only stores the power for the coming init.
    if (!irHwIsUp()) irSetTxPower((int)badgeConfig.get(kTreadIrPowerPct));
    s_dither.reset();
  }
  driveIrWanted = wantIr;

  const uint32_t freeBytes = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
  const drive::Out o = s_core.tick(now, freeBytes);
  if (o.send && wantIr && irHwIsUp()) {
    if (irGetMode() != IR_MODE_RAW_SYMBOL) irSetMode(IR_MODE_RAW_SYMBOL);
    int l, r;
    s_dither.next(o.leftTenths, o.rightTenths, tuning(), l, r);
    uint16_t pairs[pftreads::kPairs * 2];
    pftreads::encodePairs(pftreads::frameBits(l, r, tuning()), pairs);
    irRawSend(pairs, pftreads::kPairs, 38000);
  }

  if (s_stateChar && (o.send || now - s_lastStateMs >= 250)) {
    s_lastStateMs = now;
    uint8_t st[drive::kStateLen];
    s_core.composeState(st, now, irHwIsUp(), batteryPct, freeBytes,
                        heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL));
    s_stateChar->setValue(st, sizeof(st));
  }
}

void driveBleStatusLine(char* buf, size_t n) {
  if (!driveBleConnected()) { snprintf(buf, n, "Drive: waiting"); return; }
  snprintf(buf, n, "Drive: %s", s_core.driving() ? "moving" : "connected");
}
#endif  // BADGE_ENABLE_DRIVE_BLE
