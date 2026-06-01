#include "amazon_client.h"
#include "amazon_cart.h"
#include "config.h"
#include "secrets.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// A desktop-ish UA — Amazon's add-to-cart path behaves better than with the
// default ESP32 UA. This is the same string a normal browser would send.
static const char* USER_AGENT =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36";

static bool ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(200);
  }
  return WiFi.status() == WL_CONNECTED;
}

void amazonClientBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

// Read up to `max` bytes of the response so we can sniff for a sign-in wall
// without pulling Amazon's (huge) cart page fully into RAM.
static String peekBody(HTTPClient& http, size_t max = 6144) {
  String out;
  out.reserve(max);
  WiFiClient* stream = http.getStreamPtr();
  uint32_t start = millis();
  while (out.length() < max && (http.connected() || stream->available()) &&
         millis() - start < HTTP_TIMEOUT_MS) {
    while (stream->available() && out.length() < max) {
      out += (char)stream->read();
    }
    if (out.length() < max) delay(5);
  }
  return out;
}

// True if the response looks like Amazon bounced us to a login page, meaning
// the stored cookies have expired or been invalidated.
static bool looksLikeSignIn(const String& url, const String& body) {
  if (url.indexOf("/ap/signin") >= 0) return true;
  if (body.indexOf("ap/signin") >= 0) return true;
  if (body.indexOf("nav-signin") >= 0) return true;     // signed-out nav
  if (body.indexOf("Sign in for the best experience") >= 0) return true;
  return false;
}

OrderResult addToCart(const Product& product, String* detail) {
  if (!ensureWifi()) {
    if (detail) *detail = "No Wi-Fi";
    return ORDER_NET_ERROR;
  }

  String url = buildCartUrl(product);

  WiFiClientSecure client;
  // NOTE: we skip TLS certificate validation for simplicity. On a trusted home
  // network the practical risk is low, but to harden against MITM, paste the
  // "Amazon Root CA 1" PEM and call client.setCACert(...) instead.
  client.setInsecure();

  HTTPClient http;
  http.setReuse(false);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setFollowRedirects(HTTPC_FORCE_FOLLOW_REDIRECTS);
  if (!http.begin(client, url)) {
    if (detail) *detail = "Connect failed";
    return ORDER_NET_ERROR;
  }

  http.addHeader("Cookie", AMAZON_COOKIE);
  http.addHeader("User-Agent", USER_AGENT);
  http.addHeader("Accept", "text/html,application/xhtml+xml");
  http.addHeader("Accept-Language", "en-US,en;q=0.9");

  int code = http.GET();
  if (code <= 0) {
    if (detail) *detail = String("Net err ") + code;
    http.end();
    return ORDER_NET_ERROR;
  }

  String finalUrl = http.getLocation();
  if (finalUrl.length() == 0) finalUrl = url;
  String body = peekBody(http);
  http.end();

  if (looksLikeSignIn(finalUrl, body)) {
    if (detail) *detail = "Session expired";
    return ORDER_AUTH_EXPIRED;
  }

  if (code >= 200 && code < 400) {
    if (detail) *detail = "Added to cart";
    return ORDER_OK;
  }

  if (detail) *detail = String("HTTP ") + code;
  return ORDER_HTTP_ERROR;
}
