# Pantry Reorder Terminal

A tiny touchscreen that lives in your pantry. Tap **Toilet Paper**, **Paper
Towels**, **Soap**, **Laundry Detergent**… and the item drops straight into your
real Amazon cart. Open the Amazon app, tap Buy, done.

Runs on an **ESP32-S3 + a small LVGL touchscreen** — no Raspberry Pi, no server
of your own, no cloud middleman.

## How it actually works (and the honest caveats)

There is **no official API for placing orders on a personal Amazon account.**
Amazon's Dash Replenishment is gated to appliance makers, the Product
Advertising API only builds links, and the Selling Partner / Business APIs are
for sellers and business accounts. So a personal "button that orders" has to
borrow your own logged-in session.

This project does that the simplest way that works:

1. You paste your **logged-in Amazon session cookies** into `secrets.h` once.
2. Tapping a tile makes an HTTPS request to Amazon's **add-to-cart endpoint**
   (`/gp/aws/cart/add.html`), replaying those cookies, so the item lands in
   **your** cart.
3. The screen shows ✓ / ✗ and beeps. You finish checkout from the Amazon app.

It deliberately stops at *add to cart*, not *place order* — adding to cart is
reliable; full headless checkout (addresses, payment, OTP/captcha) is not, and
one misfire there buys you the wrong thing.

> [!WARNING]
> Please read before building:
> - **Your Amazon login lives on the device.** The session cookies are
>   effectively your account. Don't put this on a device you don't physically
>   control, and don't share a flash dump.
> - **It's a gray area under Amazon's Terms of Service** and it's inherently
>   fragile. Amazon rotates session tokens and runs anti-bot checks; expect to
>   re-paste cookies every so often when tiles start saying *Sign-in needed*.
>   No guarantees it keeps working — treat it as a fun hack, not a product.
> - **No affiliate tag in this mode.** Amazon Associates forbids earning fees on
>   your own purchases, so adding to your own cart must run untagged
>   (`AFFILIATE_TAG ""`). The tag plumbing only exists for a separate
>   share-with-others build that hands the link off via QR instead.

## Hardware

- [Elecrow ESP32-S3 3.5" Terminal](https://www.elecrow.com/esp-terminal-3-5-inch-320-480-spi-tft-capacitive-touch-display-with-ov2640-camera.html)
  — 480×320, ILI9488, FT6236 capacitive touch, LVGL-certified, Wi-Fi + buzzer.
  Any ESP32-S3 + LVGL touchscreen works; you'll just adjust the pins.
- A USB-C cable and a Wi-Fi network.

## Build

Uses [PlatformIO](https://platformio.org/).

1. Copy the secrets template and fill it in:
   ```bash
   cp src/secrets.example.h src/secrets.h
   ```
   Set `WIFI_SSID` / `WIFI_PASSWORD`, then paste your Amazon cookies (next
   section).
2. Edit `src/products.h` — replace the placeholder `B000000000` ASINs with the
   real products you reorder. Make sure `AMAZON_HOST` in `src/config.h` matches
   your storefront (`www.amazon.com`, `www.amazon.co.uk`, …).
3. Flash it:
   ```bash
   pio run -t upload && pio device monitor
   ```

### Getting your Amazon cookies

On a desktop browser logged into the **same** Amazon account/storefront:

1. Log in with **"Keep me signed in"** checked.
2. Open **DevTools → Network**, reload the Amazon home page.
3. Click the top document request → **Headers → Request Headers**.
4. Copy the entire value of the **`cookie:`** header.
5. Paste it into `AMAZON_COOKIE` in `src/secrets.h` (escape any `"` as `\"`).

When tiles start reporting **Sign-in needed**, repeat these steps and re-flash.

### Finding an ASIN

It's the 10-character code in any product URL —
`amazon.com/dp/`**`B0XXXXXXXX`** — or under "Product details" on the listing.
A single tile can bundle several ASINs (see the `Trash + Liners` example in
`products.h`) so one tap reorders a kit.

## Customising

| What | Where |
|------|-------|
| Items / tiles / quantities | `src/products.h` |
| Storefront, timeouts, buzzer, grid size | `src/config.h` |
| Wi-Fi + Amazon cookies (gitignored) | `src/secrets.h` |
| Display & touch pins | `src/board.h` |

## Project layout

```
src/
  main.cpp          LVGL + display/touch wiring, the loop
  ui.cpp / ui.h     the home grid + "adding…/result" screen
  amazon_client.*   the authenticated add-to-cart HTTPS request
  amazon_cart.*     builds the /gp/aws/cart/add.html URL
  products.h        YOUR catalog (edit me)
  config.h          non-secret settings
  secrets.example.h template -> copy to secrets.h
  board.h           all board-specific pins
  display.cpp/.h    Arduino_GFX panel bring-up
  touch.cpp/.h      FT6236 capacitive touch + coordinate mapping
  lv_conf.h         minimal LVGL config
```

## Troubleshooting

- **Black screen / garbled colors** — wrong panel pins for your SKU. Copy the
  `Arduino_GFX` constructor from Elecrow's official LVGL demo for your exact
  board into `src/display.cpp`, and try toggling `COLOR_SWAP` (board.h) +
  `LV_COLOR_16_SWAP` (lv_conf.h) together.
- **Taps land in the wrong place** — set `TOUCH_DEBUG 1` in `touch.cpp`, watch
  the serial monitor, and adjust `TOUCH_SWAP_XY` / `TOUCH_INVERT_X` /
  `TOUCH_INVERT_Y` in `board.h`.
- **Every tap says "Sign-in needed"** — cookies expired or are from a different
  storefront. Re-grab them and confirm `AMAZON_HOST` matches.
- **"Failed / HTTP 4xx"** — Amazon changed/blocked the request, or the ASIN is
  unavailable in your region. This is the fragile part; the QR-handoff approach
  is the robust fallback if you'd rather not chase it.

---

Part of the [macintosh-mini](../) project. Personal, non-commercial use; not
affiliated with or endorsed by Amazon.
