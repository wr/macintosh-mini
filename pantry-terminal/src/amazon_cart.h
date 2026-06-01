// amazon_cart.h — turns a Product into an Amazon "add to cart" URL.
#pragma once
#include <Arduino.h>
#include "products.h"

// Builds a URL of the form:
//   https://HOST/gp/aws/cart/add.html?AssociateTag=TAG&ASIN.1=..&Quantity.1=..
// The AssociateTag parameter is omitted entirely when no tag is configured.
// Scanning/opening the result lands on Amazon with the item(s) in the cart.
String buildCartUrl(const Product& product);
