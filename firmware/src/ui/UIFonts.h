#pragma once

#include <U8g2lib.h>

namespace UIFonts {

static constexpr const char* kTextName = "Terminus t0_11";
static constexpr const uint8_t* kText = u8g2_font_t0_11_tr;

// Compact font for the thin status-bar and footer bands, which are
// dimensioned (8 px status pill, baseline-6 text) for a ~6 px font.
// kText (Terminus, ~10 px) crowds those bands, so chrome draws use
// this instead; menu/body text keeps kText.
static constexpr const uint8_t* kChrome = u8g2_font_smallsimple_tr;

}  // namespace UIFonts
