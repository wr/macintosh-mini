// board.h — ALL board-specific pins live here.
//
// =====================  READ THIS BEFORE YOU FLASH  ========================
// These defaults target the *Elecrow ESP32-S3 3.5" Terminal* (480x320, ILI9488
// parallel, FT6236 capacitive touch). Elecrow ships several similar SKUs with
// different pinouts. The single most reliable thing you can do is open
// Elecrow's own LVGL/Arduino_GFX demo for YOUR exact board and copy the
// Arduino_GFX constructor + touch I2C pins into this file. If the screen stays
// black or touch is offset, that's the knob to turn — not the app code.
// ===========================================================================
#pragma once

// ---- Display (ILI9488, 8-bit 8080 parallel via Arduino_GFX) ----------------
#define TFT_BL   46   // backlight enable (active high)

#define TFT_DC   2
#define TFT_CS   46   // some Elecrow parallel panels tie CS; verify
#define TFT_WR   1
#define TFT_RD   41

// D0..D7 data bus
#define TFT_D0   41
#define TFT_D1   40
#define TFT_D2   39
#define TFT_D3   38
#define TFT_D4   37
#define TFT_D5   36
#define TFT_D6   35
#define TFT_D7   45

#define TFT_RST  -1   // -1 if tied to the board reset

// Logical (post-rotation) screen size used by the app.
#define SCREEN_WIDTH  480
#define SCREEN_HEIGHT 320
#define SCREEN_ROTATION 1   // 1 or 3 = landscape on a native-portrait ILI9488

// If colors look inverted/wrong, flip this (and LV_COLOR_16_SWAP in lv_conf.h).
#define COLOR_SWAP 0

// ---- Capacitive touch (FT6236 / FT6336, I2C @ 0x38) ------------------------
#define TOUCH_SDA  38
#define TOUCH_SCL  39
#define TOUCH_RST  -1
#define TOUCH_INT  -1
#define TOUCH_I2C_ADDR 0x38

// Touch panel reports coordinates in the panel's native orientation. These
// knobs map raw touch -> screen pixels for SCREEN_ROTATION above. Tune by
// printing raw values (see touch.cpp) and adjusting until a tap lands true.
#define TOUCH_SWAP_XY   1
#define TOUCH_INVERT_X  0
#define TOUCH_INVERT_Y  1
#define TOUCH_RAW_MAX_X 320   // native panel max along its X
#define TOUCH_RAW_MAX_Y 480   // native panel max along its Y
