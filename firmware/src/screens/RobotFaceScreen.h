#pragma once
#include "Screen.h"
#include "../emotion/EmotionConsumer.h"

// A lively animated robot face. Rounded eyes blink, idle-wander, lean
// with tilt (IMU), and cycle through shape-driven moods — expression
// comes entirely from the eye SHAPE (lids carved into the top/bottom),
// no separate eyebrows. The 8x8 LED matrix shows a mouth that tracks
// gaze and mood. Reachable from the main menu.
//
// The eye/lid geometry is the native U8g2 reimplementation of the look
// prototyped in the host mock (scratchpad robot_mock.c) and signed off
// pose-by-pose; keep the two in sync if the look is revised.
class RobotFaceScreen : public Screen {
 public:
  void onEnter(GUIManager& gui) override;
  void onExit(GUIManager& gui) override;
  void render(oled& d, GUIManager& gui) override;
  void handleInput(const Inputs& inputs, int16_t cursorX, int16_t cursorY,
                   GUIManager& gui) override;
  ScreenId id() const override { return kScreenRobotFace; }
  bool showCursor() const override { return false; }
  ScreenAccess access() const override { return ScreenAccess::kAny; }

  // Bind the shared emotion override source (written by the BLE service).
  void bindEmotion(EmotionConsumer* c) { emotion_ = c; }

 private:
  enum Mood : uint8_t {
    kNeutral, kHappy, kTired, kSad, kAngry, kSurprised, kCurious, kScared,
    kMoodCount
  };

  void pickExpressiveMood();
  void pickGaze();
  void updateMatrixMouth(int gazeShift);
  static void drawEye(oled& d, int x, int y, int w, int h, int rad,
                      Mood lid, float amt);

  // Tweened state — current values ease toward targets each frame.
  float open_ = 0.f;                 // eye openness 0..1
  float gx_ = 0.f, gy_ = 0.f;        // gaze offset (px)
  float gxTgt_ = 0.f, gyTgt_ = 0.f;
  float moodAmt_ = 0.f;              // 0..1 progress into current mood

  Mood mood_ = kNeutral;
  bool blinking_ = false;
  uint32_t blinkStartMs_ = 0;
  uint32_t nextBlinkMs_ = 0;
  uint32_t nextGazeMs_ = 0;
  uint32_t nextMoodMs_ = 0;

  int lastMouthMood_ = -1;
  int lastMouthShift_ = 99;

  EmotionConsumer* emotion_ = nullptr;
};
