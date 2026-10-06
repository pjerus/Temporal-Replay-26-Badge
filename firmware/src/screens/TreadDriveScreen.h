#pragma once
#ifdef BADGE_ENABLE_DRIVE_BLE
#include "Screen.h"
#include "../drive/DriveBleService.h"
#include "../drive/JoyPad.h"
#include "../hardware/Inputs.h"
#include "../hardware/oled.h"
#include "../ui/ButtonGlyphs.h"
#include "../ui/GUI.h"

extern char badgeName[];

// Drive the tank base from the badge: joystick steers, the up/down
// buttons dash, left/right do a quarter turn, up+down together exits.
// Feeds the same DriveCore as the BLE service, so the stop rules match.
class TreadDriveScreen : public Screen {
 public:
  void onEnter(GUIManager& gui) override {
    (void)gui;
    pad_ = drive::JoyPad();
    pad_.invertY = true;   // on this badge the stick reads smaller Y when pushed forward
    left_ = right_ = 0;
    driveLocalSet(true, 0, 0);
  }
  void onExit(GUIManager& gui) override {
    (void)gui;
    driveLocalSet(false, 0, 0);
  }
  void handleInput(const Inputs& inputs, int16_t cursorX, int16_t cursorY,
                   GUIManager& gui) override {
    (void)cursorX; (void)cursorY;
    const Inputs::ButtonStates& b = inputs.buttons();
    const Inputs::ButtonEdges& e = inputs.edges();
    drive::PadIn in{};
    in.joyX = inputs.joyX();
    in.joyY = inputs.joyY();
    in.up = b.up; in.down = b.down;
    in.leftPressed = e.leftPressed; in.rightPressed = e.rightPressed;
    in.nowMs = millis();
    const drive::PadOut o = pad_.step(in);
    if (o.exit) { gui.popScreen(); return; }
    left_ = o.left; right_ = o.right;
    driveLocalSet(true, left_, right_);
  }
  void render(oled& d, GUIManager& gui) override {
    (void)gui;
    char line[28];
    d.setDrawColor(1);
    d.setFontPreset(FONT_SMALL);
    d.drawStr(0, 10, badgeName[0] ? badgeName : "DRIVE");   // which badge this is
    snprintf(line, sizeof(line), "L %+d.%d   R %+d.%d",
             left_ / 10, abs(left_) % 10, right_ / 10, abs(right_) % 10);
    d.drawStr(0, 28, line);
    d.setFontPreset(FONT_TINY);
    ButtonGlyphs::drawInlineHint(d, 0, 46, "^ v full speed   < > turn");
    ButtonGlyphs::drawInlineHint(d, 0, 60, "^ + v together: exit");
  }
  ScreenId id() const override { return kScreenTreadDrive; }
  bool showCursor() const override { return false; }
  ScreenAccess access() const override { return ScreenAccess::kAny; }

 private:
  drive::JoyPad pad_;
  int8_t left_ = 0, right_ = 0;
};
#endif
