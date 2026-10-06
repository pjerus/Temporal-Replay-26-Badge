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
    if (l == 0 && r == 0) { if (driving_) stop(); return; }
    // Only a start from rest sends at once; a resend or a speed change rides
    // the next 90 ms frame, so a chatty controller cannot flood the IR queue.
    if (!driving_) fresh_ = true;
    left_ = l; right_ = r;
    startMs_ = nowMs; ttlMs_ = (uint32_t)ttl * 100;
    driving_ = true; stopsLeft_ = 0;
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

// When the drive service may ask for the IR hardware. IR stays wanted for
// kHoldMs after the last need so the final stop frame is sent, and is not
// asked for again within kLockoutMs of a release, so the IR task's teardown
// has finished before anything touches the hardware again.
class IrLease {
 public:
  static constexpr uint32_t kHoldMs = 300;
  static constexpr uint32_t kLockoutMs = 300;

  bool want(bool need, uint32_t nowMs) {
    if (need) {
      if (!held_ && released_ && (uint32_t)(nowMs - releasedMs_) < kLockoutMs) return false;
      held_ = true; lastNeedMs_ = nowMs;
      return true;
    }
    if (!held_) return false;
    if ((uint32_t)(nowMs - lastNeedMs_) < kHoldMs) return true;
    held_ = false; released_ = true; releasedMs_ = nowMs;
    return false;
  }

 private:
  bool held_ = false, released_ = false;
  uint32_t lastNeedMs_ = 0, releasedMs_ = 0;
};

}  // namespace drive