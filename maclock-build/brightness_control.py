#!/usr/bin/env python3

# ####################################
# brightness_control.py
#
# Rotary encoder brightness control for Waveshare 2.8" DPI LCD.
# Encoder CLK on GPIO 11, DT on GPIO 10.
# Controls backlight via software PWM on GPIO 18.
#
# March 26, 2026 - http://wells.ee/journal/macintosh-mini
# ####################################

import signal
import sys
import time

try:
    import lgpio
except ImportError:
    print("lgpio not found. Install: sudo apt-get install python3-lgpio")
    sys.exit(1)

# --- Config ---
CLK_PIN = 11
DT_PIN = 10
BL_PIN = 18
PWM_FREQ = 10000
MIN_DUTY = 5
MAX_DUTY = 100
STEP = 20

brightness = MAX_DUTY
h = None


def set_backlight(duty):
    lgpio.tx_pwm(h, BL_PIN, PWM_FREQ, duty)


def cleanup(*_):
    if h is not None:
        lgpio.tx_pwm(h, BL_PIN, PWM_FREQ, MAX_DUTY)
        lgpio.gpiochip_close(h)
    sys.exit(0)


def main():
    global brightness, h

    h = lgpio.gpiochip_open(0)

    lgpio.gpio_claim_input(h, CLK_PIN, lgpio.SET_PULL_UP)
    lgpio.gpio_claim_input(h, DT_PIN, lgpio.SET_PULL_UP)

    set_backlight(brightness)
    print(f"Brightness control running. brightness={brightness}%", flush=True)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # Gray code state machine for robust encoder reading
    last_clk = lgpio.gpio_read(h, CLK_PIN)
    last_dt = lgpio.gpio_read(h, DT_PIN)
    last_encoded = (last_clk << 1) | last_dt
    encoder_val = 0

    # Lookup table for gray code transitions
    TRANSITION = [
         0, -1,  1,  0,
         1,  0,  0, -1,
        -1,  0,  0,  1,
         0,  1, -1,  0,
    ]

    try:
        while True:
            clk = lgpio.gpio_read(h, CLK_PIN)
            dt = lgpio.gpio_read(h, DT_PIN)
            encoded = (clk << 1) | dt
            if encoded != last_encoded:
                delta = TRANSITION[(last_encoded << 2) | encoded]
                encoder_val += delta

                # Full quadrature cycle per detent
                if encoder_val >= 4:
                    encoder_val = 0
                    brightness = min(MAX_DUTY, brightness + STEP)
                    set_backlight(brightness)
                    print(f"Brightness: {brightness}%", flush=True)
                elif encoder_val <= -4:
                    encoder_val = 0
                    brightness = max(MIN_DUTY, brightness - STEP)
                    set_backlight(brightness)
                    print(f"Brightness: {brightness}%", flush=True)

                last_encoded = encoded
            time.sleep(0.001)
    except Exception as e:
        print(f"Error: {e}", flush=True)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
