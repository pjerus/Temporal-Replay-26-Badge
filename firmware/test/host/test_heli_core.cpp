#include "../../src/drive/HeliCore.h"
#include <cassert>
#include <cstdio>
using namespace heli;
static PadIn in(int x, int y, uint32_t now) { PadIn i{}; i.joyX = x; i.joyY = y; i.nowMs = now; return i; }
int main() {
  const int C = 2047;
  { // frame word: yaw, pitch, channel bit + throttle, trim
    assert(frameWord(63, 63, 0, 63, false) == 0x3F3F003Fu);
    assert(frameWord(63, 63, 40, 63, false) == 0x3F3F283Fu);
    assert(frameWord(0, 127, 127, 0, true) == 0x007FFF00u);
  }
  { // pairs: header, 32 bits MSB first, closing mark
    uint16_t p[kPairs * 2];
    encodePairs(0x80000001u, p);
    assert(p[0] == 2000 && p[1] == 2000);
    assert(p[2] == 300 && p[3] == 700);          // first bit is 1
    assert(p[4] == 300 && p[5] == 300);          // second bit is 0
    assert(p[64] == 300 && p[65] == 700);        // last bit is 1
    assert(p[66] == 300 && kPairs == 34);
  }
  { // starts at zero throttle, centred, and stays there with nothing pressed
    Pad p; PadOut o = p.step(in(C, C, 0));
    assert(o.throttle == 0 && o.yaw == 63 && o.pitch == 63 && o.trim == 63 && !o.exit);
  }
  { // throttle steps on press, repeats while held, and is clamped
    Pad p; p.throttleStep = 4;
    PadIn i = in(C, C, 0); i.up = true;
    assert(p.step(i).throttle == 4);
    i.nowMs = Pad::kRepeatMs - 1; assert(p.step(i).throttle == 4);
    i.nowMs = Pad::kRepeatMs; assert(p.step(i).throttle == 8);
    for (uint32_t t = 1; t < 100; t++) { i.nowMs = t * Pad::kRepeatMs + Pad::kRepeatMs; p.step(i); }
    assert(p.step(i).throttle == 127);
    PadIn d = in(C, C, 100000); d.down = true;
    assert(p.step(d).throttle == 123);
    for (uint32_t t = 1; t < 100; t++) { d.nowMs = 100000 + t * Pad::kRepeatMs; p.step(d); }
    assert(p.step(d).throttle == 0);
  }
  { // both throttle buttons together: exit with the rotors cut
    Pad p; PadIn i = in(C, C, 0); i.up = true; p.step(i);
    i.down = true; i.nowMs = 50; PadOut o = p.step(i);
    assert(o.exit && o.throttle == 0);
  }
  { // trim buttons nudge and clamp
    Pad p; p.trim = 63;
    PadIn i = in(C, C, 0); i.rightPressed = true; assert(p.step(i).trim == 63 + Pad::kTrimStep);
    PadIn l = in(C, C, 10); l.leftPressed = true; assert(p.step(l).trim == 63);
    p.trim = 1; assert(p.step(l).trim == 0);
    p.trim = 126; assert(p.step(i).trim == 127);
  }
  { // stick: sideways is yaw, forward/back is pitch, deadzone holds centre, flips work
    Pad p;
    PadOut o = p.step(in(4095, C, 0)); assert(o.yaw == 126 && o.pitch == 63);
    o = p.step(in(0, C, 0)); assert(o.yaw == 0);
    o = p.step(in(C, 4095, 0)); assert(o.pitch == 126 && o.yaw == 63);
    o = p.step(in(C + 150, C - 150, 0)); assert(o.yaw == 63 && o.pitch == 63);
    p.invertY = true; o = p.step(in(C, 4095, 0)); assert(o.pitch == 0);
    p.invertX = true; o = p.step(in(4095, C, 0)); assert(o.yaw == 0);
  }
  std::puts("heli_core ok");
}
