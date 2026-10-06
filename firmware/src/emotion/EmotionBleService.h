#pragma once
#ifdef BADGE_ENABLE_EMOTION_BLE
#include <stdint.h>
#include "EmotionConsumer.h"

// Start the BLE emotion GATT peripheral. `secret` is the 8-byte shared
// token a writer must prefix to each emotion frame; `advName` is the BLE
// advertised name.
class BLEServer;
// Lets one more service ride on the same BLE server. addServices runs
// after the emotion service is created and before advertising starts.
// onConnect / onDisconnect run on the BLE host task: keep them tiny.
struct EmotionBleExtension {
  void (*addServices)(BLEServer* server);
  void (*onConnect)();
  void (*onDisconnect)();
};
void emotionBleBegin(EmotionConsumer& consumer, const uint8_t secret[8],
                     const char* advName,
                     const EmotionBleExtension* ext = nullptr);

// Refresh the readable state characteristic (call roughly once a second).
void emotionBleStatePublish(EmotionConsumer& consumer, uint8_t batteryPct);
#endif  // BADGE_ENABLE_EMOTION_BLE
