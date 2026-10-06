#include "../../src/drive/DriveCore.h"
#include <cassert>
#include <cstdio>
#include <cstring>
using namespace drive;
static const uint8_t S[8] = {1, 2, 3, 4, 5, 6, 7, 8};
static const uint32_t ROOMY = 9000;
static void cmd(Core& c, int l, int r, int ttl, uint32_t now) {
  uint8_t b[kCmdLen];
  memcpy(b, S, 8); b[8] = (uint8_t)(int8_t)l; b[9] = (uint8_t)(int8_t)r; b[10] = (uint8_t)ttl;
  c.onWrite(b, kCmdLen, S, now);
}
static int countSends(Core& c, uint32_t from, uint32_t to, uint32_t free = ROOMY) {
  int n = 0;
  for (uint32_t t = from; t < to; t += 5) if (c.tick(t, free).send) n++;
  return n;
}
int main() {
  uint8_t st[kStateLen];
  { // idle: nothing sent
    Core c; assert(countSends(c, 0, 1000) == 0); assert(!c.driving()); assert(c.burstDone()); }
  { // a command drives, one frame per 90 ms, then expires into a 4-frame stop
    Core c; cmd(c, 40, 40, 5, 1000);
    Out o = c.tick(1000, ROOMY);
    assert(o.send && o.leftTenths == 40 && o.rightTenths == 40 && c.driving());
    assert(countSends(c, 1005, 1500) == 5);          // 1090,1180,1270,1360,1450
    int stops = 0;
    for (uint32_t t = 1500; t < 2500; t += 5) { Out s = c.tick(t, ROOMY);
      if (s.send) { assert(s.leftTenths == 0 && s.rightTenths == 0); stops++; } }
    assert(stops == kStopFrames); assert(!c.driving()); assert(c.burstDone());
    assert(countSends(c, 2500, 4000) == 0);          // then silence
  }
  { // replaces_running_command
    Core c; cmd(c, 40, 40, 10, 0); c.tick(0, ROOMY);
    cmd(c, -30, 20, 2, 100);
    Out o = c.tick(100, ROOMY); assert(o.send && o.leftTenths == -30 && o.rightTenths == 20);
    assert(c.driving()); c.tick(299, ROOMY); assert(c.driving());
    c.tick(300, ROOMY); assert(!c.driving());        // new 0.2 s timer, not the old 1 s
  }
  { // 0/0 stops at once
    Core c; cmd(c, 40, 40, 10, 0); c.tick(0, ROOMY); cmd(c, 0, 0, 1, 50);
    Out o = c.tick(50, ROOMY); assert(o.send && o.leftTenths == 0); assert(!c.driving()); }
  { // rejected input leaves the running move alone and raises the flag
    Core c; cmd(c, 40, 40, 10, 0); c.tick(0, ROOMY);
    uint8_t bad[kCmdLen] = {9, 9, 9, 9, 9, 9, 9, 9, 10, 10, 5};
    c.onWrite(bad, kCmdLen, S, 10);                  // wrong secret
    assert(c.driving()); c.composeState(st, 10, true, 50, ROOMY, ROOMY); assert(st[0] & 0x08);
    cmd(c, 71, 0, 5, 20);  assert(c.driving());      // speed out of range
    cmd(c, 10, -71, 5, 20);
    cmd(c, 10, 10, 0, 20);                           // ttl 0
    cmd(c, 10, 10, 11, 20);                          // ttl too long
    uint8_t shortb[5] = {0}; c.onWrite(shortb, 5, S, 20);
    c.onWrite(nullptr, kCmdLen, S, 20);
    c.composeState(st, 20, true, 50, ROOMY, ROOMY);
    assert((int8_t)st[1] == 40 && (int8_t)st[2] == 40 && st[7] == 1);
    cmd(c, 10, 10, 5, 30);                           // a good one clears the flag
    c.composeState(st, 30, true, 50, ROOMY, ROOMY); assert(!(st[0] & 0x08) && st[7] == 2);
  }
  { // disconnect_sends_stop_burst
    Core c; cmd(c, 40, 40, 10, 0); c.tick(0, ROOMY); c.onDisconnect();
    assert(!c.driving()); assert(!c.burstDone());
    assert(countSends(c, 5, 1000) == kStopFrames); assert(c.burstDone());
  }
  { // refused below the floor: flag set, only coast frames ever go out
    Core c; cmd(c, 40, 40, 10, 0);
    for (uint32_t t = 0; t < 500; t += 5) { Out o = c.tick(t, kFloorBytes - 1);
      if (o.send) assert(o.leftTenths == 0 && o.rightTenths == 0); }
    assert(!c.driving());
    c.composeState(st, 500, true, 50, kFloorBytes - 1, kFloorBytes - 1); assert(st[0] & 0x04);
  }
  { // floor_stops_running_move
    Core c; cmd(c, 40, 40, 10, 0); c.tick(0, ROOMY); assert(c.driving());
    Out o = c.tick(90, kFloorBytes - 1);
    assert(!c.driving()); assert(o.send && o.leftTenths == 0);
  }
  { // expiry_survives_wrap
    Core c; const uint32_t near = 0xFFFFFF00u; cmd(c, 40, 40, 10, near); c.tick(near, ROOMY);
    c.tick(near + 500, ROOMY); assert(c.driving());       // wrapped past zero, still valid
    c.tick(near + 1000, ROOMY); assert(!c.driving());
  }
  { // status layout
    Core c; cmd(c, -25, 33, 10, 0); c.tick(0, ROOMY);
    c.composeState(st, 400, true, 87, 9216, 8192);
    assert(st[0] == 0x03); assert((int8_t)st[1] == -25 && (int8_t)st[2] == 33);
    assert(st[3] == 6); assert(st[4] == 87); assert(st[5] == 36 && st[6] == 32); assert(st[7] == 1);
    c.composeState(st, 400, false, 87, 400000, 400000); assert(st[5] == 255 && st[6] == 255);
  }
  { // stale command: lifetime runs from arrival, so one applied late never drives
    Core c; cmd(c, 40, 40, 6, 0);
    for (uint32_t t = 1000; t < 1500; t += 5) { Out o = c.tick(t, ROOMY);
      if (o.send) assert(o.leftTenths == 0 && o.rightTenths == 0); }
    assert(!c.driving());
  }
  { // IrLease: hold after last need, then a lockout before IR may be asked for again
    IrLease l;
    assert(l.want(true, 0));
    assert(l.want(false, 100));                    // held so the stop burst gets out
    assert(l.want(false, IrLease::kHoldMs - 1));
    assert(!l.want(false, IrLease::kHoldMs));      // released here
    assert(!l.want(true, IrLease::kHoldMs + 10));  // teardown may be running
    assert(l.want(true, IrLease::kHoldMs + IrLease::kLockoutMs));
    IrLease w; const uint32_t near = 0xFFFFFFF0u;  // wrap-safe
    assert(w.want(true, near)); assert(w.want(false, near + 100)); assert(!w.want(false, near + IrLease::kHoldMs));
  }
  std::puts("drive_core ok");
}