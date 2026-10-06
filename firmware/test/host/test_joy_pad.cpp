#include "../../src/drive/JoyPad.h"
#include <cassert>
#include <cstdio>
using namespace drive;
static PadIn in(int x, int y, uint32_t now) { PadIn i{}; i.joyX = x; i.joyY = y; i.nowMs = now; return i; }
int main() {
  const int C = 2047;
  { // centred stick, and anything inside the deadzone, is stop
    JoyPad p; PadOut o = p.step(in(C, C, 0)); assert(o.left == 0 && o.right == 0 && !o.exit);
    o = p.step(in(C + 150, C - 150, 10)); assert(o.left == 0 && o.right == 0);
  }
  { // full forward, full back, half forward
    JoyPad p;
    PadOut o = p.step(in(C, 4095, 0)); assert(o.left == 70 && o.right == 70);
    o = p.step(in(C, 0, 0)); assert(o.left == -70 && o.right == -70);
    o = p.step(in(C, C + 1100, 0)); assert(o.left > 25 && o.left < 45 && o.left == o.right);
  }
  { // sideways with no forward spins on the spot; stick right = turn right
    JoyPad p; PadOut o = p.step(in(4095, C, 0)); assert(o.left == 70 && o.right == -70);
    o = p.step(in(0, C, 0)); assert(o.left == -70 && o.right == 70);
  }
  { // forward and right curves right, never past the limits
    JoyPad p; PadOut o = p.step(in(4095, 4095, 0)); assert(o.left == 70 && o.right == 0);
    o = p.step(in(C + 600, 4095, 0)); assert(o.left == 70 && o.right > 0 && o.right < 70);
  }
  { // dash buttons act after a short hold, and beat the stick
    JoyPad p; PadIn i = in(C, 0, 0); i.up = true;
    PadOut o = p.step(i); assert(o.left == -70);                 // not yet: stick still rules
    i.nowMs = JoyPad::kDashDelayMs; o = p.step(i); assert(o.left == 70 && o.right == 70);
    PadIn d = in(C, C, 1000); d.down = true; p.step(d);
    d.nowMs = 1000 + JoyPad::kDashDelayMs; o = p.step(d); assert(o.left == -70 && o.right == -70);
  }
  { // both dash buttons together: exit, and no movement on the way
    JoyPad p; PadIn i = in(C, C, 0); i.up = true; PadOut o = p.step(i); assert(o.left == 0 && !o.exit);
    i.nowMs = 60; i.down = true; o = p.step(i); assert(o.exit && o.left == 0 && o.right == 0);
  }
  { // quarter turn: runs for kTurnMs whatever the stick does, then hands back
    JoyPad p; PadIn i = in(C, C, 0); i.rightPressed = true;
    PadOut o = p.step(i); assert(o.left == JoyPad::kTurnTenths && o.right == -JoyPad::kTurnTenths);
    o = p.step(in(C, 4095, JoyPad::kTurnMs - 1)); assert(o.left == JoyPad::kTurnTenths && o.right == -JoyPad::kTurnTenths);
    o = p.step(in(C, C, JoyPad::kTurnMs)); assert(o.left == 0 && o.right == 0);
    PadIn l = in(C, C, 2000); l.leftPressed = true;
    o = p.step(l); assert(o.left == -JoyPad::kTurnTenths && o.right == JoyPad::kTurnTenths);
  }
  { // exit cancels a turn in progress
    JoyPad p; PadIn i = in(C, C, 0); i.leftPressed = true; p.step(i);
    PadIn e = in(C, C, 100); e.up = e.down = true; PadOut o = p.step(e); assert(o.exit && o.left == 0);
  }
  { // invertY flips forward and back only
    JoyPad p; p.invertY = true; PadOut o = p.step(in(C, 4095, 0)); assert(o.left == -70 && o.right == -70);
    o = p.step(in(4095, C, 0)); assert(o.left == 70 && o.right == -70);
  }
  std::puts("joy_pad ok");
}
