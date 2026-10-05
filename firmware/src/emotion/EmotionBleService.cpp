#include "EmotionBleService.h"
#ifdef BADGE_ENABLE_EMOTION_BLE

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <string.h>

#include "EmotionFrame.h"

// Service + characteristic UUIDs (random, allocated 2026-10-05). The
// Python client in emotion-channel/ must use these exact strings.
#define EMO_SVC_UUID    "ae3428d5-a3d6-4a2d-a827-6a7c5fd1d4e0"
#define EMO_WRITE_UUID  "5a413f11-6b24-4987-a5a9-93774a4c783f"
#define EMO_STATE_UUID  "021ece59-011c-44cb-8f30-2931c0885d11"

// State characteristic layout (7 bytes, little-endian), mirrored by
// emotion-channel parse_state():
//   [0] flags  (bit0 override active, bit1 face on screen)
//   [1] override mood (0 when inactive)
//   [2] override intensity (0..255, 0 when inactive)
//   [3] override ms-left / 100  (uint16 lo)   0xFFFF = latch
//   [4] override ms-left / 100  (uint16 hi)
//   [5] autonomous mood
//   [6] battery percent
constexpr size_t kStateLen = 7;

namespace {
EmotionConsumer* s_consumer = nullptr;
BLECharacteristic* s_stateChar = nullptr;
uint8_t s_secret[8] = {0};

// A write is [8-byte shared secret][6-byte emotion frame] = 14 bytes.
// The Arduino BLE onWrite() cannot return a GATT error, so a malformed
// or unauthorized write is silently ignored — the client confirms the
// result by reading the state characteristic.
class WriteCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    if (!s_consumer) return;
    const uint8_t* data = c->getData();
    size_t len = c->getLength();
    if (!data || len != 8 + emotion::kFrameLen) return;            // malformed
    if (memcmp(data, s_secret, 8) != 0) return;                     // bad auth
    emotion::Frame f;
    if (!emotion::decode(data + 8, emotion::kFrameLen, f)) return;   // bad frame
    s_consumer->apply(f, millis());
  }
};
}  // namespace

void emotionBleBegin(EmotionConsumer& consumer, const uint8_t secret[8], const char* advName) {
  s_consumer = &consumer;
  memcpy(s_secret, secret, 8);

  BLEDevice::init(advName ? advName : "badge");
  BLEServer* server = BLEDevice::createServer();
  BLEService* svc = server->createService(EMO_SVC_UUID);

  BLECharacteristic* writeChar =
      svc->createCharacteristic(EMO_WRITE_UUID, BLECharacteristic::PROPERTY_WRITE);
  writeChar->setCallbacks(new WriteCb());

  s_stateChar =
      svc->createCharacteristic(EMO_STATE_UUID, BLECharacteristic::PROPERTY_READ);
  uint8_t zero[kStateLen] = {0};
  s_stateChar->setValue(zero, sizeof(zero));

  svc->start();

  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(EMO_SVC_UUID);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
}

void emotionBleStatePublish(EmotionConsumer& consumer, uint8_t batteryPct) {
  if (!s_stateChar) return;
  const uint32_t now = millis();
  const bool active = consumer.activeAt(now);

  uint8_t flags = 0;
  if (active) flags |= 0x01;
  if (consumer.faceOnScreen()) flags |= 0x02;

  uint32_t msLeft = consumer.msLeftAt(now);
  uint16_t ds;
  if (msLeft == UINT32_MAX) {
    ds = 0xFFFF;  // latch
  } else {
    uint32_t d = msLeft / 100;
    ds = d > 0xFFFF ? 0xFFFF : (uint16_t)d;
  }

  uint8_t buf[kStateLen];
  buf[0] = flags;
  buf[1] = active ? consumer.mood() : 0;
  buf[2] = active ? (uint8_t)(consumer.intensity() * 255.0f + 0.5f) : 0;
  buf[3] = (uint8_t)(ds & 0xFF);
  buf[4] = (uint8_t)((ds >> 8) & 0xFF);
  buf[5] = consumer.autonomousMood();
  buf[6] = batteryPct;
  s_stateChar->setValue(buf, sizeof(buf));
}

#endif  // BADGE_ENABLE_EMOTION_BLE
