// ui.h — LVGL screens for the pantry terminal.
#pragma once

// Build the home grid + status screen. Call once after lv_init() and the
// display/touch drivers are registered.
void uiInit();

// Call every iteration of loop() (after lv_timer_handler). Runs any pending
// add-to-cart request and handles the auto-return-to-grid timeout.
void uiLoop();
