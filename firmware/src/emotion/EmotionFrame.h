#pragma once
#include <stddef.h>
#include <stdint.h>

// Emotion wire frame — the cross-language contract. Keep byte-for-byte
// identical to emotion-channel/emotion_channel/frame.py. No Arduino deps
// so this compiles and is tested on the host.
//
// Layout (6 bytes, little-endian):
//   byte 0   mood index (0..7)
//   byte 1   intensity (0..255)
//   byte 2-3 ttl in deciseconds (uint16; 0 = latch until replaced/cleared)
//   byte 4   source id
//   byte 5   flags (bit0 = speaking)
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
