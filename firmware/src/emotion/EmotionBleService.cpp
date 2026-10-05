#include "EmotionBleService.h"
#ifdef BADGE_ENABLE_EMOTION_BLE

// Stub — the NimBLE GATT service is implemented in Task 6. Kept as a
// linkable no-op so the BADGE_ENABLE_EMOTION_BLE build is green first.
void emotionBleBegin(EmotionConsumer& consumer, const uint8_t secret[8], const char* advName) {
  (void)consumer;
  (void)secret;
  (void)advName;
}

void emotionBleStatePublish(EmotionConsumer& consumer, uint8_t batteryPct) {
  (void)consumer;
  (void)batteryPct;
}

#endif  // BADGE_ENABLE_EMOTION_BLE
