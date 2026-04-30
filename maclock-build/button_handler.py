#!/usr/bin/env python3

# ####################################
# button_handler.py
#
# Button handler for two momentary pushbuttons.
# Button 1: GPIO 27 (Pin 13)
# Button 2: GPIO 26 (Pin 37)
#
# Edit the COMMANDS dict below to set what each button does.
#
# March 26, 2026 - http://wells.ee/journal/macintosh-mini
# ####################################

import signal
import subprocess
import sys
import threading
import time

try:
    import lgpio
except ImportError:
    print('lgpio not found. Install: sudo apt-get install python3-lgpio')
    sys.exit(1)

# --- Config ---
BTN1_PIN = 27
BTN2_PIN = 26
DEBOUNCE_MS = 300

# Edit these commands to your shortcuts.
# Each value is a list suitable for subprocess.Popen().
COMMANDS = {
    # Button 1: Safe shutdown
    BTN1_PIN: ['sudo', 'shutdown', '-h', 'now'],

    # Button 2: Reset — plays the era-matched crash sound, then restarts
    # tty1 getty -> autologin -> ~/.profile -> sheepshaver.sh.
    BTN2_PIN: ['sudo', '/usr/local/bin/sheepshaver-restart.sh'],
}

# --- Main ---
last_trigger = {BTN1_PIN: 0.0, BTN2_PIN: 0.0}
lock = threading.Lock()

def on_press(chip, gpio, level, tick):
    # level: 0=falling (button down with pull-up), 1=rising, 2=watchdog timeout
    if level != 0:
        return
    now = time.monotonic()
    with lock:
        if (now - last_trigger[gpio]) <= (DEBOUNCE_MS / 1000):
            return
        last_trigger[gpio] = now
    cmd = COMMANDS[gpio]
    print(f'GPIO{gpio} pressed -> {cmd}', flush=True)
    subprocess.Popen(cmd)

def main():
    h = lgpio.gpiochip_open(0)
    # Claim with falling-edge alerts and pull-up
    lgpio.gpio_claim_alert(h, BTN1_PIN, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
    lgpio.gpio_claim_alert(h, BTN2_PIN, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)

    cb1 = lgpio.callback(h, BTN1_PIN, lgpio.FALLING_EDGE, on_press)
    cb2 = lgpio.callback(h, BTN2_PIN, lgpio.FALLING_EDGE, on_press)

    print(f'Button handler running. BTN1=GPIO{BTN1_PIN}, BTN2=GPIO{BTN2_PIN}', flush=True)

    stop = threading.Event()

    def cleanup(*_):
        stop.set()

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    try:
        stop.wait()
    finally:
        cb1.cancel()
        cb2.cancel()
        lgpio.gpiochip_close(h)

if __name__ == '__main__':
    main()
