#include "ui.h"
#include <lvgl.h>
#include <Arduino.h>

#include "config.h"
#include "products.h"
#include "amazon_client.h"

// ---- screens / widgets -----------------------------------------------------
static lv_obj_t* scr_home;
static lv_obj_t* scr_status;
static lv_obj_t* status_title;
static lv_obj_t* status_msg;
static lv_obj_t* status_spinner;

// ---- deferred-work state ---------------------------------------------------
static int      pending_order = -1;   // product index queued by a tap
static bool     showing_result = false;
static uint32_t result_at = 0;

static void beep(bool ok) {
#if BUZZER_ENABLED
  tone(BUZZER_PIN, ok ? 1700 : 320, ok ? 70 : 200);
#endif
}

static void showHome() {
  showing_result = false;
  lv_scr_load(scr_home);
}

static void showBusy(const char* name) {
  lv_label_set_text(status_title, "Adding to cart");
  lv_label_set_text(status_msg, name);
  lv_obj_set_style_text_color(status_title, lv_color_white(), 0);
  lv_obj_clear_flag(status_spinner, LV_OBJ_FLAG_HIDDEN);
  lv_scr_load(scr_status);
  lv_refr_now(NULL);  // force the busy screen to paint before we block on Wi-Fi
}

static void showResult(OrderResult r, const char* name, const String& detail) {
  lv_obj_add_flag(status_spinner, LV_OBJ_FLAG_HIDDEN);

  lv_color_t color;
  const char* title;
  switch (r) {
    case ORDER_OK:
      title = LV_SYMBOL_OK "  Added";
      color = lv_palette_main(LV_PALETTE_GREEN);
      break;
    case ORDER_AUTH_EXPIRED:
      title = LV_SYMBOL_WARNING "  Sign-in needed";
      color = lv_palette_main(LV_PALETTE_AMBER);
      break;
    default:
      title = LV_SYMBOL_CLOSE "  Failed";
      color = lv_palette_main(LV_PALETTE_RED);
      break;
  }
  lv_label_set_text(status_title, title);
  lv_obj_set_style_text_color(status_title, color, 0);

  String msg = String(name);
  if (r == ORDER_OK) {
    msg += "\nOpen the Amazon app to check out.";
  } else if (r == ORDER_AUTH_EXPIRED) {
    msg += "\nRefresh the Amazon cookies in secrets.h.";
  } else {
    msg += "\n" + detail;
  }
  lv_label_set_text(status_msg, msg.c_str());

  beep(r == ORDER_OK);
  showing_result = true;
  result_at = millis();
}

// ---- events ----------------------------------------------------------------
static void tile_clicked(lv_event_t* e) {
  lv_obj_t* btn = lv_event_get_target(e);
  int idx = (int)(intptr_t)lv_obj_get_user_data(btn);
  if (idx < 0 || idx >= PRODUCT_COUNT) return;
  showBusy(PRODUCTS[idx].name);
  pending_order = idx;  // actual request runs in uiLoop()
}

static void back_clicked(lv_event_t* e) { showHome(); }

// ---- builders --------------------------------------------------------------
static lv_obj_t* makeTile(lv_obj_t* parent, const Product& p, int idx) {
  lv_obj_t* btn = lv_btn_create(parent);
  lv_obj_set_size(btn, 148, 118);
  lv_obj_set_style_radius(btn, 14, 0);
  lv_obj_set_user_data(btn, (void*)(intptr_t)idx);
  lv_obj_add_event_cb(btn, tile_clicked, LV_EVENT_CLICKED, NULL);

  lv_obj_t* sym = lv_label_create(btn);
  lv_label_set_text(sym, p.symbol);
  lv_obj_set_style_text_font(sym, &lv_font_montserrat_28, 0);
  lv_obj_align(sym, LV_ALIGN_TOP_MID, 0, 6);

  lv_obj_t* name = lv_label_create(btn);
  lv_label_set_text(name, p.name);
  lv_label_set_long_mode(name, LV_LABEL_LONG_WRAP);
  lv_obj_set_width(name, 134);
  lv_obj_set_style_text_align(name, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_text_font(name, &lv_font_montserrat_16, 0);
  lv_obj_align(name, LV_ALIGN_BOTTOM_MID, 0, -6);
  return btn;
}

static void buildHome() {
  scr_home = lv_obj_create(NULL);
  lv_obj_set_style_bg_color(scr_home, lv_color_hex(0x101418), 0);

  lv_obj_t* header = lv_label_create(scr_home);
  lv_label_set_text(header, "Pantry Reorder");
  lv_obj_set_style_text_color(header, lv_color_white(), 0);
  lv_obj_set_style_text_font(header, &lv_font_montserrat_20, 0);
  lv_obj_align(header, LV_ALIGN_TOP_MID, 0, 6);

  lv_obj_t* grid = lv_obj_create(scr_home);
  lv_obj_set_size(grid, SCREEN_WIDTH, SCREEN_HEIGHT - 36);
  lv_obj_align(grid, LV_ALIGN_BOTTOM_MID, 0, 0);
  lv_obj_set_style_bg_opa(grid, LV_OPA_TRANSP, 0);
  lv_obj_set_style_border_width(grid, 0, 0);
  lv_obj_set_flex_flow(grid, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(grid, LV_FLEX_ALIGN_SPACE_EVENLY,
                        LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

  for (int i = 0; i < PRODUCT_COUNT; i++) makeTile(grid, PRODUCTS[i], i);
}

static void buildStatus() {
  scr_status = lv_obj_create(NULL);
  lv_obj_set_style_bg_color(scr_status, lv_color_hex(0x101418), 0);

  status_spinner = lv_spinner_create(scr_status, 1000, 60);
  lv_obj_set_size(status_spinner, 64, 64);
  lv_obj_align(status_spinner, LV_ALIGN_TOP_MID, 0, 30);

  status_title = lv_label_create(scr_status);
  lv_obj_set_style_text_font(status_title, &lv_font_montserrat_28, 0);
  lv_obj_set_style_text_color(status_title, lv_color_white(), 0);
  lv_obj_align(status_title, LV_ALIGN_CENTER, 0, -10);

  status_msg = lv_label_create(scr_status);
  lv_label_set_long_mode(status_msg, LV_LABEL_LONG_WRAP);
  lv_obj_set_width(status_msg, SCREEN_WIDTH - 60);
  lv_obj_set_style_text_align(status_msg, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_text_font(status_msg, &lv_font_montserrat_16, 0);
  lv_obj_set_style_text_color(status_msg, lv_color_hex(0xC0C7CE), 0);
  lv_obj_align(status_msg, LV_ALIGN_CENTER, 0, 40);

  lv_obj_t* back = lv_btn_create(scr_status);
  lv_obj_set_size(back, 140, 48);
  lv_obj_align(back, LV_ALIGN_BOTTOM_MID, 0, -12);
  lv_obj_add_event_cb(back, back_clicked, LV_EVENT_CLICKED, NULL);
  lv_obj_t* bl = lv_label_create(back);
  lv_label_set_text(bl, LV_SYMBOL_LEFT "  Back");
  lv_obj_center(bl);
}

// ---- public ----------------------------------------------------------------
void uiInit() {
  buildHome();
  buildStatus();
  showHome();
}

void uiLoop() {
  if (pending_order >= 0) {
    int idx = pending_order;
    pending_order = -1;
    String detail;
    OrderResult r = addToCart(PRODUCTS[idx], &detail);
    showResult(r, PRODUCTS[idx].name, detail);
    return;
  }
  if (showing_result && millis() - result_at > CONFIRM_TIMEOUT_MS) {
    showHome();
  }
}
