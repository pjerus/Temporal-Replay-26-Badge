#pragma once
// Joystick and buttons to tread speeds, for the on-badge Drive app.
// Pure logic, no hardware calls — host-tested in test/host/test_joy_pad.cpp.
#include <cstdint>

namespace drive {

struct PadIn {
  int joyX, joyY;           // 0..4095, centre 2047; larger X = right, larger Y = forward
  bool up, down;            // dash buttons, held
  bool leftPressed, rightPressed;  // quarter-turn buttons, press edges
  uint32_t nowMs;
};

struct PadOut {
  int8_t left, right;       // tenths of a speed step, -70..70
  bool exit;
};

class JoyPad {
 public:
  static constexpr int kCentre = 2047;
  static constexpr int kDeadzone = 200;
  static constexpr uint32_t kDashDelayMs = 150;  // so pressing both to exit does not lurch
  static constexpr uint32_t kTurnMs = 500;       // quarter turn on carpet at kTurnTenths
  static constexpr int8_t kTurnTenths = 40;

  bool invertY = false;

  PadOut step(const PadIn& in) {
    if (in.up && in.down) { turning_ = false; upHeld_ = downHeld_ = false; return {0, 0, true}; }

    if (in.leftPressed || in.rightPressed) {
      turning_ = true; turnStartMs_ = in.nowMs; turnDir_ = in.rightPressed ? 1 : -1;
    }
    if (turning_) {
      if ((uint32_t)(in.nowMs - turnStartMs_) < kTurnMs) {
        const int8_t t = (int8_t)(turnDir_ * kTurnTenths);
        return {t, (int8_t)-t, false};
      }
      turning_ = false;
    }

    if (dash(in.up, upHeld_, upSinceMs_, in.nowMs)) return {70, 70, false};
    if (dash(in.down, downHeld_, downSinceMs_, in.nowMs)) return {-70, -70, false};

    int y = axis(in.joyY), x = axis(in.joyX);
    if (invertY) y = -y;
    return {clamp(y + x), clamp(y - x), false};
  }

 private:
  static bool dash(bool held, bool& was, uint32_t& since, uint32_t now) {
    if (!held) { was = false; return false; }
    if (!was) { was = true; since = now; }
    return (uint32_t)(now - since) >= kDashDelayMs;
  }
  static int axis(int raw) {
    int d = raw - kCentre;
    const int sign = d < 0 ? -1 : 1;
    d *= sign;
    if (d < kDeadzone) return 0;
    const int v = (d - kDeadzone) * 70 / (kCentre - kDeadzone);
    return sign * (v > 70 ? 70 : v);
  }
  static int8_t clamp(int v) { return (int8_t)(v > 70 ? 70 : v < -70 ? -70 : v); }

  bool turning_ = false, upHeld_ = false, downHeld_ = false;
  int turnDir_ = 0;
  uint32_t turnStartMs_ = 0, upSinceMs_ = 0, downSinceMs_ = 0;
};

}  // namespace drive
