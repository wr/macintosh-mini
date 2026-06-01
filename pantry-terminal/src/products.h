// products.h — your pantry catalog. This is the other file you'll edit a lot.
//
// Each tile is one Product. Find a product's ASIN on its Amazon page (it's the
// 10-character code in the URL, e.g. amazon.com/dp/B0BXXXXXXX -> "B0BXXXXXXX",
// or under "Product details"). A Product can bundle up to MAX_ASINS items so a
// single tap can reorder a whole kit (e.g. detergent + dryer sheets).
//
// `symbol` is shown big on the tile. You can use any LVGL built-in symbol
// (LV_SYMBOL_*) or just a short text label — see ui.cpp for how it's drawn.
#pragma once
#include <stdint.h>

#define MAX_ASINS 3

struct CartItem {
  const char* asin;   // 10-char Amazon ASIN
  uint8_t     qty;    // how many to add
};

struct Product {
  const char* name;             // shown under the tile
  const char* symbol;           // big glyph/short text on the tile
  CartItem    items[MAX_ASINS]; // one or more ASINs added together
  uint8_t     count;            // how many entries in items[] are used
};

// ---------------------------------------------------------------------------
// EDIT ME: replace the placeholder ASINs (B000000000) with the real products
// you want to reorder. Keep `count` in sync with how many items you list.
// ---------------------------------------------------------------------------
static const Product PRODUCTS[] = {
  { "Toilet Paper",   "TP",  { {"B000000000", 1} }, 1 },
  { "Paper Towels",   "PT",  { {"B000000000", 1} }, 1 },
  { "Hand Soap",      "SOAP",{ {"B000000000", 2} }, 1 },
  { "Laundry Det.",   "LDY", { {"B000000000", 1} }, 1 },
  { "Dish Soap",      "DISH",{ {"B000000000", 1} }, 1 },
  // Example of a one-tap bundle (two ASINs ordered together):
  { "Trash + Liners", "BAG", { {"B000000000", 1}, {"B000000001", 1} }, 2 },
};

static const uint8_t PRODUCT_COUNT = sizeof(PRODUCTS) / sizeof(PRODUCTS[0]);
