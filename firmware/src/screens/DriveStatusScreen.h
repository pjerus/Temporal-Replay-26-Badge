#pragma once
#ifdef BADGE_ENABLE_DRIVE_BLE
#include "Screen.h"
#include "../hardware/oled.h"
#include "../drive/DriveBleService.h"

// One plain line saying what the tread-drive service is doing.
class DriveStatusScreen : public Screen {
 public:
  void render(oled& d, GUIManager& gui) override {
    (void)gui;
    char line[24];
    driveBleStatusLine(line, sizeof(line));
    d.setDrawColor(1);
    d.setFontPreset(FONT_SMALL);
    d.drawStr(0, 36, line);
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
