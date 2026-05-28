#!/usr/bin/env python3

# ####################################
# button_handler.py
#
# Button handler for two momentary pushbuttons.
# Button 1: GPIO 27 (Pin 13)
# Button 2: GPIO 26 (Pin 37)
#
# Edit the COMMANDS / DOUBLE_COMMANDS dicts below to set what each button does.
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
DEBOUNCE_MS = 50         # reject contact bounce; low enough a double-press still registers
DOUBLE_PRESS_MS = 500    # two presses within this window count as a double-press

# Single-press action per button (list for subprocess.Popen).
COMMANDS = {
    # Button 1: Safe shutdown
    BTN1_PIN: ['sudo', 'shutdown', '-h', 'now'],

    # Button 2 (single press): Reset — crash sound, then relaunch the emulator
    # via tty1 getty -> autologin -> ~/.profile -> launcher.
    BTN2_PIN: ['sudo', '/usr/local/bin/sheepshaver-restart.sh'],
}

# Double-press action. Buttons listed here distinguish single from double;
# others fire their single-press command immediately on press.
DOUBLE_COMMANDS = {
    # Button 2 (double press): Quit the emulator for good — no relaunch.
    BTN2_PIN: ['sudo', '/usr/local/bin/macintosh-quit.sh'],
}

# --- Main ---
last_trigger = {BTN1_PIN: 0.0, BTN2_PIN: 0.0}
pending = {}             # gpio -> True while a first press awaits a possible second
seq = {}                 # gpio -> token, so a superseded single-press timer no-ops
lock = threading.Lock()


def run(cmd):
    print(f'-> {cmd}', flush=True)
    subprocess.Popen(cmd)


def fire_single(gpio, token):
    # Runs the single-press command unless a second press superseded this timer.
    with lock:
        if not pending.get(gpio) or seq.get(gpio) != token:
            return
        pending[gpio] = False
    run(COMMANDS[gpio])


def on_press(chip, gpio, level, tick):
    # level: 0=falling (button down with pull-up), 1=rising, 2=watchdog timeout
    if level != 0:
        return
    now = time.monotonic()
    with lock:
        if (now - last_trigger[gpio]) <= (DEBOUNCE_MS / 1000):
            return
        last_trigger[gpio] = now

        # Buttons without a double-press action fire immediately.
        if gpio not in DOUBLE_COMMANDS:
            run(COMMANDS[gpio])
            return

        if pending.get(gpio):
            # Second press inside the window -> double-press.
            pending[gpio] = False
            run(DOUBLE_COMMANDS[gpio])
            return

        # First press -> wait briefly to see whether a second one follows.
        pending[gpio] = True
        token = seq.get(gpio, 0) + 1
        seq[gpio] = token

    threading.Timer(DOUBLE_PRESS_MS / 1000, fire_single, args=(gpio, token)).start()


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
