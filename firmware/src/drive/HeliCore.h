#pragma once
// Syma S107G helicopter: IR frame and the HELI app's controls.
// Pure logic, no hardware calls — host-tested in test/host/test_heli_core.cpp.
#include <cstdint>

namespace heli {

// Frame: 2000/2000 us header, 32 bits MSB first, each a 300 us mark then a
// 300 us (0) or 700 us (1) space, then a closing mark. 38 kHz carrier.
constexpr int kPairs = 34;

inline uint32_t frameWord(uint8_t yaw, uint8_t pitch, uint8_t throttle, uint8_t trim, bool channelB) {
  return ((uint32_t)(yaw & 0x7F) << 24) | ((uint32_t)(pitch & 0x7F) << 16) |
         ((uint32_t)((channelB ? 0x80 : 0) | (throttle & 0x7F)) << 8) | (trim & 0x7F);
}

inline void encodePairs(uint32_t word, uint16_t out[kPairs * 2]) {
  out[0] = 2000; out[1] = 2000;
  for (int i = 0; i < 32; i++) {
    out[2 + i * 2] = 300;
    out[3 + i * 2] = ((word >> (31 - i)) & 1) ? 700 : 300;
  }
  out[66] = 300; out[67] = 1000;
}

inline uint32_t periodMs(bool channelB) { return channelB ? 180 : 120; }

struct PadIn {
  int joyX, joyY;                  // 0..4095, centre 2047
  bool up, down;                   // throttle buttons, held
  bool leftPressed, rightPressed;  // trim buttons, press edges
  uint32_t nowMs;
};

struct PadOut {
  uint8_t yaw, pitch, throttle, trim;   // 0..127; yaw, pitch and trim centre on 63
  bool exit;
};

class Pad {
 public:
  static constexpr int kCentre = 2047;
  static constexpr int kDeadzone = 200;
  static constexpr uint32_t kRepeatMs = 120;   // throttle step rate while a button is held
  static constexpr int kTrimStep = 2;

  int throttleStep = 4;
  int trim = 63;
  bool invertX = false, invertY = false;

  PadOut step(const PadIn& in) {
    if (in.up && in.down) { throttle_ = 0; upHeld_ = downHeld_ = false; return {63, 63, 0, (uint8_t)trim, true}; }

    if (due(in.up, upHeld_, upAtMs_, in.nowMs)) throttle_ = clamp(throttle_ + throttleStep);
    if (due(in.down, downHeld_, downAtMs_, in.nowMs)) throttle_ = clamp(throttle_ - throttleStep);
    if (in.leftPressed) trim = clamp(trim - kTrimStep);
    if (in.rightPressed) trim = clamp(trim + kTrimStep);

    int x = axis(in.joyX), y = axis(in.joyY);
    if (invertX) x = -x;
    if (invertY) y = -y;
    return {(uint8_t)(63 + x), (uint8_t)(63 + y), (uint8_t)throttle_, (uint8_t)trim, false};
  }

 private:
  static bool due(bool held, bool& was, uint32_t& at, uint32_t now) {
    if (!held) { was = false; return false; }
    if (was && (uint32_t)(now - at) < kRepeatMs) return false;
    was = true; at = now;
    return true;
  }
  static int axis(int raw) {
    int d = raw - kCentre;
    const int sign = d < 0 ? -1 : 1;
    d *= sign;
    if (d < kDeadzone) return 0;
    const int v = (d - kDeadzone) * 63 / (kCentre - kDeadzone);
    return sign * (v > 63 ? 63 : v);
  }
  static int clamp(int v) { return v > 127 ? 127 : v < 0 ? 0 : v; }

  int throttle_ = 0;
  bool upHeld_ = false, downHeld_ = false;
  uint32_t upAtMs_ = 0, downAtMs_ = 0;
};

}  // namespace heli
