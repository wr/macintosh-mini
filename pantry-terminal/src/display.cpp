#include "display.h"
#include "board.h"

// 8-bit 8080 parallel bus -> ILI9488. If your Elecrow SKU is the SPI variant,
// replace this with the Arduino_ESP32SPI bus from Elecrow's demo instead.
static Arduino_DataBus* bus = new Arduino_ESP32LCD8(
    TFT_DC, TFT_CS, TFT_WR, TFT_RD,
    TFT_D0, TFT_D1, TFT_D2, TFT_D3,
    TFT_D4, TFT_D5, TFT_D6, TFT_D7);

// 18-bit color init is what these ILI9488 panels expect over parallel.
Arduino_GFX* gfx =
    new Arduino_ILI9488_18bit(bus, TFT_RST, SCREEN_ROTATION, false /* IPS */);

void displayBegin() {
  gfx->begin();
  gfx->fillScreen(BLACK);

#ifdef TFT_BL
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);  // backlight on
#endif
}
