// display.h — display bring-up (Arduino_GFX) exposed to main.cpp.
#pragma once
#include <Arduino_GFX_Library.h>

extern Arduino_GFX* gfx;

// Initialise the panel + backlight. Call once from setup().
void displayBegin();
