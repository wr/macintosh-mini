// secrets.example.h — copy this to secrets.h (which is gitignored) and fill in.
//
//   cp src/secrets.example.h src/secrets.h
//
// secrets.h holds your Wi-Fi password and — importantly — your logged-in
// Amazon session cookies. Those cookies are effectively your Amazon login.
// Treat this file like a password: never commit it, never share a device dump.
#pragma once

// ---- Wi-Fi (required: direct add-to-cart needs the network) ----------------
#define WIFI_SSID     "your-ssid"
#define WIFI_PASSWORD "your-password"

// ---- Amazon session cookies ------------------------------------------------
// Paste the FULL cookie header from a browser that's logged into the same
// amazon.com account and storefront as AMAZON_HOST in config.h.
//
// How to grab it (desktop Chrome/Firefox):
//   1. Log into amazon.com with "Keep me signed in" checked.
//   2. Open DevTools -> Network tab, reload the Amazon home page.
//   3. Click the top document request -> Headers -> Request Headers.
//   4. Copy the entire value of the "cookie:" header.
//   5. Paste it below as one line. Escape any double-quotes as \".
//
// The important ones are session-id, ubid-main, x-main, at-main, sess-at-main,
// session-token. It's simplest to just paste everything verbatim.
//
// These rotate over time. When tiles start reporting "Session expired", repeat
// the steps above and re-flash (or update it via the device's config portal if
// you wire one up).
#define AMAZON_COOKIE "session-id=000-0000000-0000000; ubid-main=000-0000000-0000000; x-main=...; at-main=...; sess-at-main=\"...\"; session-token=..."
