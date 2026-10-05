# Emotion Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a skill-enabled AI inject emotions (mood + intensity + duration) onto the badge robot face over Bluetooth LE, with the reusable pieces packaged for the shared code library.

**Architecture:** The badge exposes a minimal NimBLE GATT "emotion" service (write-with-response to set an emotion, readable characteristic for state). A host-side Python bridge (bleak) wraps that service in an API-key HTTP endpoint; the same Python code can also talk to the badge directly (no bridge). A pure-logic `EmotionConsumer` on the badge applies an override to `RobotFaceScreen` for its duration, then lets the autonomous liveliness resume. A 6-byte wire frame is the cross-language contract shared by firmware and host.

**Tech Stack:** ESP32-S3 Arduino C++17 (PlatformIO, NimBLE-Arduino), host Python 3.11+ (bleak, FastAPI or Flask, pytest), a Claude skill wrapper.

**Spec:** `docs/superpowers/specs/emotion-channel-design.html`

## Global Constraints

- Target board is **ESP32-S3 — Bluetooth LE only, no Bluetooth Classic.** No A2DP/HFP anywhere in this plan (that is the sibling voice spec).
- BLE is currently **compiled out**: `platformio.ini` has `build_src_filter` lines `-<ble/>` and `+<ble/BleScan.cpp>`, gated behind the unset `BADGE_ENABLE_BLE_PROXIMITY`. This feature re-enables **only** the files it needs behind a **new** flag `BADGE_ENABLE_EMOTION_BLE`; it must NOT turn on the proximity scanner.
- **Measure flash + RAM** after the GATT service links, against the current ~2.6 MB image, and confirm it fits the OTA-frozen 16 MB partition (`partitions_replay_16MB_doom.csv`). Record the delta in the task.
- **Mood enum order is fixed and shared**, identical in firmware and host: `0 neutral, 1 happy, 2 tired, 3 sad, 4 angry, 5 surprised, 6 curious, 7 scared` — matches `RobotFaceScreen::Mood` (`src/screens/RobotFaceScreen.h`).
- **Override-then-expire** is the only apply mode. `ttl = 0` means *latch until replaced or explicitly cleared*.
- **Wire frame is the contract.** Any change to it changes both the C++ codec and the Python codec in the same commit.
- **Settings are passed in, never hardcoded in shared code** (coding-discipline rule 4): API key, badge BLE address/name, shared secret, bind port — all via args/env with defaults. The local bind port is registered via the `local-dev-hosting` skill and reachable at a `.test` host.
- **Reusable modules are registered as coderef entries** once they pass their tests (`coderef check` then `coderef approve`).
- This is internal tooling; no outward-facing cost display is involved (no-cost rule N/A).

## Review Focus

Inputs the spec implies but which a happy-path test would miss — each is pinned to a task below:

- **Malformed BLE frame** (wrong length, mood byte > 7): the badge must reject it and leave the face unchanged, never index past the mood table. → Task 2 tests.
- **Bad/missing auth** (wrong shared token on GATT write; wrong/absent Bearer key at the bridge): the emotion must not apply; GATT write errors, bridge returns 401. → Task 6 + Task 9 tests.
- **Emotion injected while the face is off-screen**: accepted and time-stamped, `state.face_on_screen=false`; because overrides expire by wall-clock, a short ttl may lapse before the user opens the face — that is the intended ephemeral behavior, asserted explicitly. → Task 4 + Task 7 tests.
- **`ttl = 0` latch**: stays indefinitely until a replacing write or an explicit clear; a clear path must exist and be tested. → Task 3 tests.
- **Badge unreachable mid-session** (out of range / disconnected): `GET /state` and `POST /emotion` return a clear error, not a stale or fabricated value. → Task 8 tests.

---

## File structure

**Shared contract + firmware (in `firmware/`):**
- `firmware/src/emotion/EmotionFrame.h` — wire-format codec (pure, host-compilable, no Arduino deps).
- `firmware/src/emotion/EmotionConsumer.h` — override/expire logic (pure, host-compilable).
- `firmware/src/emotion/EmotionBleService.h/.cpp` — NimBLE GATT service; the only file with BLE/Arduino deps.
- `firmware/src/screens/RobotFaceScreen.h/.cpp` — modify to read `EmotionConsumer`.
- `firmware/src/main.cpp`, `firmware/src/ui/GUI.cpp` — wire the consumer + service in.
- `firmware/platformio.ini` — new `BADGE_ENABLE_EMOTION_BLE` flag + build-filter.
- `firmware/test/host/` — standalone host tests (clang++), not on-device.

**Host library + bridge (new top-level `emotion-channel/`):**
- `emotion-channel/emotion_channel/frame.py` — Python codec (mirror of `EmotionFrame.h`).
- `emotion-channel/emotion_channel/backends.py` — `BleBackend`, `HttpBackend`.
- `emotion-channel/emotion_channel/client.py` — `EmotionClient`.
- `emotion-channel/emotion_channel/bridge.py` — API-key HTTP service.
- `emotion-channel/emotion_channel/config.py` — settings from env/args with defaults.
- `emotion-channel/tests/` — pytest.
- `emotion-channel/pyproject.toml`.

**Skill:**
- `~/.claude/skills/badge-emotion/SKILL.md` + a thin script calling `EmotionClient` over HTTP.

---

## Phase 0 — Shared wire-format contract

### Task 1: Python emotion frame codec

**Files:**
- Create: `emotion-channel/emotion_channel/frame.py`
- Create: `emotion-channel/tests/test_frame.py`
- Create: `emotion-channel/pyproject.toml` (minimal: name, py>=3.11, deps: pytest dev)

**Interfaces:**
- Produces: `MOODS: list[str]` (index-ordered); `encode_emotion(mood: str|int, intensity: float, ttl_ms: int, source: int = 0, speaking: bool = False) -> bytes` (6 bytes); `decode_emotion(buf: bytes) -> dict` with keys `mood`(str), `intensity`(float 0..1), `ttl_ms`(int), `source`(int), `speaking`(bool); raises `ValueError` on bad input.

- [ ] **Step 1: Write the failing test**

```python
# emotion-channel/tests/test_frame.py
import pytest
from emotion_channel.frame import encode_emotion, decode_emotion, MOODS

def test_roundtrip_happy():
    buf = encode_emotion("happy", 0.8, 20000, source=1)
    assert len(buf) == 6
    d = decode_emotion(buf)
    assert d["mood"] == "happy"
    assert abs(d["intensity"] - 0.8) < 0.01
    assert d["ttl_ms"] == 20000
    assert d["source"] == 1
    assert d["speaking"] is False

def test_mood_order_is_fixed():
    assert MOODS == ["neutral","happy","tired","sad","angry","surprised","curious","scared"]

def test_ttl_zero_is_latch():
    assert decode_emotion(encode_emotion("angry", 1.0, 0))["ttl_ms"] == 0

def test_ttl_caps_at_uint16_deciseconds():
    # 2 bytes of deciseconds -> max 65535 ds = 6553500 ms
    assert decode_emotion(encode_emotion("sad", 0.5, 9_999_999))["ttl_ms"] == 6553500

def test_bad_mood_rejected():
    with pytest.raises(ValueError):
        encode_emotion("ecstatic", 0.5, 1000)

def test_short_buffer_rejected():
    with pytest.raises(ValueError):
        decode_emotion(b"\x01\x02")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd emotion-channel && python -m pytest tests/test_frame.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
# emotion-channel/emotion_channel/frame.py
"""Emotion wire frame — the cross-language contract. Keep byte-for-byte
identical to firmware/src/emotion/EmotionFrame.h."""
import struct

MOODS = ["neutral", "happy", "tired", "sad", "angry", "surprised", "curious", "scared"]
_SPEAKING_BIT = 0x01

def _mood_index(mood):
    if isinstance(mood, int):
        if not 0 <= mood < len(MOODS):
            raise ValueError(f"mood index out of range: {mood}")
        return mood
    try:
        return MOODS.index(mood)
    except ValueError:
        raise ValueError(f"unknown mood: {mood!r}")

def encode_emotion(mood, intensity, ttl_ms, source=0, speaking=False):
    mi = _mood_index(mood)
    inten = max(0, min(255, round(float(intensity) * 255)))
    ttl_ds = max(0, min(0xFFFF, round(int(ttl_ms) / 100)))
    flags = _SPEAKING_BIT if speaking else 0
    return struct.pack("<BBHBB", mi, inten, ttl_ds, source & 0xFF, flags)

def decode_emotion(buf):
    if len(buf) != 6:
        raise ValueError(f"emotion frame must be 6 bytes, got {len(buf)}")
    mi, inten, ttl_ds, source, flags = struct.unpack("<BBHBB", buf)
    if mi >= len(MOODS):
        raise ValueError(f"mood index out of range: {mi}")
    return {
        "mood": MOODS[mi],
        "intensity": inten / 255,
        "ttl_ms": ttl_ds * 100,
        "source": source,
        "speaking": bool(flags & _SPEAKING_BIT),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd emotion-channel && python -m pytest tests/test_frame.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add emotion-channel/emotion_channel/frame.py emotion-channel/tests/test_frame.py emotion-channel/pyproject.toml
git commit -m "feat(emotion): python wire-frame codec"
```

### Task 2: C++ emotion frame codec (host-tested)

**Files:**
- Create: `firmware/src/emotion/EmotionFrame.h`
- Create: `firmware/test/host/test_emotion_frame.cpp`

**Interfaces:**
- Produces: namespace `emotion` with `struct Frame { uint8_t mood; uint8_t intensity; uint16_t ttlDs; uint8_t source; uint8_t flags; };`, `constexpr size_t kFrameLen = 6;`, `size_t encode(const Frame&, uint8_t out[kFrameLen]);`, `bool decode(const uint8_t* in, size_t len, Frame& out);` (returns false on wrong length or `mood > 7`). Byte layout identical to Task 1.

- [ ] **Step 1: Write the failing test**

```cpp
// firmware/test/host/test_emotion_frame.cpp
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
  printf("ok\n");
  return 0;
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd firmware && /usr/bin/clang++ -std=c++17 -w test/host/test_emotion_frame.cpp -o /tmp/tef && /tmp/tef`
Expected: FAIL to compile (`EmotionFrame.h` not found).

- [ ] **Step 3: Write minimal implementation**

```cpp
// firmware/src/emotion/EmotionFrame.h
#pragma once
#include <stddef.h>
#include <stdint.h>

// Emotion wire frame — the cross-language contract. Keep byte-for-byte
// identical to emotion-channel/emotion_channel/frame.py. No Arduino deps
// so this compiles and is tested on the host.
namespace emotion {
constexpr size_t kFrameLen = 6;
constexpr uint8_t kMoodCount = 8;
constexpr uint8_t kFlagSpeaking = 0x01;

struct Frame {
  uint8_t mood;       // 0..7
  uint8_t intensity;  // 0..255
  uint16_t ttlDs;     // deciseconds; 0 = latch
  uint8_t source;
  uint8_t flags;
};

inline size_t encode(const Frame& f, uint8_t out[kFrameLen]) {
  out[0] = f.mood;
  out[1] = f.intensity;
  out[2] = (uint8_t)(f.ttlDs & 0xFF);         // little-endian
  out[3] = (uint8_t)((f.ttlDs >> 8) & 0xFF);
  out[4] = f.source;
  out[5] = f.flags;
  return kFrameLen;
}

inline bool decode(const uint8_t* in, size_t len, Frame& out) {
  if (len != kFrameLen) return false;
  if (in[0] >= kMoodCount) return false;
  out.mood = in[0];
  out.intensity = in[1];
  out.ttlDs = (uint16_t)(in[2] | (in[3] << 8));
  out.source = in[4];
  out.flags = in[5];
  return true;
}
}  // namespace emotion
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd firmware && /usr/bin/clang++ -std=c++17 -w test/host/test_emotion_frame.cpp -o /tmp/tef && /tmp/tef`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/emotion/EmotionFrame.h firmware/test/host/test_emotion_frame.cpp
git commit -m "feat(emotion): c++ wire-frame codec (host-tested)"
```

---

## Phase 1 — Firmware: consumer logic + face integration

### Task 3: EmotionConsumer override/expire logic (host-tested)

**Files:**
- Create: `firmware/src/emotion/EmotionConsumer.h`
- Create: `firmware/test/host/test_emotion_consumer.cpp`

**Interfaces:**
- Consumes: `emotion::Frame` (Task 2).
- Produces: `class EmotionConsumer` with:
  `void apply(const emotion::Frame& f, uint32_t nowMs);`
  `void clear();`
  `bool activeAt(uint32_t nowMs) const;`
  `uint8_t mood() const;` `float intensity() const;`
  `uint32_t msLeftAt(uint32_t nowMs) const;` (0 none/expired; `UINT32_MAX` for a `ttlDs==0` latch)
  `void setFaceOnScreen(bool v);` `bool faceOnScreen() const;`
  All time is passed in (`nowMs`); no Arduino deps. Uses `volatile`/plain fields — single-writer from the BLE task, read from render task; store the 6 raw fields + `setAtMs` so reads are consistent without locks.

- [ ] **Step 1: Write the failing test**

```cpp
// firmware/test/host/test_emotion_consumer.cpp
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
  assert(c.activeAt(9'999'999));
  assert(c.msLeftAt(9'999'999) == UINT32_MAX);
  c.clear();
  assert(!c.activeAt(5001));

  // face-on-screen flag
  assert(!c.faceOnScreen());
  c.setFaceOnScreen(true);
  assert(c.faceOnScreen());

  printf("ok\n");
  return 0;
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd firmware && /usr/bin/clang++ -std=c++17 -w test/host/test_emotion_consumer.cpp -o /tmp/tec && /tmp/tec`
Expected: FAIL to compile (`EmotionConsumer.h` not found).

- [ ] **Step 3: Write minimal implementation**

```cpp
// firmware/src/emotion/EmotionConsumer.h
#pragma once
#include <stdint.h>
#include "EmotionFrame.h"

// Holds the currently injected emotion and answers whether it is still
// live at a given time. Pure logic (time passed in) so it is host-tested
// and reused by any device. Single writer (BLE task) / single reader
// (render task); fields are plain and a read is a cheap snapshot.
class EmotionConsumer {
 public:
  void apply(const emotion::Frame& f, uint32_t nowMs) {
    frame_ = f; setAtMs_ = nowMs; active_ = true;
  }
  void clear() { active_ = false; }

  bool activeAt(uint32_t nowMs) const {
    if (!active_) return false;
    if (frame_.ttlDs == 0) return true;            // latch
    return (nowMs - setAtMs_) <= (uint32_t)frame_.ttlDs * 100u;
  }
  uint8_t mood() const { return frame_.mood; }
  float intensity() const { return frame_.intensity / 255.0f; }

  uint32_t msLeftAt(uint32_t nowMs) const {
    if (!active_) return 0;
    if (frame_.ttlDs == 0) return UINT32_MAX;       // latch
    uint32_t span = (uint32_t)frame_.ttlDs * 100u;
    uint32_t elapsed = nowMs - setAtMs_;
    return elapsed >= span ? 0 : (span - elapsed);
  }

  void setFaceOnScreen(bool v) { faceOnScreen_ = v; }
  bool faceOnScreen() const { return faceOnScreen_; }

 private:
  emotion::Frame frame_{};
  uint32_t setAtMs_ = 0;
  volatile bool active_ = false;
  volatile bool faceOnScreen_ = false;
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd firmware && /usr/bin/clang++ -std=c++17 -w test/host/test_emotion_consumer.cpp -o /tmp/tec && /tmp/tec`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/emotion/EmotionConsumer.h firmware/test/host/test_emotion_consumer.cpp
git commit -m "feat(emotion): EmotionConsumer override/expire logic (host-tested)"
```

### Task 4: RobotFaceScreen reads the override

**Files:**
- Modify: `firmware/src/screens/RobotFaceScreen.h` (add a consumer pointer + setter)
- Modify: `firmware/src/screens/RobotFaceScreen.cpp` (onEnter/onExit set faceOnScreen; render honors an active override)
- Create: `firmware/test/host/test_robotface_override.cpp` (tests only the override-selection helper, extracted as a free function)

**Interfaces:**
- Consumes: `EmotionConsumer` (Task 3).
- Produces: `void RobotFaceScreen::bindEmotion(EmotionConsumer* c);`. New private free helper in the `.cpp`'s anonymous namespace, declared in a tiny internal header so it is host-testable:
  `bool chooseOverride(const EmotionConsumer& c, uint32_t nowMs, uint8_t& moodOut, float& intensityOut);` → true when render should use the injected mood instead of the autonomous pick.

Because the override-selection is the only new *logic* (the rest is drawing already covered on-device), the host test targets `chooseOverride`; the drawing change is verified on-device in Task 7.

- [ ] **Step 1: Write the failing test**

```cpp
// firmware/test/host/test_robotface_override.cpp
#include "../../src/emotion/EmotionConsumer.h"
#include "../../src/screens/RobotFaceOverride.h"   // declares chooseOverride
#include <cassert>
#include <cstdio>
int main() {
  EmotionConsumer c;
  uint8_t m; float in;
  assert(!chooseOverride(c, 1000, m, in));          // nothing injected
  emotion::Frame surprised{5, 230, 100 /*10s*/, 0, 0};
  c.apply(surprised, 1000);
  assert(chooseOverride(c, 2000, m, in));
  assert(m == 5);
  assert(in > 0.89f && in < 0.91f);
  assert(!chooseOverride(c, 20000, m, in));          // expired -> autonomous
  printf("ok\n");
  return 0;
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd firmware && /usr/bin/clang++ -std=c++17 -w test/host/test_robotface_override.cpp -o /tmp/tro && /tmp/tro`
Expected: FAIL to compile (`RobotFaceOverride.h` not found).

- [ ] **Step 3: Write minimal implementation**

Create `firmware/src/screens/RobotFaceOverride.h`:

```cpp
#pragma once
#include <stdint.h>
#include "../emotion/EmotionConsumer.h"

// Returns true and fills moodOut/intensityOut when an injected emotion
// should drive the face at nowMs; false to use the autonomous picker.
inline bool chooseOverride(const EmotionConsumer& c, uint32_t nowMs,
                           uint8_t& moodOut, float& intensityOut) {
  if (!c.activeAt(nowMs)) return false;
  moodOut = c.mood();
  intensityOut = c.intensity();
  return true;
}
```

In `RobotFaceScreen.h`, add:
```cpp
#include "../emotion/EmotionConsumer.h"
// ... in the class:
 public:
  void bindEmotion(EmotionConsumer* c) { emotion_ = c; }
 private:
  EmotionConsumer* emotion_ = nullptr;
```

In `RobotFaceScreen.cpp`:
- `#include "RobotFaceOverride.h"`.
- In `onEnter`: `if (emotion_) emotion_->setFaceOnScreen(true);`
- In `onExit`: `if (emotion_) emotion_->setFaceOnScreen(false);`
- In `render`, replace the mood/intensity selection. After computing `now`, before the autonomous mood block:
```cpp
  uint8_t ovMood; float ovInten;
  if (emotion_ && chooseOverride(*emotion_, now, ovMood, ovInten)) {
    mood_ = (Mood)ovMood;
    moodAmt_ = ovInten;            // drive the tween straight to injected strength
    nextMoodMs_ = now + 1000;      // hold; re-checked each frame while active
  } else if (now >= nextMoodMs_) {
    if (mood_ == kNeutral) pickExpressiveMood();
    else { mood_ = kNeutral; nextMoodMs_ = now + 4500 + random(5000); }
  }
```
(Leave the existing `moodAmt_` easing line; when overriding we set it directly, the ease is a no-op toward the same value.)

- [ ] **Step 4: Run host test to verify it passes**

Run: `cd firmware && /usr/bin/clang++ -std=c++17 -w test/host/test_robotface_override.cpp -o /tmp/tro && /tmp/tro`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/screens/RobotFaceOverride.h firmware/src/screens/RobotFaceScreen.h firmware/src/screens/RobotFaceScreen.cpp firmware/test/host/test_robotface_override.cpp
git commit -m "feat(emotion): RobotFaceScreen honors an injected override"
```

---

## Phase 2 — Firmware: NimBLE GATT service

### Task 5: Re-enable a minimal BLE build behind a new flag

**Files:**
- Modify: `firmware/platformio.ini`

Add to the `echo-dev` (and `echo`) build flags: `-DBADGE_ENABLE_EMOTION_BLE`. Add to `build_src_filter` (after the existing `+<ble/BleScan.cpp>` line): `+<emotion/>` and `+<ble/BadgeBeaconAdv.cpp>` **only if** `EmotionBleService` reuses it — otherwise add just `+<emotion/EmotionBleService.cpp>`. Do **not** add `-DBADGE_ENABLE_BLE_PROXIMITY` and do **not** re-add the scanner (`BleBeaconScanner.cpp`).

- [ ] **Step 1: Add the flag and filter.** Edit `platformio.ini` as above.
- [ ] **Step 2: Build (service not written yet — expect it to link with an empty service TU).** Create a stub `firmware/src/emotion/EmotionBleService.cpp` with `#ifdef BADGE_ENABLE_EMOTION_BLE` wrapping an empty `void emotionBleBegin(EmotionConsumer&) {}` so the build is green.
  Run: `~/.platformio/penv/bin/pio run -e echo-dev 2>&1 | tail -5`
  Expected: SUCCESS.
- [ ] **Step 3: Record the flash/RAM baseline.** Note `RAM:` and `Flash:` lines from the build output in the commit message.
- [ ] **Step 4: Commit**

```bash
git add firmware/platformio.ini firmware/src/emotion/EmotionBleService.cpp
git commit -m "build(emotion): BADGE_ENABLE_EMOTION_BLE flag + emotion src filter"
```

### Task 6: EmotionBleService — NimBLE GATT service

**Files:**
- Modify: `firmware/src/emotion/EmotionBleService.cpp`
- Create: `firmware/src/emotion/EmotionBleService.h`

**Interfaces:**
- Consumes: `EmotionConsumer` (Task 3), `emotion::decode` (Task 2), the NimBLE-Arduino API used by `ble/BadgeBeaconAdv.cpp` (study that file for the project's init/advertising pattern), `Power` for battery %.
- Produces: `void emotionBleBegin(EmotionConsumer& consumer, const uint8_t secret[8], const char* advName);` and `void emotionBleStatePublish(EmotionConsumer& consumer, uint8_t batteryPct);` (called periodically to refresh the readable state characteristic).

**UUIDs (allocate once, document here):** service `d7a40000-...`, emotion char `d7a40001-...`, state char `d7a40002-...`, events char `d7a40003-...` (phase 2, declared NOTIFY, not populated yet). Use full random 128-bit UUIDs generated at implementation time; write them into the header as named constants.

**Auth:** the `emotion` write payload is `[8-byte shared secret][6-byte frame]` = 14 bytes (fits the negotiated ATT MTU). The write callback rejects (returns a GATT error) unless the first 8 bytes equal `secret` AND `emotion::decode` of the remaining 6 succeeds. On success it calls `consumer.apply(frame, millis())`.

**State characteristic (7 bytes, little-endian):** `[flags][ovMood][ovIntensity][msLeft/100 uint16][autoMood][batteryPct]`, where `flags` bit0 = override active, bit1 = face_on_screen. `msLeft/100` caps at `0xFFFF`; a latch publishes `0xFFFF` with the active bit set.

- [ ] **Step 1: On-device acceptance test (written first, as a runnable script).**

Create `firmware/test/device/emotion_smoke.md` describing the manual/scripted check, and a host script `emotion-channel/scripts/smoke_write.py` (uses bleak; depends on Phase 3 backend — if running Phase 2 standalone, use a `nRF Connect` manual step instead). The pass condition:
  1. Flash, open the ROBOT screen.
  2. From the host, connect and write `secret + encode_emotion("scared",1.0,8000)` to the emotion char.
  3. The face shows scared (teardrop) within ~0.5 s and returns to lively after ~8 s.
  4. A wrong-secret write produces a GATT write error and the face does NOT change.
  5. A 3-byte garbage write produces a GATT write error and does NOT crash (badge stays responsive).

- [ ] **Step 2: Implement `EmotionBleService.cpp`.** Model init/advertising on `ble/BadgeBeaconAdv.cpp`. Register the service, the write callback (auth + decode + `apply`), and the read callback (compose the 7-byte state from `consumer` + `Power::batteryPercent()`). Guard the whole file in `#ifdef BADGE_ENABLE_EMOTION_BLE`.

- [ ] **Step 3: Build + flash.**
  Run: `~/.platformio/penv/bin/pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem11301 2>&1 | tail -5`
  Expected: SUCCESS. Record the flash/RAM delta vs Task 5 baseline in the commit message; confirm it still fits the partition.

- [ ] **Step 4: Run the on-device acceptance test** from Step 1 (manual with nRF Connect if Phase 3 isn't built yet). All five conditions pass.

- [ ] **Step 5: Commit**

```bash
git add firmware/src/emotion/EmotionBleService.h firmware/src/emotion/EmotionBleService.cpp firmware/test/device/emotion_smoke.md
git commit -m "feat(emotion): NimBLE GATT emotion service (write+state, auth)"
```

### Task 7: Wire the consumer + service into the app

**Files:**
- Modify: `firmware/src/main.cpp` (define `EmotionConsumer g_emotion;`, call `emotionBleBegin` in setup under the flag, call `emotionBleStatePublish` from the periodic service tick)
- Modify: `firmware/src/ui/GUI.cpp` (after `sRobotFace` is constructed, `sRobotFace.bindEmotion(&g_emotion);`)

**Interfaces:**
- Consumes: `emotionBleBegin`, `emotionBleStatePublish` (Task 6), `RobotFaceScreen::bindEmotion` (Task 4).

- [ ] **Step 1: Add the global + bind.** `extern EmotionConsumer g_emotion;` declared in a small `emotion/EmotionGlobals.h`; defined in `main.cpp`. Bind in `GUI.cpp` where `sRobotFace` lives.
- [ ] **Step 2: Call begin + publish.** In `main.cpp` setup (guarded): load the 8-byte secret from config (`BadgeConfig`, default to a compile-time dev secret), call `emotionBleBegin(g_emotion, secret, advName)`. In the periodic tick (~1 Hz is enough) call `emotionBleStatePublish(g_emotion, Power::batteryPercent())`.
- [ ] **Step 3: Build + flash.**
  Run: `~/.platformio/penv/bin/pio run -e echo-dev -t upload --upload-port /dev/cu.usbmodem11301 2>&1 | tail -5`
  Expected: SUCCESS.
- [ ] **Step 4: On-device verify** the full Task 6 acceptance test now works end-to-end, **and** the off-screen case: inject while on a different screen → the state read reports `face_on_screen=false`; open ROBOT within the ttl → the emotion shows; open it after the ttl → it does not (expired, as designed).
- [ ] **Step 5: Commit**

```bash
git add firmware/src/main.cpp firmware/src/ui/GUI.cpp firmware/src/emotion/EmotionGlobals.h
git commit -m "feat(emotion): wire consumer + BLE service into the app"
```

---

## Phase 3 — Host: client with BLE + HTTP backends

### Task 8: BleBackend + EmotionClient

**Files:**
- Create: `emotion-channel/emotion_channel/config.py`
- Create: `emotion-channel/emotion_channel/backends.py` (`BleBackend`)
- Create: `emotion-channel/emotion_channel/client.py` (`EmotionClient`)
- Create: `emotion-channel/tests/test_client.py`

**Interfaces:**
- Consumes: `encode_emotion`, `decode_emotion` (Task 1); the GATT UUIDs + 7-byte state layout (Task 6); `bleak`.
- Produces:
  `class Backend(Protocol): async def send(frame: bytes) -> None; async def read_state() -> dict`
  `class BleBackend(Backend)` ctor `(address: str, secret: bytes, *, uuids=DEFAULT_UUIDS)` — prepends `secret` to `frame`, writes the emotion char with-response, reads+parses the state char; raises `BadgeUnreachable` on connect failure.
  `class EmotionClient` ctor `(backend: Backend)` with `inject(mood, intensity, ttl_ms, source=0, speaking=False) -> dict` (returns the post-write state) and `state() -> dict`.
  `parse_state(buf: bytes) -> dict` (pure; mirrors Task 6 layout) in `backends.py`.
  `class BadgeUnreachable(Exception)`.

- [ ] **Step 1: Write the failing test** (pure `parse_state` + client against a fake backend):

```python
# emotion-channel/tests/test_client.py
import pytest
from emotion_channel.backends import parse_state, BadgeUnreachable
from emotion_channel.client import EmotionClient
from emotion_channel.frame import decode_emotion

def test_parse_state_override_active():
    # flags=0b11 active+face, mood=5, inten=230, msLeft/100=50, autoMood=0, batt=76
    buf = bytes([0b11, 5, 230, 50, 0, 0, 76])
    s = parse_state(buf)
    assert s["override"]["mood"] == "surprised"
    assert s["override"]["ms_left"] == 5000
    assert s["face_on_screen"] is True
    assert s["battery_pct"] == 76

def test_parse_state_idle():
    buf = bytes([0, 0, 0, 0, 2, 0, 50])
    s = parse_state(buf)
    assert s["override"] is None
    assert s["autonomous"] == "tired"

class FakeBackend:
    def __init__(self): self.sent = None
    async def send(self, frame): self.sent = frame
    async def read_state(self): return bytes([0b01, 1, 204, 100, 0, 0, 90])

def test_client_inject_roundtrips_frame():
    import asyncio
    be = FakeBackend()
    c = EmotionClient(be)
    state = asyncio.run(c.inject("happy", 0.8, 20000))
    assert decode_emotion(be.sent)["mood"] == "happy"   # backend got a valid frame
    assert state["override"]["mood"] == "happy"
```

- [ ] **Step 2: Run to verify it fails.** `cd emotion-channel && python -m pytest tests/test_client.py -v` → FAIL (imports).
- [ ] **Step 3: Implement** `config.py` (UUIDs + defaults from env), `parse_state` + `BleBackend` + `BadgeUnreachable` in `backends.py`, `EmotionClient` in `client.py`. `BleBackend.send/read_state` use `async with bleak.BleakClient(address): ...`, wrapping `BleakError`/timeout as `BadgeUnreachable`.
- [ ] **Step 4: Run to verify it passes.** Same command → PASS (3 tests).
- [ ] **Step 5: On-device integration check** (requires a flashed badge from Phase 2): `python -m emotion_channel.scripts.smoke_write --address <badge> --mood scared` sets the face. Document in the task; this is a manual integration step, not a unit test.
- [ ] **Step 6: Commit**

```bash
git add emotion-channel/emotion_channel/config.py emotion-channel/emotion_channel/backends.py emotion-channel/emotion_channel/client.py emotion-channel/tests/test_client.py
git commit -m "feat(emotion): python BleBackend + EmotionClient"
```

---

## Phase 4 — Host: the bridge (HTTP + API key)

### Task 9: HttpBackend + bridge service

**Files:**
- Modify: `emotion-channel/emotion_channel/backends.py` (add `HttpBackend`)
- Create: `emotion-channel/emotion_channel/bridge.py`
- Create: `emotion-channel/tests/test_bridge.py`
- Modify: `emotion-channel/pyproject.toml` (deps: `bleak`, `fastapi`, `uvicorn`, `httpx` for tests)

**Interfaces:**
- Consumes: `EmotionClient`, `BleBackend` (Task 8), `encode_emotion`/`decode_emotion`, `config` (badge registry: name → address + secret; `EMOTION_API_KEY`; bind port).
- Produces:
  FastAPI app `create_app(registry, api_key, backend_factory=BleBackend)`:
  `POST /emotion` body `{target, mood, intensity, ttl_ms, source?}` header `Authorization: Bearer <key>` → `{ok, applied, state}`; 401 on bad key; 404 on unknown target; 502 (`{ok:false, error}`) on `BadgeUnreachable`.
  `GET /state?target=` → state json or 502.
  `class HttpBackend(Backend)` ctor `(base_url, api_key, target)` — the client-side mirror so a skill can use the bridge via the same `EmotionClient`.

- [ ] **Step 1: Write the failing test** (TestClient + fake backend factory, no real BLE):

```python
# emotion-channel/tests/test_bridge.py
from fastapi.testclient import TestClient
from emotion_channel.bridge import create_app
from emotion_channel.backends import BadgeUnreachable

class FakeBackend:
    def __init__(self, address, secret, **kw): self.last=None
    async def send(self, frame): self.last=frame
    async def read_state(self): return bytes([0b01,1,204,100,0,0,88])

REG = {"lobby": {"address": "AA:BB", "secret": b"12345678"}}

def app(factory=FakeBackend):
    return TestClient(create_app(REG, api_key="k3y", backend_factory=factory))

def test_requires_api_key():
    r = app().post("/emotion", json={"target":"lobby","mood":"happy","intensity":0.8,"ttl_ms":20000})
    assert r.status_code == 401

def test_happy_path():
    r = app().post("/emotion", headers={"Authorization":"Bearer k3y"},
                   json={"target":"lobby","mood":"happy","intensity":0.8,"ttl_ms":20000})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["state"]["override"]["mood"] == "happy"

def test_unknown_target():
    r = app().post("/emotion", headers={"Authorization":"Bearer k3y"},
                   json={"target":"nope","mood":"happy","intensity":0.8,"ttl_ms":20000})
    assert r.status_code == 404

def test_badge_unreachable_is_502():
    class Dead(FakeBackend):
        async def send(self, frame): raise BadgeUnreachable("out of range")
    r = app(Dead).post("/emotion", headers={"Authorization":"Bearer k3y"},
                       json={"target":"lobby","mood":"happy","intensity":0.8,"ttl_ms":20000})
    assert r.status_code == 502 and r.json()["ok"] is False
```

- [ ] **Step 2: Run to verify it fails.** `cd emotion-channel && python -m pytest tests/test_bridge.py -v` → FAIL.
- [ ] **Step 3: Implement** `HttpBackend` and `create_app`. The app builds an `EmotionClient(backend_factory(addr, secret))` per request (or caches per target), validates the Bearer key with `secrets.compare_digest`, maps exceptions to 401/404/502. Add a `__main__`/console entry that reads `config` and runs uvicorn on the registered port.
- [ ] **Step 4: Run to verify it passes.** Same command → PASS (4 tests).
- [ ] **Step 5: Register the port** via the `local-dev-hosting` skill and add the `.test` hostname; record the chosen port in `config.py` default + a one-line note in the task.
- [ ] **Step 6: On-device end-to-end** (flashed badge + bridge running): `curl -H "Authorization: Bearer $EMOTION_API_KEY" -d '{"target":"...","mood":"curious","intensity":0.7,"ttl_ms":15000}' https://emotion.test/emotion` moves the face. Manual integration step.
- [ ] **Step 7: Commit**

```bash
git add emotion-channel/emotion_channel/backends.py emotion-channel/emotion_channel/bridge.py emotion-channel/tests/test_bridge.py emotion-channel/pyproject.toml
git commit -m "feat(emotion): HTTP bridge with API-key auth + HttpBackend"
```

---

## Phase 5 — The Claude skill + library registration

### Task 10: `badge-emotion` skill

**Files:**
- Create: `~/.claude/skills/badge-emotion/SKILL.md`
- Create: `~/.claude/skills/badge-emotion/inject.py` (thin CLI over `EmotionClient` + `HttpBackend`)

**Interfaces:**
- Consumes: `EmotionClient`, `HttpBackend` (Task 9); config via env (`EMOTION_BRIDGE_URL`, `EMOTION_API_KEY`, `EMOTION_TARGET`).

- [ ] **Step 1:** Write `SKILL.md`: name `badge-emotion`, description "inject an emotion (mood + strength + duration) onto a Temporal badge robot face, and read its state"; document the two actions and the env config; note it uses the HTTP backend (bridge) by default and can be pointed at a BLE backend for direct use.
- [ ] **Step 2:** Write `inject.py`: args `--mood --intensity --ttl-ms [--state]`; prints the returned state as JSON. Reads config from env with clear errors when unset.
- [ ] **Step 3: Verify** against a running bridge + badge: `python inject.py --mood happy --intensity 0.9 --ttl-ms 12000` moves the face and prints state; `--state` prints current state.
- [ ] **Step 4: Commit** (skills live outside the repo; commit in the dotfiles/skills location as appropriate, or note it's a user-global skill).

### Task 11: Register reusable modules as coderef entries

**Files:** coderef `entries/` (library repo).

- [ ] **Step 1:** For each reusable unit — `emotion-frame` (the wire format, both language files as references), `emotion-consumer` (C++), `emotion-client-py` (client + backends + bridge) — create a coderef entry with its marker line and one-paragraph guidance on what it does, how to use it, and its single dependency (the wire frame).
- [ ] **Step 2:** `coderef check <names>` → fix any rule violations.
- [ ] **Step 3:** `coderef approve <names>` to commit + tag each.
- [ ] **Step 4:** `coderef index` to refresh the index.

---

## Self-review notes

- **Spec coverage:** message schema → Tasks 1–2; override/expire → Task 3; face integration → Tasks 4, 7; GATT service + auth + state → Task 6; feedback (ack via write-with-response, `GET /state`, `face_on_screen`) → Tasks 6, 8, 9; multi-badge Pi gateway → Task 9 (`target` + registry; the bridge runs unchanged on a Pi); two-backend client (D + E) → Tasks 8, 9; skill → Task 10; library → Task 11; BLE-compiled-out risk → Task 5 + flash measurement in Tasks 5–7. Voice extension is explicitly out of scope. **No gaps.**
- **Review Focus coverage:** malformed frame → Task 2 + Task 6 Step 1 cond. 5; bad auth → Task 6 Step 1 cond. 4 + Task 9 `test_requires_api_key`; off-screen injection → Task 7 Step 4; `ttl=0` latch → Task 3; badge unreachable → Task 9 `test_badge_unreachable_is_502` + `BadgeUnreachable` in Task 8.
- **Type consistency:** `emotion::Frame` fields and the 6-byte/7-byte layouts are used identically across Tasks 2, 3, 6, 8; `EmotionClient`/`Backend`/`parse_state`/`BadgeUnreachable` names are consistent across Tasks 8–9.
