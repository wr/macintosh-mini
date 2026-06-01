// amazon_client.h — performs the authenticated add-to-cart request.
#pragma once
#include <Arduino.h>
#include "products.h"

enum OrderResult {
  ORDER_OK,           // item(s) added to your cart
  ORDER_AUTH_EXPIRED, // request hit a sign-in wall -> refresh cookies
  ORDER_NET_ERROR,    // Wi-Fi/TLS/connection failure
  ORDER_HTTP_ERROR,   // unexpected HTTP status from Amazon
};

// Connects to Wi-Fi if needed and adds the product to your Amazon cart by
// replaying the stored session cookies. Blocking; expected to take a couple of
// seconds. `detail` (optional) receives a short human-readable status.
OrderResult addToCart(const Product& product, String* detail = nullptr);

// Kick off Wi-Fi early (called from setup) so the first tap is snappy.
void amazonClientBegin();
