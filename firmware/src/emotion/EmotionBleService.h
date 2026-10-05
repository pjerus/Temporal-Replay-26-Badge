#pragma once
#ifdef BADGE_ENABLE_EMOTION_BLE
#include <stdint.h>
#include "EmotionConsumer.h"

// Start the BLE emotion GATT peripheral. `secret` is the 8-byte shared
// token a writer must prefix to each emotion frame; `advName` is the BLE
// advertised name.
void emotionBleBegin(EmotionConsumer& consumer, const uint8_t secret[8], const char* advName);

// Refresh the readable state characteristic (call roughly once a second).
void emotionBleStatePublish(EmotionConsumer& consumer, uint8_t batteryPct);
#endif  // BADGE_ENABLE_EMOTION_BLE
