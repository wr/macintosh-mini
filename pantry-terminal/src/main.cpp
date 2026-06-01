#include <Arduino.h>
#include <lvgl.h>

#include "board.h"
#include "display.h"
#include "touch.h"
#include "ui.h"
#include "amazon_client.h"

// LVGL draw buffer — a few dozen lines tall is plenty and fits internal RAM.
#define DRAW_BUF_LINES 48
static lv_disp_draw_buf_t draw_buf;
static lv_color_t* buf1;

static void disp_flush(lv_disp_drv_t* drv, const lv_area_t* area,
                       lv_color_t* color_p) {
  uint32_t w = area->x2 - area->x1 + 1;
  uint32_t h = area->y2 - area->y1 + 1;
  gfx->draw16bitRGBBitmap(area->x1, area->y1, (uint16_t*)color_p, w, h);
  lv_disp_flush_ready(drv);
}

static void touch_read(lv_indev_drv_t* drv, lv_indev_data_t* data) {
  int16_t x, y;
  if (touchRead(&x, &y)) {
    data->state = LV_INDEV_STATE_PRESSED;
    data->point.x = x;
    data->point.y = y;
  } else {
    data->state = LV_INDEV_STATE_RELEASED;
  }
}

void setup() {
  Serial.begin(115200);

  displayBegin();
  touchBegin();
  lv_init();

  size_t buf_px = SCREEN_WIDTH * DRAW_BUF_LINES;
  buf1 = (lv_color_t*)heap_caps_malloc(buf_px * sizeof(lv_color_t),
                                       MALLOC_CAP_DMA);
  if (!buf1) buf1 = (lv_color_t*)malloc(buf_px * sizeof(lv_color_t));
  lv_disp_draw_buf_init(&draw_buf, buf1, NULL, buf_px);

  static lv_disp_drv_t disp_drv;
  lv_disp_drv_init(&disp_drv);
  disp_drv.hor_res = SCREEN_WIDTH;
  disp_drv.ver_res = SCREEN_HEIGHT;
  disp_drv.flush_cb = disp_flush;
  disp_drv.draw_buf = &draw_buf;
  lv_disp_drv_register(&disp_drv);

  static lv_indev_drv_t indev_drv;
  lv_indev_drv_init(&indev_drv);
  indev_drv.type = LV_INDEV_TYPE_POINTER;
  indev_drv.read_cb = touch_read;
  lv_indev_drv_register(&indev_drv);

  uiInit();
  amazonClientBegin();  // start associating to Wi-Fi so the first tap is quick
}

void loop() {
  lv_timer_handler();
  uiLoop();
  delay(5);
}
