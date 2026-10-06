#pragma once
// LEGO Power Functions "combo PWM" frames for a two-tread base.
// Pure logic, no hardware calls — host-tested in test/host/test_pf_treads.cpp.
// Output A = left tread, output B = right tread (measured on Pat's base).
#include <cstddef>
#include <cstdint>

namespace pftreads {

struct Tuning {
  uint8_t channel;      // 0..3 = LEGO channel 1..4
  int16_t leftTrimPct;  // 100 = none; 109 = left runs 9% faster
  bool flipRight;       // motors face opposite ways
};

constexpr size_t kPairs = 18;  // start + 16 bits + stop

// Speed -7..7 to the 4-bit PWM code: 0 coast, 1..7 one way, 9..15 the other.
// On this base the "9..15" direction is tread-forward.
inline uint8_t pwmCode(int speed) {
  if (speed == 0) return 0;
  return (uint8_t)(speed > 0 ? 16 - speed : -speed);
}

inline uint16_t frameBits(int left, int right, const Tuning& t) {
  const uint8_t n1 = 0x4 | (t.channel & 0x3);              // escape=1: combo PWM
  const uint8_t n2 = pwmCode(t.flipRight ? -right : right); // output B
  const uint8_t n3 = pwmCode(left);                         // output A
  const uint8_t n4 = 0xF ^ n1 ^ n2 ^ n3;
  return (uint16_t)((n1 << 12) | (n2 << 8) | (n3 << 4) | n4);
}

inline void encodePairs(uint16_t bits, uint16_t out[kPairs * 2]) {
  size_t i = 0;
  out[i++] = 158; out[i++] = 1026;
  for (int b = 15; b >= 0; b--) {
    out[i++] = 158;
    out[i++] = ((bits >> b) & 1) ? 553 : 263;
  }
  out[i++] = 158; out[i++] = 1026;
}

// A fractional speed alternates between the two nearest whole steps so the
// average over many frames equals the asked speed. Works in thousandths.
class Dither {
 public:
  void reset() { accL_ = accR_ = 0; }
  void next(int8_t leftTenths, int8_t rightTenths, const Tuning& t,
            int& left, int& right) {
    left = step(accL_, (int32_t)leftTenths * t.leftTrimPct);
    right = step(accR_, (int32_t)rightTenths * 100);
  }

 private:
  static int step(int32_t& acc, int32_t milli) {
    if (milli > 7000) milli = 7000;
    if (milli < -7000) milli = -7000;
    acc += milli;
    const int whole = (int)(acc / 1000);  // truncates toward zero
    acc -= (int32_t)whole * 1000;
    return whole;
  }
  int32_t accL_ = 0, accR_ = 0;
};

}  // namespace pftreads