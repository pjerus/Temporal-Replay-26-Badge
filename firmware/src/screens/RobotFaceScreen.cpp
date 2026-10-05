#include "RobotFaceScreen.h"
#include "RobotFaceOverride.h"

#include <Arduino.h>
#include <math.h>

#include "../hardware/HardwareConfig.h"
#include "../hardware/IMU.h"
#include "../hardware/Inputs.h"
#include "../hardware/LEDmatrix.h"
#include "../hardware/oled.h"
#include "../ui/GUI.h"

extern IMU imu;
#ifdef BADGE_HAS_LED_MATRIX
extern LEDmatrix badgeMatrix;
#endif

namespace {
constexpr int CY = 32;   // vertical centre of the eyes
constexpr int GAP = 10;  // space between the eyes
constexpr int EW = 36;   // base eye width
constexpr int EH = 36;   // base eye height
constexpr int RAD = 8;   // base corner radius

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// 8x8 mouth per mood (bit 7 = leftmost column). Indexed by Mood; the
// row count matches RobotFaceScreen::kMoodCount.
const uint8_t kMouths[8][8] = {
  /*neutral  */ {0,0,0,0,0,0b00111100,0,0},
  /*happy    */ {0,0,0,0,0b01000010,0b00111100,0,0},
  /*tired    */ {0,0,0,0,0,0,0b00111100,0},
  /*sad      */ {0,0,0,0,0,0b01000010,0b00111100,0},
  /*angry    */ {0,0,0,0,0b00111100,0b01000010,0,0},
  /*surprised*/ {0,0,0b00011000,0b00100100,0b00100100,0b00011000,0,0},
  /*curious  */ {0,0,0,0,0,0b00111100,0,0},
  /*scared   */ {0,0,0b00011000,0b00100100,0b00100100,0b00011000,0,0},
};
}  // namespace

void RobotFaceScreen::drawEye(oled& d, int x, int y, int w, int h, int rad,
                              Mood lid, float amt) {
  int r = rad > h / 2 ? h / 2 : rad;
  if (r < 0) r = 0;
  d.setDrawColor(1);
  d.drawRBox(x, y, w, h, r);

  if (h <= 8 || lid == kNeutral) return;
  const int t = (int)lroundf((h / 2) * amt);
  if (t < 1) return;
  d.setDrawColor(0);
  switch (lid) {
    case kTired:  d.fillTriangle(x, y - 1, x + w, y - 1, x,     y + t - 1); break;
    case kAngry:  d.fillTriangle(x, y - 1, x + w, y - 1, x + w, y + t - 1); break;
    case kHappy:  d.drawRBox(x - 1, (y + h) - t + 1, w + 2, h, 8);          break;
    case kSad:    d.drawRBox(x - 1, y - 1, w + 2, t, 8);                    break;
    default: break;
  }
  d.setDrawColor(1);
}

void RobotFaceScreen::pickExpressiveMood() {
  // Weighted toward upbeat; heavier moods show up occasionally.
  static const Mood pool[] = {
    kHappy, kHappy, kHappy, kCurious, kCurious, kCurious,
    kSurprised, kSurprised, kHappy, kTired, kSad, kAngry, kScared,
  };
  mood_ = pool[random((long)(sizeof(pool) / sizeof(pool[0])))];
  moodAmt_ = 0.f;
  nextMoodMs_ = millis() + 2500 + random(2500);  // hold the expression
}

void RobotFaceScreen::pickGaze() {
  gxTgt_ = (float)(random(23) - 11);
  gyTgt_ = (float)(random(13) - 6);
  nextGazeMs_ = millis() + 900 + random(2200);
}

void RobotFaceScreen::updateMatrixMouth(int shift) {
#ifdef BADGE_HAS_LED_MATRIX
  const int bucket = (int)mood_;
  if (bucket < 0 || bucket >= 8) return;  // defensive: never index kMouths out of bounds
  if (bucket == lastMouthMood_ && shift == lastMouthShift_) return;
  lastMouthMood_ = bucket;
  lastMouthShift_ = shift;
  uint8_t mask[LED_MATRIX_HEIGHT];
  for (int r = 0; r < LED_MATRIX_HEIGHT && r < 8; r++) {
    uint8_t row = kMouths[bucket][r];
    if (shift > 0) row >>= 1;       // gaze right -> mouth right
    else if (shift < 0) row <<= 1;
    mask[r] = row;
  }
  badgeMatrix.drawMaskHardware(mask, 60, 0);
#else
  (void)shift;
#endif
}

void RobotFaceScreen::onEnter(GUIManager& gui) {
  (void)gui;
  const uint32_t now = millis();
  open_ = 0.f;
  gx_ = gy_ = gxTgt_ = gyTgt_ = 0.f;
  moodAmt_ = 0.f;
  mood_ = kNeutral;
  blinking_ = false;
  nextBlinkMs_ = now + 700;
  nextGazeMs_ = now + 600;
  nextMoodMs_ = now + 1200;
  lastMouthMood_ = -1;
  lastMouthShift_ = 99;
  if (emotion_) emotion_->setFaceOnScreen(true);
#ifdef BADGE_HAS_LED_MATRIX
  badgeMatrix.setMicropythonMode(true);  // take the matrix from the idle overlay
#endif
}

void RobotFaceScreen::onExit(GUIManager& gui) {
  (void)gui;
  if (emotion_) emotion_->setFaceOnScreen(false);
#ifdef BADGE_HAS_LED_MATRIX
  badgeMatrix.clear(0);
  badgeMatrix.setMicropythonMode(false);
#endif
}

void RobotFaceScreen::render(oled& d, GUIManager& gui) {
  const uint32_t now = millis();

  // ── Blink: snap shut, then reopen ──
  float openTgt = 1.f;
  if (!blinking_ && now >= nextBlinkMs_) { blinking_ = true; blinkStartMs_ = now; }
  if (blinking_) {
    const uint32_t ph = now - blinkStartMs_;
    openTgt = (ph < 90) ? 0.f : 1.f;
    if (ph >= 180) { blinking_ = false; nextBlinkMs_ = now + 1500 + random(2800); }
  }
  open_ += (openTgt - open_) * 0.5f;

  // ── Gaze: idle target plus a lean from tilt ──
  if (now >= nextGazeMs_) pickGaze();
  float tiltX = 0.f, tiltY = 0.f;
  if (imu.isReady()) { tiltX = imu.tiltXMg() / 110.f; tiltY = imu.tiltYMg() / 150.f; }
  gx_ += (clampf(gxTgt_ + tiltX, -11.f, 11.f) - gx_) * 0.14f;
  gy_ += (clampf(gyTgt_ + tiltY, -6.f, 6.f) - gy_) * 0.14f;

  // ── Mood: an injected emotion overrides; otherwise alternate between
  //    an expression and a neutral rest. ──
  uint8_t ovMood; float ovInten;
  if (emotion_ && chooseOverride(*emotion_, now, ovMood, ovInten)) {
    mood_ = (Mood)ovMood;
    moodAmt_ = ovInten;          // honor the injected strength directly
    nextMoodMs_ = now + 1000;    // re-checked each frame while active
  } else {
    if (now >= nextMoodMs_) {
      if (mood_ == kNeutral) pickExpressiveMood();
      else { mood_ = kNeutral; nextMoodMs_ = now + 4500 + random(5000); }
    }
    moodAmt_ += (((mood_ == kNeutral) ? 0.f : 1.f) - moodAmt_) * 0.12f;
    if (emotion_) emotion_->setAutonomousMood((uint8_t)mood_);
  }

  // ── Geometry ──
  const float scale = (mood_ == kSurprised || mood_ == kScared)
                          ? 1.f + 0.22f * moodAmt_ : 1.f;
  const int ew = (int)lroundf(EW * scale);
  const int eh = (int)lroundf(EH * scale);
  const int gxi = (int)lroundf(gx_);
  const int gyi = (int)lroundf(gy_);

  int wL = ew, wR = ew;
  int ehL = eh, ehR = eh;
  if (mood_ == kCurious) {  // enlarge the outer eye toward the gaze
    if (gxi >= 0) { wR += 6; ehR += 8; } else { wL += 6; ehL += 8; }
  }
  const int hL = (int)lroundf(ehL * open_);
  const int hR = (int)lroundf(ehR * open_);

  const int totalW = wL + GAP + wR;
  const int xL = (128 - totalW) / 2 + gxi;
  const int yL = CY - hL / 2 + gyi;
  const int xR = xL + wL + GAP;
  const int yR = CY - hR / 2 + gyi;
  const int rad = (mood_ == kSurprised || mood_ == kScared) ? 16 : RAD;

  const Mood lid = (mood_ == kHappy || mood_ == kTired ||
                    mood_ == kSad || mood_ == kAngry) ? mood_ : kNeutral;
  drawEye(d, xL, yL, wL, hL, rad, lid, moodAmt_);
  drawEye(d, xR, yR, wR, hR, rad, lid, moodAmt_);

  // Scared: a teardrop on the forehead above the outer eye.
  if (mood_ == kScared && moodAmt_ > 0.4f) {
    const int cx = xR + wR - 4, cy = yR - 2;
    d.setDrawColor(1);
    d.fillTriangle(cx, cy - 6, cx - 3, cy + 1, cx + 3, cy + 1);
    d.drawDisc(cx, cy + 2, 3);
  }

  updateMatrixMouth(gxi > 4 ? 1 : (gxi < -4 ? -1 : 0));

  gui.requestRender();  // keep the animation ticking
}

void RobotFaceScreen::handleInput(const Inputs& inputs, int16_t cursorX,
                                  int16_t cursorY, GUIManager& gui) {
  (void)cursorX;
  (void)cursorY;
  const Inputs::ButtonEdges& e = inputs.edges();
  if (e.cancelPressed || e.bPressed) { gui.popScreen(); return; }
  if (e.confirmPressed) {
    if (emotion_ && emotion_->activeAt(millis())) {
      emotion_->clear();  // escape: drop an injected emotion, back to autonomous
    } else if (mood_ == kNeutral) {  // otherwise nudge a fresh expression on demand
      pickExpressiveMood();
    } else {
      nextMoodMs_ = millis();
    }
  }
}
