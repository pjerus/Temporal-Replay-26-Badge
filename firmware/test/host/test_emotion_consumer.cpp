#include "../../src/emotion/EmotionConsumer.h"
#include <cassert>
#include <cstdio>
int main() {
  EmotionConsumer c;
  assert(!c.activeAt(1000));
  assert(c.msLeftAt(1000) == 0);

  emotion::Frame happy{1, 204, 200 /*20.0s*/, 0, 0};
  c.apply(happy, 1000);
  assert(c.activeAt(1000));
  assert(c.mood() == 1);
  assert(c.msLeftAt(1000) == 20000);
  assert(c.activeAt(20000));        // still inside window
  assert(!c.activeAt(21001));       // expired by wall clock
  assert(c.msLeftAt(21001) == 0);

  // ttl=0 latches forever until cleared
  emotion::Frame latch{4, 255, 0, 0, 0};
  c.apply(latch, 5000);
  assert(c.activeAt(9999999));
  assert(c.msLeftAt(9999999) == UINT32_MAX);
  c.clear();
  assert(!c.activeAt(5001));

  // face-on-screen flag
  assert(!c.faceOnScreen());
  c.setFaceOnScreen(true);
  assert(c.faceOnScreen());

  printf("ok\n");
  return 0;
}
