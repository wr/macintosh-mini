// config.h — non-secret settings you'll tweak. Secrets (Wi-Fi password, Amazon
// session cookies) live in secrets.h, which is gitignored. Copy
// secrets.example.h -> secrets.h and fill it in.
//
// How it works: tapping a tile makes an HTTPS request to Amazon's add-to-cart
// endpoint, replaying YOUR logged-in session cookies, so the item lands in your
// real cart. You then open the Amazon app and tap Buy. No QR, no backend.
#pragma once

// ---------------------------------------------------------------------------
// Amazon storefront — must match the account your cookies belong to.
//   US "www.amazon.com"  UK "www.amazon.co.uk"  DE "www.amazon.de"
//   CA "www.amazon.ca"   JP "www.amazon.co.jp"  ...
// ---------------------------------------------------------------------------
#define AMAZON_HOST "www.amazon.com"

// ---------------------------------------------------------------------------
// Affiliate tag — KEEP EMPTY for this (personal, own-cart) mode.
// Amazon Associates forbids earning fees on your own purchases, so a direct-
// to-your-own-cart build must not carry a tag. The tag plumbing only exists
// for a separate share-with-others QR build. Leave "" here.
// ---------------------------------------------------------------------------
#define AFFILIATE_TAG ""

// ---------------------------------------------------------------------------
// Behaviour
// ---------------------------------------------------------------------------
#define HTTP_TIMEOUT_MS    12000  // per add-to-cart request
#define CONFIRM_TIMEOUT_MS 20000  // auto-return to the grid after showing a result
#define BUZZER_ENABLED     true   // short beep on tap (Elecrow Terminal has a buzzer)
#define BUZZER_PIN         3      // verify against your board's pinout

// UI grid layout on the 480x320 screen.
#define GRID_COLS 3
#define GRID_ROWS 2
