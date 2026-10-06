# Tread Drive over Bluetooth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The spare badge, riding on the tank base with no cable, accepts "left speed, right speed, valid-for" over Bluetooth and turns it into LEGO Power Functions infrared, stopping whenever commands stop.

**Architecture:** Two pure C++ units with no hardware calls (`PfTreads` makes infrared frames, `DriveCore` holds the command, timer, stop rules and status), tested on the Mac. A thin firmware shell (`DriveBleService`) connects them to the existing Bluetooth server and the existing infrared task. Everything is compiled only into the `echo-drive` build.

**Tech Stack:** Arduino C++17 on ESP32-S3 (PlatformIO, `~/.platformio/penv/bin/pio`), Arduino BLE API (NimBLE underneath), host tests with Apple clang (`c++ -std=c++17`), Mac test controller in Python with `bleak` run through `uv run --with bleak`.

**Spec:** `docs/superpowers/specs/tread-drive-ble-design.html` (revision 2)

## Global Constraints

- All new firmware code is inside `#ifdef BADGE_ENABLE_DRIVE_BLE`. The `echo`, `echo-dev` and `echo-ir` builds must compile to the same behaviour as before. The face badge is never flashed.
- Only the spare badge is flashed (USB port found with `ls /dev/cu.usbmodem*`; it has been `1101` and `101`). Kill serial readers first.
- Always `~/.platformio/penv/bin/pio`, never the `pio` shim.
- Command frame is exactly 11 bytes: secret[8], left tenths (int8, −70..70), right tenths (int8, −70..70), valid-for in tenths of a second (uint8, 1..10).
- Status is exactly 8 bytes, layout in Task 2.
- Memory floor: 6144 bytes of free internal heap. Below it, a non-zero drive command is refused.
- Infrared frames go out every 90 ms while driving; a stop is 4 coast frames, then silence.
- Nothing is allocated after start-up: no `new`, `malloc`, `String`, `std::vector` or task creation in the tick or the callbacks.
- Tuned defaults (measured 2026-10-06): LEGO channel 1, left trim 109 %, right side flipped, transmit power 50 %.
- Service UUID `80a239a9-d8c0-4b45-82eb-41fd7207df9b`, command characteristic `98b99101-ab97-48b5-a9c9-e666e456806c`, status characteristic `1350f2e6-4bdf-4459-a813-4afaf1a8ffee`.
- Bluetooth name on this build: `Rocky IR Tread`.
- Never print the shared secret in logs or test output.
- Commit after each task with the trailers in the session's attribution note. Do not push.

**One deviation from the spec, decided here:** the firmware's settings system holds numbers only, so the Bluetooth name is a build setting in `platformio.ini` (`-DBADGE_BLE_NAME`), not a line in `settings.txt`. The four tuning numbers are in `settings.txt` as the spec says.

## Review Focus

1. **A command arrives while a previous one is still valid** — the new one replaces it at once, including its timer. (Task 2 test `replaces_running_command`.)
2. **`millis()` wraps after 49 days** — expiry must use unsigned subtraction, not `now > deadline`. (Task 2 test `expiry_survives_wrap`.)
3. **Controller disconnects mid-move** — the stop burst is still sent even though infrared is about to be switched off. (Task 2 test `disconnect_sends_stop_burst`; Task 4 keeps infrared up until `burstDone()`.)
4. **Trim pushes a speed past 7** (7.0 × 1.09 = 7.63) — clamps to 7, never wraps into the reverse codes. (Task 1 test `trim_clamps_at_seven`.)
5. **Memory drops below the floor during a move** — the move is stopped, not just the next one refused. (Task 2 test `floor_stops_running_move`.)

---

### Task 0: Commit the memory-proof changes

The working tree already holds the send-only infrared option and the `echo-drive` env from the proof Pat watched.

**Files:**
- Already modified: `firmware/src/ir/BadgeIR.cpp`, `firmware/platformio.ini`

- [ ] **Step 1: Confirm the diff is only those two changes**

Run: `cd /Users/pat/ai-dev/pi-arduino && git diff --stat -- firmware/src/ir/BadgeIR.cpp firmware/platformio.ini`
Expected: two files; `BadgeIR.cpp` adds two `BADGE_IR_TX_ONLY` blocks; `platformio.ini` adds `[env:echo-ir]`-style block `[env:echo-drive]`.

- [ ] **Step 2: Commit only those two files**

```bash
git add firmware/src/ir/BadgeIR.cpp firmware/platformio.ini
git commit -m "firmware: echo-drive build with send-only IR beside emotion BLE"
```
Leave `firmware/initial_filesystem/manifest.json`, `arduino-cli.yaml` and `backups/` alone.

---

### Task 1: PfTreads — speeds to infrared frames

**Files:**
- Create: `firmware/src/drive/PfTreads.h`
- Test: `firmware/test/host/test_pf_treads.cpp`

**Interfaces:**
- Produces:
  - `struct pftreads::Tuning { uint8_t channel; int16_t leftTrimPct; bool flipRight; };` (`channel` is 0..3 for LEGO channels 1..4)
  - `uint16_t pftreads::frameBits(int left, int right, const Tuning& t);` whole speeds −7..7
  - `constexpr size_t pftreads::kPairs = 18;`
  - `void pftreads::encodePairs(uint16_t bits, uint16_t out[36]);` mark/space microseconds, in the order `irRawSend` takes
  - `class pftreads::Dither { void reset(); void next(int8_t leftTenths, int8_t rightTenths, const Tuning& t, int& left, int& right); };`

- [ ] **Step 1: Write the failing test**

`firmware/test/host/test_pf_treads.cpp`:
```cpp
#include "../../src/drive/PfTreads.h"
#include <cassert>
#include <cstdio>
int main() {
  using namespace pftreads;
  const Tuning t{0, 109, true};
  // Reference values from the tuned scripts/pf_ir/ir_drive.py.
  assert(frameBits(0, 0, t) == 0x400B);    // coast both
  assert(frameBits(3, 3, t) == 0x43D5);    // forward: A=16-3, B flipped=3
  assert(frameBits(-4, 4, t) == 0x444B);   // spin left
  const Tuning ch2{1, 109, true};
  assert(frameBits(7, 7, ch2) == 0x5794);
  const Tuning noflip{0, 100, false};
  assert(frameBits(3, 3, noflip) == 0x4DDB);

  // encodePairs: start, 16 bits MSB first, stop
  uint16_t p[36];
  encodePairs(0x400B, p);
  assert(p[0] == 158 && p[1] == 1026);          // start
  assert(p[2] == 158 && p[3] == 263);           // bit15 = 0
  assert(p[4] == 158 && p[5] == 553);           // bit14 = 1
  assert(p[34] == 158 && p[35] == 1026);        // stop
  assert(p[33] == 553);                         // bit0 = 1

  // Dither: 4.0 with 109% trim averages 4.36 on the left, 4.0 on the right
  Dither d; d.reset();
  int sumL = 0, sumR = 0, l, r;
  for (int i = 0; i < 100; i++) { d.next(40, 40, t, l, r); sumL += l; sumR += r;
    assert(l == 4 || l == 5); assert(r == 4); }
  assert(sumL == 436 && sumR == 400);

  // negative speeds mirror
  d.reset(); sumL = 0;
  for (int i = 0; i < 100; i++) { d.next(-40, -40, t, l, r); sumL += l; assert(r == -4); }
  assert(sumL == -436);

  // trim_clamps_at_seven: 7.0 * 1.09 never exceeds 7
  d.reset();
  for (int i = 0; i < 50; i++) { d.next(70, 70, t, l, r); assert(l == 7 && r == 7); }

  // zero stays zero
  d.reset(); d.next(0, 0, t, l, r); assert(l == 0 && r == 0);
  std::puts("pf_treads ok");
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd /Users/pat/ai-dev/pi-arduino/firmware && c++ -std=c++17 -o /tmp/t_pf test/host/test_pf_treads.cpp`
Expected: FAIL, `PfTreads.h` file not found.

- [ ] **Step 3: Write the implementation**

`firmware/src/drive/PfTreads.h`:
```cpp
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
```

- [ ] **Step 4: Run the test**

Run: `c++ -std=c++17 -o /tmp/t_pf test/host/test_pf_treads.cpp && /tmp/t_pf`
Expected: `pf_treads ok`

- [ ] **Step 5: Commit**

```bash
git add firmware/src/drive/PfTreads.h firmware/test/host/test_pf_treads.cpp
git commit -m "firmware: PfTreads, tread speeds to Power Functions IR frames"
```

---

### Task 2: DriveCore — command, timer, stop rules, status

**Files:**
- Create: `firmware/src/drive/DriveCore.h`
- Test: `firmware/test/host/test_drive_core.cpp`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces (all in `namespace drive`):
  - `constexpr size_t kCmdLen = 11; constexpr size_t kStateLen = 8; constexpr uint32_t kFloorBytes = 6144; constexpr uint32_t kFrameMs = 90; constexpr uint8_t kStopFrames = 4;`
  - `struct Out { bool send; int8_t leftTenths; int8_t rightTenths; };`
  - `class Core` with:
    - `void onWrite(const uint8_t* data, size_t len, const uint8_t secret[8], uint32_t nowMs);`
    - `void onDisconnect();`
    - `Out tick(uint32_t nowMs, uint32_t freeBytes);` — call every loop; `send` is true at most once per 90 ms
    - `bool driving() const; bool burstDone() const;`
    - `void composeState(uint8_t out[8], uint32_t nowMs, bool irReady, uint8_t batteryPct, uint32_t freeBytes, uint32_t minFreeBytes) const;`
- Status bytes: `[0]` flags (bit0 driving, bit1 infrared ready, bit2 refused for low memory, bit3 last command rejected), `[1]` left tenths, `[2]` right tenths, `[3]` time left in tenths of a second, `[4]` battery %, `[5]` free heap in quarter-KB (capped 255), `[6]` lowest free heap in quarter-KB (capped 255), `[7]` accepted-command count mod 256.

- [ ] **Step 1: Write the failing test**

`firmware/test/host/test_drive_core.cpp`:
```cpp
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
  std::puts("drive_core ok");
}
```

- [ ] **Step 2: Run it to see it fail**

Run: `c++ -std=c++17 -o /tmp/t_dc test/host/test_drive_core.cpp`
Expected: FAIL, `DriveCore.h` file not found.

- [ ] **Step 3: Write the implementation**

`firmware/src/drive/DriveCore.h`:
```cpp
#pragma once
// Tread-drive command state: what to send, for how long, and when to stop.
// Pure logic, no hardware calls — host-tested in test/host/test_drive_core.cpp.
// Rule: a stop always wins, and silence means stop.
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace drive {

constexpr size_t kCmdLen = 11;        // secret[8] left right ttl
constexpr size_t kStateLen = 8;
constexpr uint32_t kFloorBytes = 6144;
constexpr uint32_t kFrameMs = 90;
constexpr uint8_t kStopFrames = 4;

struct Out {
  bool send;
  int8_t leftTenths;
  int8_t rightTenths;
};

class Core {
 public:
  void onWrite(const uint8_t* data, size_t len, const uint8_t secret[8],
               uint32_t nowMs) {
    if (!data || len != kCmdLen || memcmp(data, secret, 8) != 0) { rejected_ = true; return; }
    const int8_t l = (int8_t)data[8], r = (int8_t)data[9];
    const uint8_t ttl = data[10];
    if (l < -70 || l > 70 || r < -70 || r > 70 || ttl < 1 || ttl > 10) { rejected_ = true; return; }
    rejected_ = false;
    accepted_++;
    if (l == 0 && r == 0) { stop(); return; }
    left_ = l; right_ = r;
    startMs_ = nowMs; ttlMs_ = (uint32_t)ttl * 100;
    driving_ = true; fresh_ = true; stopsLeft_ = 0;
  }

  void onDisconnect() { if (driving_ || stopsLeft_ == 0) stop(); }

  Out tick(uint32_t nowMs, uint32_t freeBytes) {
    if (driving_ && freeBytes < kFloorBytes) { lowMem_ = true; stop(); }
    else if (freeBytes >= kFloorBytes) lowMem_ = false;
    if (driving_ && (uint32_t)(nowMs - startMs_) >= ttlMs_) stop();

    const bool due = fresh_ || (uint32_t)(nowMs - lastSendMs_) >= kFrameMs;
    if (!due) return {false, 0, 0};
    if (driving_) {
      fresh_ = false; lastSendMs_ = nowMs;
      return {true, left_, right_};
    }
    if (stopsLeft_ > 0) {
      fresh_ = false; lastSendMs_ = nowMs; stopsLeft_--;
      return {true, 0, 0};
    }
    return {false, 0, 0};
  }

  bool driving() const { return driving_; }
  bool burstDone() const { return !driving_ && stopsLeft_ == 0; }

  void composeState(uint8_t out[kStateLen], uint32_t nowMs, bool irReady,
                    uint8_t batteryPct, uint32_t freeBytes,
                    uint32_t minFreeBytes) const {
    uint8_t flags = 0;
    if (driving_) flags |= 0x01;
    if (irReady) flags |= 0x02;
    if (lowMem_) flags |= 0x04;
    if (rejected_) flags |= 0x08;
    uint32_t leftMs = 0;
    if (driving_) {
      const uint32_t used = (uint32_t)(nowMs - startMs_);
      leftMs = used < ttlMs_ ? ttlMs_ - used : 0;
    }
    out[0] = flags;
    out[1] = (uint8_t)(driving_ ? left_ : 0);
    out[2] = (uint8_t)(driving_ ? right_ : 0);
    out[3] = (uint8_t)(leftMs / 100);
    out[4] = batteryPct;
    out[5] = quarterKb(freeBytes);
    out[6] = quarterKb(minFreeBytes);
    out[7] = accepted_;
  }

 private:
  static uint8_t quarterKb(uint32_t bytes) {
    const uint32_t q = bytes / 256;
    return q > 255 ? 255 : (uint8_t)q;
  }
  void stop() {
    driving_ = false; left_ = right_ = 0;
    stopsLeft_ = kStopFrames; fresh_ = true;
  }

  bool driving_ = false, fresh_ = false, rejected_ = false, lowMem_ = false;
  int8_t left_ = 0, right_ = 0;
  uint8_t stopsLeft_ = 0, accepted_ = 0;
  uint32_t startMs_ = 0, ttlMs_ = 0, lastSendMs_ = 0;
};

}  // namespace drive
```

A non-zero command that arrives below the floor is taken in by `onWrite` and stopped by the very next `tick`, which raises the refused flag and sends only the stop burst.

- [ ] **Step 4: Run the test**

Run: `c++ -std=c++17 -o /tmp/t_dc test/host/test_drive_core.cpp && /tmp/t_dc`
Expected: `drive_core ok`. If an assertion fails, fix the implementation, not the test.

- [ ] **Step 5: Run all host tests**

Run: `for f in test/host/test_*.cpp; do c++ -std=c++17 -o /tmp/t_h "$f" && /tmp/t_h || echo "FAIL $f"; done`
Expected: no `FAIL` lines.

- [ ] **Step 6: Commit**

```bash
git add firmware/src/drive/DriveCore.h firmware/test/host/test_drive_core.cpp
git commit -m "firmware: DriveCore, tread command timer and stop rules"
```

---

### Task 3: Tread settings and the Bluetooth name

**Files:**
- Modify: `firmware/src/infra/BadgeConfig.h` (enum `SettingIndex`, after the last existing entry)
- Modify: `firmware/src/infra/BadgeConfig.cpp` (`kDefs` table end, near line 131; settings-file writer, near line 1143)
- Modify: `firmware/platformio.ini` (`[env:echo-drive]`)
- Modify: `firmware/src/main.cpp:495`

**Interfaces:**
- Produces: `kTreadChannel`, `kTreadTrimPct`, `kTreadFlipRight`, `kTreadIrPowerPct` in `SettingIndex` (only when `BADGE_ENABLE_DRIVE_BLE`), read with `badgeConfig.get(index)`; macro `BADGE_BLE_NAME`.

- [ ] **Step 1: Add the enum entries**

At the very end of `enum SettingIndex` in `BadgeConfig.h`, after the last existing entry and before the closing brace:
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
  // Tread drive (Power Functions IR). Tuned on Pat's tank base 2026-10-06.
  kTreadChannel,     // LEGO channel 1..4
  kTreadTrimPct,     // left tread speed, percent of asked speed
  kTreadFlipRight,   // 1 = right motor faces the other way
  kTreadIrPowerPct,  // IR carrier duty while driving
#endif
```

- [ ] **Step 2: Add the table rows**

At the end of `Config::kDefs` in `BadgeConfig.cpp`, after the `creds_py` row. The enum order and the table order must match exactly.
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
     {"tr_chan",     "Tread Chan",   1,    1,        4,      1},
     {"tr_trim",     "Tread Trim %", 109,  50,     200,      1},
     {"tr_flip",     "Tread FlipR",  1,    0,        1,      1},
     {"tr_ir_pw",    "Tread IR %",   50,   1,       50,      1},
#endif
```
Check: if the enum has entries after `kCredsPy` that the table lists in another position, place both additions last in their lists. `kMaxSettings` is 64; the existing `static_assert` will fail the build if that is exceeded.

- [ ] **Step 3: Write them to the settings file**

In the settings-file writer in `BadgeConfig.cpp`, directly after the `log_imu` line:
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
  pos += snprintf(buf + pos, room(), "\ntr_chan  = %ld;       # LEGO IR channel 1..4\n",
      (long)values_[kTreadChannel]);
  pos += snprintf(buf + pos, room(), "tr_trim  = %ld;       # left tread speed, %% of asked (109 = 9%% faster)\n",
      (long)values_[kTreadTrimPct]);
  pos += snprintf(buf + pos, room(), "tr_flip  = %ld;       # 1 = right motor faces the other way\n",
      (long)values_[kTreadFlipRight]);
  pos += snprintf(buf + pos, room(), "tr_ir_pw = %ld;       # IR transmit power while driving, 1..50\n",
      (long)values_[kTreadIrPowerPct]);
#endif
```

- [ ] **Step 4: Build flags and name**

Replace the `[env:echo-drive]` `build_flags` block in `platformio.ini` with:
```ini
build_flags =
    ${env:echo-dev.build_flags}
    -DBADGE_IR_TX_ONLY
    -DBADGE_ENABLE_DRIVE_BLE
    '-DBADGE_BLE_NAME="Rocky IR Tread"'
```
In `main.cpp`, above the `#ifdef BADGE_ENABLE_EMOTION_BLE` block at line ~489:
```cpp
#ifndef BADGE_BLE_NAME
#define BADGE_BLE_NAME "TemporalBadge"
#endif
```
and change `emotionBleBegin(g_emotion, kEmotionSecret, "TemporalBadge");` to use `BADGE_BLE_NAME`.

- [ ] **Step 5: Build both variants**

Run: `cd firmware && ~/.platformio/penv/bin/pio run -e echo-drive 2>&1 | tail -3 && ~/.platformio/penv/bin/pio run -e echo-dev 2>&1 | tail -3`
Expected: `SUCCESS` twice.

- [ ] **Step 6: Commit**

```bash
git add firmware/src/infra/BadgeConfig.h firmware/src/infra/BadgeConfig.cpp firmware/platformio.ini firmware/src/main.cpp
git commit -m "firmware: tread tuning settings and a build-set BLE name"
```

---

### Task 4: DriveBleService — wire it to Bluetooth and infrared

**Files:**
- Create: `firmware/src/drive/DriveBleService.h`, `firmware/src/drive/DriveBleService.cpp`
- Modify: `firmware/src/emotion/EmotionBleService.h`, `firmware/src/emotion/EmotionBleService.cpp` (extension hook)
- Modify: `firmware/src/ir/BadgeIR.h`, `firmware/src/ir/BadgeIR.cpp` (`driveIrWanted`)
- Modify: `firmware/src/main.cpp` (begin + tick)
- Modify: `firmware/platformio.ini` (`build_src_filter` — `base` already includes `+<*>`, so `src/drive/` is compiled; confirm, no change expected)

**Interfaces:**
- Consumes: `pftreads::*` (Task 1), `drive::Core` (Task 2), the four settings (Task 3), `irRawSend`, `irSetMode`, `irGetMode`, `irSetTxPower` from `ir/BadgeIR.h`.
- Produces: `void driveBleTick(uint8_t batteryPct);`, `const EmotionBleExtension* driveBleExtension(const uint8_t secret[8]);`, `bool driveBleConnected();`, `void driveBleStatusLine(char* buf, size_t n);`

Why the hook: the Bluetooth table of services is fixed when advertising first starts, and `emotionBleBegin` owns the server, its callbacks and that start. The drive service must be added inside it, before advertising.

- [ ] **Step 1: Add the extension hook to the emotion service**

`EmotionBleService.h` — add above the `emotionBleBegin` declaration, and add the last parameter:
```cpp
class BLEServer;
// Lets one more service ride on the same BLE server. addServices runs
// after the emotion service is created and before advertising starts.
// onConnect / onDisconnect run on the BLE host task: keep them tiny.
struct EmotionBleExtension {
  void (*addServices)(BLEServer* server);
  void (*onConnect)();
  void (*onDisconnect)();
};
void emotionBleBegin(EmotionConsumer& consumer, const uint8_t secret[8],
                     const char* advName,
                     const EmotionBleExtension* ext = nullptr);
```
(Replace the existing `emotionBleBegin` declaration with this one.)

`EmotionBleService.cpp`:
- add `const EmotionBleExtension* s_ext = nullptr;` beside `s_consumer`;
- in `ServerCb` add `void onConnect(BLEServer* s) override { (void)s; if (s_ext && s_ext->onConnect) s_ext->onConnect(); }` and, as the first line of `onDisconnect`, `if (s_ext && s_ext->onDisconnect) s_ext->onDisconnect();`
- change the definition's signature to match, store `s_ext = ext;` first, and insert `if (s_ext && s_ext->addServices) s_ext->addServices(server);` directly after `svc->start();`.

- [ ] **Step 2: Let the drive service keep infrared up**

`BadgeIR.h`, beside `extern volatile bool pythonIrListening;`:
```cpp
extern volatile bool      driveIrWanted;   // true while the tread-drive service needs TX
```
`BadgeIR.cpp`, beside the `pythonIrListening` definition: `volatile bool    driveIrWanted       = false;`
and change `irShouldBeActive()` to `return irHardwareEnabled || pythonIrListening || driveIrWanted;`

Also add to `BadgeIR.h` / `.cpp` a one-line reader so the service can report "infrared ready" without reaching into statics:
```cpp
bool irHwUp();                                   // .h
bool irHwUp() { return s_hw_up; }                // .cpp, after irHwInit's definition
```

- [ ] **Step 3: Write the service**

`firmware/src/drive/DriveBleService.h`:
```cpp
#pragma once
#ifdef BADGE_ENABLE_DRIVE_BLE
#include <cstddef>
#include <cstdint>
#include "../emotion/EmotionBleService.h"

// Tread drive over BLE: a command characteristic and a status
// characteristic on the emotion channel's server. See
// docs/superpowers/specs/tread-drive-ble-design.html.
const EmotionBleExtension* driveBleExtension(const uint8_t secret[8]);
void driveBleTick(uint8_t batteryPct);       // call every main-loop pass
bool driveBleConnected();
void driveBleStatusLine(char* buf, size_t n);
#endif
```

`firmware/src/drive/DriveBleService.cpp`:
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
#include "DriveBleService.h"

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <esp_heap_caps.h>
#include <cstring>

#include "DriveCore.h"
#include "PfTreads.h"
#include "../infra/BadgeConfig.h"
#include "../ir/BadgeIR.h"

#define DRV_SVC_UUID    "80a239a9-d8c0-4b45-82eb-41fd7207df9b"
#define DRV_WRITE_UUID  "98b99101-ab97-48b5-a9c9-e666e456806c"
#define DRV_STATE_UUID  "1350f2e6-4bdf-4459-a813-4afaf1a8ffee"

namespace {
drive::Core s_core;
pftreads::Dither s_dither;
BLECharacteristic* s_stateChar = nullptr;
uint8_t s_secret[8] = {0};

// BLE callbacks run on the BLE host task; the core runs on the main loop.
// Callbacks only park data here; driveBleTick() applies it.
portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
uint8_t s_pending[drive::kCmdLen];
uint8_t s_pendingLen = 0;       // 0 = nothing; 0xFF = malformed write
bool s_connected = false;
bool s_dropPending = false;
uint32_t s_lastStateMs = 0;

class WriteCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    const uint8_t* data = c->getData();
    const size_t len = c->getLength();
    portENTER_CRITICAL(&s_mux);
    if (data && len == drive::kCmdLen) {
      memcpy(s_pending, data, drive::kCmdLen);
      s_pendingLen = drive::kCmdLen;
    } else {
      s_pendingLen = 0xFF;
    }
    portEXIT_CRITICAL(&s_mux);
  }
};
WriteCb s_writeCb;

void addServices(BLEServer* server) {
  BLEService* svc = server->createService(DRV_SVC_UUID);
  BLECharacteristic* w =
      svc->createCharacteristic(DRV_WRITE_UUID, BLECharacteristic::PROPERTY_WRITE);
  w->setCallbacks(&s_writeCb);
  s_stateChar =
      svc->createCharacteristic(DRV_STATE_UUID, BLECharacteristic::PROPERTY_READ);
  uint8_t zero[drive::kStateLen] = {0};
  s_stateChar->setValue(zero, sizeof(zero));
  svc->start();
}
void onConnect() { s_connected = true; }
void onDisconnect() { s_connected = false; s_dropPending = true; }

const EmotionBleExtension s_ext = {addServices, onConnect, onDisconnect};

pftreads::Tuning tuning() {
  return {(uint8_t)(badgeConfig.get(kTreadChannel) - 1),
          (int16_t)badgeConfig.get(kTreadTrimPct),
          badgeConfig.get(kTreadFlipRight) != 0};
}
}  // namespace

const EmotionBleExtension* driveBleExtension(const uint8_t secret[8]) {
  memcpy(s_secret, secret, 8);
  return &s_ext;
}

bool driveBleConnected() { return s_connected; }

void driveBleTick(uint8_t batteryPct) {
  const uint32_t now = millis();

  uint8_t buf[drive::kCmdLen];
  uint8_t len;
  bool dropped;
  portENTER_CRITICAL(&s_mux);
  len = s_pendingLen; s_pendingLen = 0;
  if (len == drive::kCmdLen) memcpy(buf, s_pending, drive::kCmdLen);
  dropped = s_dropPending; s_dropPending = false;
  portEXIT_CRITICAL(&s_mux);

  if (dropped) s_core.onDisconnect();
  if (len == drive::kCmdLen) s_core.onWrite(buf, len, s_secret, now);
  else if (len == 0xFF) s_core.onWrite(nullptr, 0, s_secret, now);

  // Infrared is up while a controller is connected, and stays up until
  // the stop burst after a disconnect has gone out.
  const bool wantIr = s_connected || !s_core.burstDone();
  if (wantIr && !driveIrWanted) {
    irSetTxPower((int)badgeConfig.get(kTreadIrPowerPct));
    s_dither.reset();
  }
  driveIrWanted = wantIr;

  const uint32_t freeBytes = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
  const drive::Out o = s_core.tick(now, freeBytes);
  if (o.send && irHwUp()) {
    if (irGetMode() != IR_MODE_RAW_SYMBOL) irSetMode(IR_MODE_RAW_SYMBOL);
    int l, r;
    s_dither.next(o.leftTenths, o.rightTenths, tuning(), l, r);
    uint16_t pairs[pftreads::kPairs * 2];
    pftreads::encodePairs(pftreads::frameBits(l, r, tuning()), pairs);
    irRawSend(pairs, pftreads::kPairs, 38000);
  }

  if (s_stateChar && (o.send || now - s_lastStateMs >= 250)) {
    s_lastStateMs = now;
    uint8_t st[drive::kStateLen];
    s_core.composeState(st, now, irHwUp(), batteryPct, freeBytes,
                        heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL));
    s_stateChar->setValue(st, sizeof(st));
  }
}

void driveBleStatusLine(char* buf, size_t n) {
  if (!s_connected) { snprintf(buf, n, "Drive: waiting"); return; }
  snprintf(buf, n, "Drive: %s", s_core.driving() ? "moving" : "connected");
}
#endif  // BADGE_ENABLE_DRIVE_BLE
```
Check while writing: `badgeConfig` is the global `Config` instance's real name (grep `extern.*Config` in `BadgeConfig.h`) and `get()` is its reader (`int32_t get(uint8_t index) const`, line 198). Use whatever the existing code uses.

- [ ] **Step 4: Hook into main.cpp**

Add `#include "drive/DriveBleService.h"` beside the emotion includes (line ~16). Change the begin call (line ~495):
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
    emotionBleBegin(g_emotion, kEmotionSecret, BADGE_BLE_NAME,
                    driveBleExtension(kEmotionSecret));
#else
    emotionBleBegin(g_emotion, kEmotionSecret, BADGE_BLE_NAME);
#endif
```
Inside the existing `#ifdef BADGE_ENABLE_EMOTION_BLE` loop block (line ~613), after the closing brace of its inner `{ ... }`:
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
    driveBleTick( (uint8_t)batteryGauge.stateOfChargePercent() );
    if ( driveBleConnected() ) sleepService.caffeine = true;   // stay awake while driven
#endif
```

- [ ] **Step 5: Build both variants and re-run host tests**

Run: `cd firmware && ~/.platformio/penv/bin/pio run -e echo-drive 2>&1 | tail -3 && ~/.platformio/penv/bin/pio run -e echo-dev 2>&1 | tail -3 && for f in test/host/test_*.cpp; do c++ -std=c++17 -o /tmp/t_h "$f" && /tmp/t_h || echo "FAIL $f"; done`
Expected: `SUCCESS` twice, every host test prints its `ok` line (the emotion tests still compile with the changed header).

- [ ] **Step 6: Commit**

```bash
git add firmware/src/drive firmware/src/emotion firmware/src/ir firmware/src/main.cpp
git commit -m "firmware: tread drive BLE service on the echo-drive build"
```

---

### Task 5: One status line on the badge screen

**Files:**
- Create: `firmware/src/screens/DriveStatusScreen.h`
- Modify: `firmware/src/screens/Screen.h` (`ScreenId`, after `kScreenRobotFace`), `firmware/src/ui/GUI.cpp` (static instance beside `sRobotFace` at line ~424 and the id-to-screen lookup that returns `&sRobotFace`), `firmware/src/main.cpp`

**Interfaces:**
- Consumes: `driveBleStatusLine(char*, size_t)`, `driveBleConnected()` (Task 4).
- Produces: `kScreenDriveStatus`.

- [ ] **Step 1: Write the screen**

`firmware/src/screens/DriveStatusScreen.h`:
```cpp
#pragma once
#ifdef BADGE_ENABLE_DRIVE_BLE
#include "Screen.h"
#include "../drive/DriveBleService.h"

// One plain line saying what the tread-drive service is doing.
class DriveStatusScreen : public Screen {
 public:
  void render(oled& d, GUIManager& gui) override {
    (void)gui;
    char line[24];
    driveBleStatusLine(line, sizeof(line));
    d.clearBuffer();
    d.setFont(u8g2_font_6x10_tf);
    d.drawStr(0, 36, line);
    d.sendBuffer();
  }
  void handleInput(const Inputs& inputs, int16_t cursorX, int16_t cursorY,
                   GUIManager& gui) override {
    (void)inputs; (void)cursorX; (void)cursorY; (void)gui;
  }
  ScreenId id() const override { return kScreenDriveStatus; }
  bool showCursor() const override { return false; }
  ScreenAccess access() const override { return ScreenAccess::kAny; }
};
#endif
```
Check against `RobotFaceScreen.cpp`'s `render`: if screens there do not call `clearBuffer`/`sendBuffer` themselves (the GUI manager does it), remove those two calls; if `oled` has no `drawStr`, use the text call that screen uses. Match the existing screens, do not invent a new drawing path.

- [ ] **Step 2: Register it**

In `Screen.h` add, directly after `kScreenRobotFace,`:
```cpp
#ifdef BADGE_ENABLE_DRIVE_BLE
  kScreenDriveStatus,
#endif
```
In `GUI.cpp`: include the header, add `static DriveStatusScreen sDriveStatus;` under the same `#ifdef` beside `static RobotFaceScreen sRobotFace;`, and add its case to the lookup that maps `kScreenRobotFace` to `&sRobotFace` (same `#ifdef`). Do not add a menu entry.

- [ ] **Step 3: Show it while connected**

In `main.cpp`, extend the Task 4 loop block:
```cpp
    {
        static bool shown = false;
        if ( guiManager.isActive() && driveBleConnected() && !shown ) {
            guiManager.pushScreen( kScreenDriveStatus ); shown = true;
        } else if ( !driveBleConnected() && shown ) {
            guiManager.popScreen(); shown = false;
        }
    }
```
Check `GUIManager` for the real name of the pop call (grep `popScreen\|goBack` in `ui/GUI.h`) and use it.

- [ ] **Step 4: Build both variants**

Run: `~/.platformio/penv/bin/pio run -e echo-drive 2>&1 | tail -3 && ~/.platformio/penv/bin/pio run -e echo-dev 2>&1 | tail -3`
Expected: `SUCCESS` twice.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/screens/DriveStatusScreen.h firmware/src/screens/Screen.h firmware/src/ui/GUI.cpp firmware/src/main.cpp
git commit -m "firmware: one-line drive status screen while a controller is connected"
```

---

### Task 6: Mac test controller

**Files:**
- Create: `firmware/scripts/pf_ir/pf_ble_drive.py`
- Create: `firmware/scripts/pf_ir/test_pf_ble_drive.py`
- Modify: `firmware/scripts/pf_ir/README.md`

**Interfaces:**
- Produces: `build_cmd(secret: bytes, left: float, right: float, ttl_ds: int) -> bytes`, `parse_state(b: bytes) -> dict`, CLI `pf_ble_drive.py [--status] [<left> <right> <ms> ...]`.
- The secret comes from the environment variable `ROCKY_TREAD_SECRET` (8 ASCII characters). The script never prints it.

- [ ] **Step 1: Write the failing test**

`firmware/scripts/pf_ir/test_pf_ble_drive.py`:
```python
import pytest
from pf_ble_drive import build_cmd, parse_state

S = b"ABCDEFGH"

def test_build_cmd_layout():
    assert build_cmd(S, 4, 4, 10) == S + bytes([40, 40, 10])
    assert build_cmd(S, -4.3, 0, 2) == S + bytes([256 - 43, 0, 2])

@pytest.mark.parametrize("args", [(7.1, 0, 5), (0, -7.1, 5), (1, 1, 0), (1, 1, 11)])
def test_build_cmd_rejects_out_of_range(args):
    with pytest.raises(ValueError):
        build_cmd(S, *args)

def test_build_cmd_needs_8_byte_secret():
    with pytest.raises(ValueError):
        build_cmd(b"short", 1, 1, 5)

def test_parse_state():
    st = parse_state(bytes([0x03, 256 - 25, 33, 6, 87, 36, 32, 1]))
    assert st == {"driving": True, "ir_ready": True, "low_memory": False, "rejected": False,
                  "left": -2.5, "right": 3.3, "left_s": 0.6, "battery": 87,
                  "free_kb": 9.0, "min_free_kb": 8.0, "accepted": 1}

def test_parse_state_wrong_length():
    with pytest.raises(ValueError):
        parse_state(b"\x00" * 7)
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd firmware/scripts/pf_ir && uv run --with pytest --with bleak pytest test_pf_ble_drive.py -q`
Expected: FAIL, no module `pf_ble_drive`.

- [ ] **Step 3: Write the script**

`firmware/scripts/pf_ir/pf_ble_drive.py`:
```python
"""Drive the tank base over Bluetooth: pf_ble_drive.py [--status] [<left> <right> <ms> ...]

Speeds are -7..7 per tread (fractions allowed, to one decimal), positive forward.
Needs the badge on the echo-drive firmware and ROCKY_TREAD_SECRET set (8 characters).
Run with:  uv run --with bleak pf_ble_drive.py 4 4 1500
"""
import asyncio, os, struct, sys

NAME = "Rocky IR Tread"
WRITE_UUID = "98b99101-ab97-48b5-a9c9-e666e456806c"
STATE_UUID = "1350f2e6-4bdf-4459-a813-4afaf1a8ffee"
RESEND_S = 0.2
TTL_DS = 6            # each command is valid 0.6 s: three missed resends, then the badge stops


def build_cmd(secret: bytes, left: float, right: float, ttl_ds: int) -> bytes:
    if len(secret) != 8:
        raise ValueError("secret must be 8 bytes")
    lt, rt = round(left * 10), round(right * 10)
    if abs(lt) > 70 or abs(rt) > 70 or not 1 <= ttl_ds <= 10:
        raise ValueError("speed must be -7..7 and ttl 1..10")
    return secret + struct.pack("<bbB", lt, rt, ttl_ds)


def parse_state(b: bytes) -> dict:
    if len(b) != 8:
        raise ValueError("state must be 8 bytes")
    flags, lt, rt, left_ds, batt, free_q, min_q, accepted = struct.unpack("<BbbBBBBB", b)
    return {"driving": bool(flags & 1), "ir_ready": bool(flags & 2),
            "low_memory": bool(flags & 4), "rejected": bool(flags & 8),
            "left": lt / 10, "right": rt / 10, "left_s": left_ds / 10, "battery": batt,
            "free_kb": free_q / 4, "min_free_kb": min_q / 4, "accepted": accepted}


async def run(steps, status_only):
    from bleak import BleakClient, BleakScanner
    secret = os.environ.get("ROCKY_TREAD_SECRET", "").encode()
    if len(secret) != 8:
        raise SystemExit("ROCKY_TREAD_SECRET must be set to 8 characters")
    dev = await BleakScanner.find_device_by_name(NAME, timeout=10)
    if dev is None:
        raise SystemExit(f"no badge named {NAME!r} found")
    async with BleakClient(dev) as c:
        await asyncio.sleep(0.5)                       # let the badge bring IR up
        print("status", parse_state(bytes(await c.read_gatt_char(STATE_UUID))))
        if status_only:
            return
        try:
            for left, right, ms in steps:
                end = asyncio.get_running_loop().time() + ms / 1000
                while asyncio.get_running_loop().time() < end:
                    await c.write_gatt_char(WRITE_UUID, build_cmd(secret, left, right, TTL_DS), response=True)
                    await asyncio.sleep(RESEND_S)
                print("did", left, right, ms)
        finally:
            await c.write_gatt_char(WRITE_UUID, build_cmd(secret, 0, 0, 1), response=True)
        await asyncio.sleep(0.5)
        print("status", parse_state(bytes(await c.read_gatt_char(STATE_UUID))))


def main(argv):
    status_only = "--status" in argv
    nums = [float(a) for a in argv if a != "--status"]
    if (not nums and not status_only) or len(nums) % 3:
        raise SystemExit(__doc__)
    steps = [(nums[i], nums[i + 1], int(nums[i + 2])) for i in range(0, len(nums), 3)]
    for left, right, _ in steps:
        build_cmd(b"00000000", left, right, TTL_DS)    # range check before connecting
    asyncio.run(run(steps, status_only))


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: Run the tests**

Run: `uv run --with pytest --with bleak pytest test_pf_ble_drive.py -q`
Expected: 8 passed.

- [ ] **Step 5: Document it**

Append to `firmware/scripts/pf_ir/README.md`:
```markdown

## Driving over Bluetooth (no cable)

Needs the badge on the `echo-drive` firmware. Set `ROCKY_TREAD_SECRET` to the badge's 8-character
shared secret first (it is the emotion channel's secret; do not put it in a file here).

    uv run --with bleak pf_ble_drive.py --status          # connect, print status and memory
    uv run --with bleak pf_ble_drive.py 4 4 1500          # forward, speed 4, 1.5 s

The script resends the command five times a second; each is valid for 0.6 s. If the script dies or
Bluetooth drops, the badge sends a stop and goes quiet, and the LEGO receiver stops by itself too.
Trim, right-side flip, channel and IR power are `tr_*` lines in the badge's `settings.txt`.
Status prints free internal memory now and the lowest since power-on; the badge refuses to drive
below 6 KB.
```

- [ ] **Step 6: Commit**

```bash
git add firmware/scripts/pf_ir/pf_ble_drive.py firmware/scripts/pf_ir/test_pf_ble_drive.py firmware/scripts/pf_ir/README.md
git commit -m "scripts: Bluetooth test controller for the tread drive"
```

---

### Task 7: On the hardware, with Pat present

Nothing in this task is done without Pat at the desk. macOS will ask once for Bluetooth permission for the terminal; tell Pat before the first run.

- [ ] **Step 1: Flash the spare**

```bash
pkill -f serial_log.py; cd firmware && P=$(ls /dev/cu.usbmodem* | head -1) && ~/.platformio/penv/bin/pio run -e echo-drive -t upload --upload-port $P 2>&1 | tail -3
```
Expected: `SUCCESS`. Wait 15 s for the boot.

- [ ] **Step 2: Memory gate (spec rule 4) — stop here if it fails**

Run: `cd scripts/pf_ir && uv run --with bleak pf_ble_drive.py --status`
Expected: a status line with `ir_ready: True` and `min_free_kb` above 6.0. Record both memory figures in the README's Bluetooth section.
If `min_free_kb` is at or below 6.0: do not go on. Report the figures to Pat; the next step is freeing memory (Wi-Fi start-up attempt, main-loop stack, the 4 KB raw-TX queue of two 2 KB entries in `BadgeIR.cpp`), which is its own piece of work.

- [ ] **Step 3: Drive with the cable still in, treads off the desk**

Run: `uv run --with bleak pf_ble_drive.py 4 4 1500`
Expected: both treads forward for about 1.5 s, then stop. Pat confirms.

- [ ] **Step 4: Cable out, on the carpet**

Pat unplugs USB and sets the badge on the base facing the receiver. One at a time, Pat confirming each: `4 4 1500` (forward about a foot, straight), `-4 -4 1500` (back), `4 -4 500` (quarter turn right), `-4 4 500` (quarter turn left).

- [ ] **Step 5: The three stop layers**

Each during `uv run --with bleak pf_ble_drive.py 3 3 8000`, base must stop within about a second:
1. Ctrl-C the script.
2. Turn the Mac's Bluetooth off (Pat does this in Control Centre).
3. Pat covers the badge's emitter with a hand.

- [ ] **Step 6: Ten-minute soak**

Run a mixed sequence for ten minutes (treads off the ground is fine), then `--status`.
Expected: `min_free_kb` still above 6.0, `rejected: False`, `low_memory: False`.

- [ ] **Step 7: Record results and commit**

Add the measured figures and any re-tuned `tr_*` values to the README section; commit `README.md` only.
