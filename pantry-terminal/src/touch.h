// touch.h — capacitive touch read, mapped to screen pixels.
#pragma once
#include <Arduino.h>

void touchBegin();

// Returns true if a finger is down; writes screen-space coordinates to x,y.
bool touchRead(int16_t* x, int16_t* y);
