#pragma once
#include <stdint.h>
#include "EmotionFrame.h"

// Holds the currently injected emotion and answers whether it is still
// live at a given time. Pure logic (time passed in) so it is host-tested
// and reused by any device. Single writer (BLE task) / single reader
// (render task); fields are plain and a read is a cheap snapshot.
class EmotionConsumer {
 public:
  void apply(const emotion::Frame& f, uint32_t nowMs) {
    frame_ = f;
    setAtMs_ = nowMs;
    active_ = true;
  }
  void clear() { active_ = false; }

  bool activeAt(uint32_t nowMs) const {
    if (!active_) return false;
    if (frame_.ttlDs == 0) return true;  // latch
    return (nowMs - setAtMs_) <= (uint32_t)frame_.ttlDs * 100u;
  }
  uint8_t mood() const { return frame_.mood; }
  float intensity() const { return frame_.intensity / 255.0f; }

  uint32_t msLeftAt(uint32_t nowMs) const {
    if (!active_) return 0;
    if (frame_.ttlDs == 0) return UINT32_MAX;  // latch
    uint32_t span = (uint32_t)frame_.ttlDs * 100u;
    uint32_t elapsed = nowMs - setAtMs_;
    return elapsed >= span ? 0 : (span - elapsed);
  }

  void setFaceOnScreen(bool v) { faceOnScreen_ = v; }
  bool faceOnScreen() const { return faceOnScreen_; }

  // The mood the autonomous (idle) loop is currently showing, for state
  // readback. Set by the face when it is not overridden.
  void setAutonomousMood(uint8_t m) { autoMood_ = m; }
  uint8_t autonomousMood() const { return autoMood_; }

 private:
  emotion::Frame frame_{};
  uint32_t setAtMs_ = 0;
  volatile bool active_ = false;
  volatile bool faceOnScreen_ = false;
  volatile uint8_t autoMood_ = 0;
};
