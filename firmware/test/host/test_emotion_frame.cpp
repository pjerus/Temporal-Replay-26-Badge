#include "../../src/emotion/EmotionFrame.h"
#include <cassert>
#include <cstdio>
int main() {
  using namespace emotion;
  // roundtrip
  Frame f{1 /*happy*/, 204 /*~0.8*/, 200 /*20.0s*/, 1, 0};
  uint8_t buf[kFrameLen];
  assert(encode(f, buf) == kFrameLen);
  Frame g{};
  assert(decode(buf, kFrameLen, g));
  assert(g.mood == 1 && g.intensity == 204 && g.ttlDs == 200 && g.source == 1);
  // little-endian ttl matches python (<H): 200 -> 0xC8 0x00
  assert(buf[2] == 0xC8 && buf[3] == 0x00);
  // reject wrong length
  Frame h{};
  assert(!decode(buf, 2, h));
  // reject out-of-range mood
  uint8_t bad[kFrameLen] = {9, 0, 0, 0, 0, 0};
  assert(!decode(bad, kFrameLen, h));
  // clear flag decodes
  uint8_t clr[kFrameLen] = {0, 0, 0, 0, 0, kFlagClear};
  Frame c{};
  assert(decode(clr, kFrameLen, c));
  assert(c.flags & kFlagClear);
  printf("ok\n");
  return 0;
}
