// lv_conf.h — minimal LVGL 8.x configuration for the pantry terminal.
// Resolved via -DLV_CONF_INCLUDE_SIMPLE and -I src (see platformio.ini).
// Anything not set here falls back to LVGL's built-in defaults.
#pragma once

#define LV_COLOR_DEPTH 16

// Set to 1 if reds/blues look swapped (and flip COLOR_SWAP in board.h to match
// the byte order Arduino_GFX writes).
#define LV_COLOR_16_SWAP 0

// Drive LVGL's tick from Arduino's millis() so we don't need a hardware timer.
#define LV_TICK_CUSTOM 1
#define LV_TICK_CUSTOM_INCLUDE "Arduino.h"
#define LV_TICK_CUSTOM_SYS_TIME_EXPR (millis())

// Heap for LVGL objects/styles.
#define LV_MEM_SIZE (48U * 1024U)

// Fonts used by ui.cpp.
#define LV_FONT_MONTSERRAT_16 1
#define LV_FONT_MONTSERRAT_20 1
#define LV_FONT_MONTSERRAT_28 1
#define LV_FONT_DEFAULT &lv_font_montserrat_16

// Widgets used: button, label, spinner (arc) — all on by default in 8.x.
