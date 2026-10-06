#pragma once
#ifdef BADGE_ENABLE_DRIVE_BLE
#include "Screen.h"
#include "../drive/DriveBleService.h"
#include "../drive/HeliCore.h"
#include "../hardware/Inputs.h"
#include "../hardware/oled.h"
#include "../infra/BadgeConfig.h"
#include "../ir/BadgeIR.h"
#include "../ui/ButtonGlyphs.h"
#include "../ui/GUI.h"

// Fly a Syma S107G helicopter from the badge: joystick turns and tilts,
// the up/down buttons step the throttle, left/right trim, up+down
// together cuts the rotors and exits. The helicopter cuts its own rotors
// when frames stop, so leaving or freezing this screen lands it.
class HeliScreen : public Screen {
 public:
  void onEnter(GUIManager& gui) override {
    (void)gui;
    pad_ = heli::Pad();
    pad_.invertY = true;   // on this badge the stick reads smaller Y when pushed forward
    pad_.trim = (int)badgeConfig.get(kHeliTrim);
    pad_.throttleStep = (int)badgeConfig.get(kHeliThrottleStep);
    channelB_ = badgeConfig.get(kHeliChannel) == 2;
    out_ = {63, 63, 0, (uint8_t)pad_.trim, false};
    lastSendMs_ = 0;
    driveLocalSet(true, 0, 0);   // holds the IR sender up and keeps BLE drive commands out
  }
  void onExit(GUIManager& gui) override {
    (void)gui;
    send(heli::frameWord(63, 63, 0, out_.trim, channelB_));
    driveLocalSet(false, 0, 0);
  }
  void handleInput(const Inputs& inputs, int16_t cursorX, int16_t cursorY,
                   GUIManager& gui) override {
    (void)cursorX; (void)cursorY;
    const Inputs::ButtonStates& b = inputs.buttons();
    const Inputs::ButtonEdges& e = inputs.edges();
    heli::PadIn in{};
    in.joyX = inputs.joyX();
    in.joyY = inputs.joyY();
    in.up = b.up; in.down = b.down;
    in.leftPressed = e.leftPressed; in.rightPressed = e.rightPressed;
    in.nowMs = millis();
    out_ = pad_.step(in);
    if (out_.exit) { gui.popScreen(); return; }
    driveLocalSet(true, 0, 0);
    if (in.nowMs - lastSendMs_ >= heli::periodMs(channelB_)) {
      lastSendMs_ = in.nowMs;
      send(heli::frameWord(out_.yaw, out_.pitch, out_.throttle, out_.trim, channelB_));
    }
  }
  void render(oled& d, GUIManager& gui) override {
    (void)gui;
    char line[28];
    d.setDrawColor(1);
    d.setFontPreset(FONT_SMALL);
    snprintf(line, sizeof(line), "HELI %c   trim %+d", channelB_ ? 'B' : 'A', (int)out_.trim - 63);
    d.drawStr(0, 10, line);
    d.drawRFrame(0, 16, 128, 9, 1);
    d.drawBox(2, 18, out_.throttle * 124 / 127, 5);
    if (!irHwIsUp()) snprintf(line, sizeof(line), "power %d%%  IR OFF", out_.throttle * 100 / 127);
    else snprintf(line, sizeof(line), "power %d%%  s%u f%u", out_.throttle * 100 / 127, (unsigned)sent_ % 1000, (unsigned)failed_ % 1000);
    d.drawStr(0, 36, line);
    d.setFontPreset(FONT_TINY);
    ButtonGlyphs::drawInlineHint(d, 0, 48, "^ v power   < > trim");
    ButtonGlyphs::drawInlineHint(d, 0, 60, "^ + v together: exit");
  }
  ScreenId id() const override { return kScreenHeli; }
  bool showCursor() const override { return false; }
  ScreenAccess access() const override { return ScreenAccess::kAny; }

 private:
  void send(uint32_t word) {
    if (!irHwIsUp()) return;
    if (irGetMode() != IR_MODE_RAW_SYMBOL) irSetMode(IR_MODE_RAW_SYMBOL);
    uint16_t pairs[heli::kPairs * 2];
    heli::encodePairs(word, pairs);
    if (irRawSend(pairs, heli::kPairs, 38000) == 0) sent_++; else failed_++;
  }

  heli::Pad pad_;
  heli::PadOut out_{63, 63, 0, 63, false};
  bool channelB_ = false;
  uint32_t lastSendMs_ = 0;
  uint32_t sent_ = 0, failed_ = 0;   // shown on screen while the app is being proven
};
#endif
