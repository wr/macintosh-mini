#include "amazon_cart.h"
#include "config.h"

// Percent-encode anything that isn't an RFC 3986 unreserved character. ASINs
// and a well-formed tag are already URL-safe, but encoding keeps us honest if
// someone drops an unusual character into config.
static String urlEncode(const String& s) {
  static const char* hex = "0123456789ABCDEF";
  String out;
  out.reserve(s.length() * 3);
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    bool unreserved = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                      (c >= '0' && c <= '9') || c == '-' || c == '_' ||
                      c == '.' || c == '~';
    if (unreserved) {
      out += c;
    } else {
      out += '%';
      out += hex[(c >> 4) & 0xF];
      out += hex[c & 0xF];
    }
  }
  return out;
}

// Empty for personal/own-account use (the default). See config.h for why a tag
// must stay empty when adding to your own cart.
static String affiliateTag() {
  return String(AFFILIATE_TAG);
}

String buildCartUrl(const Product& product) {
  String url = "https://";
  url += AMAZON_HOST;
  url += "/gp/aws/cart/add.html";

  char sep = '?';
  String tag = affiliateTag();
  if (tag.length() > 0) {
    url += sep; sep = '&';
    url += "AssociateTag=";
    url += urlEncode(tag);
  }

  uint8_t n = product.count > MAX_ASINS ? MAX_ASINS : product.count;
  for (uint8_t i = 0; i < n; i++) {
    const CartItem& item = product.items[i];
    if (item.asin == nullptr || item.asin[0] == '\0') continue;
    int idx = i + 1;  // Amazon uses 1-based ASIN.1, Quantity.1, ...
    url += sep; sep = '&';
    url += "ASIN."; url += idx; url += '=';
    url += urlEncode(String(item.asin));
    url += "&Quantity."; url += idx; url += '=';
    url += (item.qty == 0 ? 1 : item.qty);
  }
  return url;
}
