#include "touch.h"
#include "board.h"
#include <Wire.h>

// Set to 1 to print raw touch coordinates to Serial while calibrating the
// TOUCH_* knobs in board.h.
#define TOUCH_DEBUG 0

void touchBegin() {
  Wire.begin(TOUCH_SDA, TOUCH_SCL);
  Wire.setClock(400000);
#if TOUCH_RST >= 0
  pinMode(TOUCH_RST, OUTPUT);
  digitalWrite(TOUCH_RST, LOW);
  delay(10);
  digitalWrite(TOUCH_RST, HIGH);
  delay(50);
#endif
}

// Read FT6x36 registers 0x02 (touch count) and 0x03..0x06 (X/Y hi+lo of point 1).
static bool readRaw(uint16_t* rx, uint16_t* ry) {
  Wire.beginTransmission(TOUCH_I2C_ADDR);
  Wire.write(0x02);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(TOUCH_I2C_ADDR, 5) != 5) return false;

  uint8_t touches = Wire.read() & 0x0F;
  uint8_t xh = Wire.read();
  uint8_t xl = Wire.read();
  uint8_t yh = Wire.read();
  uint8_t yl = Wire.read();
  if (touches == 0 || touches > 2) return false;

  *rx = ((xh & 0x0F) << 8) | xl;
  *ry = ((yh & 0x0F) << 8) | yl;
  return true;
}

bool touchRead(int16_t* x, int16_t* y) {
  uint16_t rx, ry;
  if (!readRaw(&rx, &ry)) return false;

#if TOUCH_DEBUG
  Serial.printf("raw touch  x=%u  y=%u\n", rx, ry);
#endif

  // Map raw panel coordinates -> screen pixels per the knobs in board.h.
  long sx, sy;
  if (TOUCH_SWAP_XY) {
    sx = (long)ry * SCREEN_WIDTH / TOUCH_RAW_MAX_Y;
    sy = (long)rx * SCREEN_HEIGHT / TOUCH_RAW_MAX_X;
  } else {
    sx = (long)rx * SCREEN_WIDTH / TOUCH_RAW_MAX_X;
    sy = (long)ry * SCREEN_HEIGHT / TOUCH_RAW_MAX_Y;
  }
  if (TOUCH_INVERT_X) sx = SCREEN_WIDTH - 1 - sx;
  if (TOUCH_INVERT_Y) sy = SCREEN_HEIGHT - 1 - sy;

  *x = constrain(sx, 0, SCREEN_WIDTH - 1);
  *y = constrain(sy, 0, SCREEN_HEIGHT - 1);
  return true;
}
