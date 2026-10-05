#pragma once
#include <stdint.h>
#include "../emotion/EmotionConsumer.h"

// Returns true and fills moodOut/intensityOut when an injected emotion
// should drive the face at nowMs; false to use the autonomous picker.
inline bool chooseOverride(const EmotionConsumer& c, uint32_t nowMs,
                           uint8_t& moodOut, float& intensityOut) {
  if (!c.activeAt(nowMs)) return false;
  moodOut = c.mood();
  intensityOut = c.intensity();
  return true;
}
