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
  printf("ok\n");
  return 0;
}
