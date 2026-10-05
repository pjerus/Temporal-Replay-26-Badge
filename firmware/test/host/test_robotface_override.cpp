#include "../../src/emotion/EmotionConsumer.h"
#include "../../src/screens/RobotFaceOverride.h"  // declares chooseOverride
#include <cassert>
#include <cstdio>
int main() {
  EmotionConsumer c;
  uint8_t m; float in;
  assert(!chooseOverride(c, 1000, m, in));  // nothing injected
  emotion::Frame surprised{5, 230, 100 /*10s*/, 0, 0};
  c.apply(surprised, 1000);
  assert(chooseOverride(c, 2000, m, in));
  assert(m == 5);
  assert(in > 0.89f && in < 0.91f);
  assert(!chooseOverride(c, 20000, m, in));  // expired -> autonomous

  // A corrupt/hostile frame with an out-of-range mood must NOT drive the
  // face (it would later index kMouths[] out of bounds).
  emotion::Frame bogus{9, 255, 100, 0, 0};
  c.apply(bogus, 100000);
  uint8_t m2 = 42; float in2 = -1.f;
  assert(!chooseOverride(c, 100100, m2, in2));

  printf("ok\n");
  return 0;
}
