#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# button_handler.py
#
# Button handler for two momentary pushbuttons.
# Button 1: GPIO 27 (Pin 13)
# Button 2: GPIO 26 (Pin 37)
#
# Edit the COMMANDS / DOUBLE_COMMANDS / HOLD_COMMANDS dicts below to set what
# each button does.
#
# March 26, 2026 - https://github.com/wr/macintosh-mini/blob/main/BUILD.md
# ####################################

import os
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
HOLD_S = 10.0            # holding a button this long counts as a hold
POLL_S = 0.025           # how often a held button is checked for its release

# Single-press action per button (list for subprocess.Popen).
COMMANDS = {
    # Button 1: Safe shutdown
    BTN1_PIN: ['sudo', 'shutdown', '-h', 'now'],

    # Button 2 (single press): Reset — crash sound, then relaunch the emulator
    # via tty1 getty -> autologin -> ~/.profile -> launcher.
    BTN2_PIN: ['sudo', '/usr/local/bin/sheepshaver-restart.sh'],
}

# Double-press action. Buttons listed here (or in HOLD_COMMANDS) distinguish
# single from double; others fire their single-press command immediately on
# press.
DOUBLE_COMMANDS = {
    # Button 2 (double press): Quit the emulator for good — no relaunch.
    BTN2_PIN: ['sudo', '/usr/local/bin/macintosh-quit.sh'],
}

# Hold action, after HOLD_S seconds held down. Releasing earlier is a single
# press. Button 1 has none on purpose: holding a power button is everyone's
# way of forcing a computer off, so it shuts down as soon as it is pressed.
HOLD_COMMANDS = {
    # Button 2 (hold): Wi-Fi setup — quit Mac OS and offer the setup hotspot.
    BTN2_PIN: ['/usr/local/bin/mac-setup', 'request'],
}

# While Wi-Fi setup is on screen, a press of button 2 cancels it instead.
SETUP_REQUESTED = '/run/mac-setup/requested'
SETUP_CANCEL = ['/usr/local/bin/mac-setup', 'cancel']


class ButtonLogic:
    """Turns press and release times into single / double / hold actions.

    Each method returns a list of (gpio, action) pairs, action being 'single',
    'double' or 'hold'. No GPIO here, so it can be tested with made-up times.
    """

    def __init__(self):
        self.last_press = {}
        self.down = {}
        self.down_at = {}
        self.pending = {}    # gpio -> time of a first press still being decided
        self.done = {}       # gpio -> True once this press has fired its action

    def press(self, gpio, now):
        if now - self.last_press.get(gpio, -1e9) <= DEBOUNCE_MS / 1000:
            return []
        self.last_press[gpio] = now
        self.down[gpio] = True
        self.down_at[gpio] = now

        # Buttons without a double-press or hold action fire immediately.
        if gpio not in DOUBLE_COMMANDS and gpio not in HOLD_COMMANDS:
            return [(gpio, 'single')]

        first = self.pending.get(gpio)
        if first is not None and now - first <= DOUBLE_PRESS_MS / 1000 \
                and gpio in DOUBLE_COMMANDS:
            # Second press inside the window -> double-press.
            self.pending[gpio] = None
            self.done[gpio] = True
            return [(gpio, 'double')]

        # First press -> wait to see whether a second press or a hold follows.
        self.pending[gpio] = now
        self.done[gpio] = False
        return []

    def release(self, gpio, now):
        self.down[gpio] = False
        first = self.pending.get(gpio)
        if first is None or self.done.get(gpio):
            return []
        if now - first < DOUBLE_PRESS_MS / 1000:
            return []    # still inside the window: tick() decides
        # Held past the window but let go before HOLD_S -> single press.
        self.pending[gpio] = None
        self.done[gpio] = True
        return [(gpio, 'single')]

    def tick(self, now):
        actions = []
        for gpio, first in list(self.pending.items()):
            if first is None or self.done.get(gpio):
                continue
            if self.down.get(gpio):
                if gpio in HOLD_COMMANDS and now - self.down_at[gpio] >= HOLD_S:
                    self.pending[gpio] = None
                    self.done[gpio] = True
                    actions.append((gpio, 'hold'))
            elif now - first >= DOUBLE_PRESS_MS / 1000:
                self.pending[gpio] = None
                self.done[gpio] = True
                actions.append((gpio, 'single'))
        return actions


def command_for(gpio, action, setup_requested):
    if action == 'hold':
        return HOLD_COMMANDS[gpio]
    if action == 'double':
        return DOUBLE_COMMANDS[gpio]
    if gpio == BTN2_PIN and setup_requested:
        return SETUP_CANCEL
    return COMMANDS[gpio]


# --- Main ---
lock = threading.Lock()


def run(cmd):
    print(f'-> {cmd}', flush=True)
    try:
        subprocess.Popen(cmd)
    except OSError as e:   # e.g. no mac-setup on a Maclock-only install
        print(f'   failed: {e}', flush=True)


def dispatch(actions):
    for gpio, action in actions:
        run(command_for(gpio, action, os.path.exists(SETUP_REQUESTED)))


def main():
    h = lgpio.gpiochip_open(0)
    logic = ButtonLogic()

    def on_press(chip, gpio, level, tick):
        # level: 0=falling (button down with pull-up), 1=rising, 2=watchdog timeout
        if level != 0:
            return
        with lock:
            actions = logic.press(gpio, time.monotonic())
        dispatch(actions)

    # Claim with falling-edge alerts and pull-up
    lgpio.gpio_claim_alert(h, BTN1_PIN, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
    lgpio.gpio_claim_alert(h, BTN2_PIN, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)

    cb1 = lgpio.callback(h, BTN1_PIN, lgpio.FALLING_EDGE, on_press)
    cb2 = lgpio.callback(h, BTN2_PIN, lgpio.FALLING_EDGE, on_press)

    print(f'Button handler running. BTN1=GPIO{BTN1_PIN}, BTN2=GPIO{BTN2_PIN}', flush=True)

    stop = threading.Event()

    def poll():
        # Releases are read from the pin rather than from rising edges: a
        # release only counts once the pin has read "up" twice in a row, so
        # contact bounce on the way down can't end a hold early.
        ups = {}
        while not stop.wait(POLL_S):
            now = time.monotonic()
            actions = []
            with lock:
                for gpio, is_down in list(logic.down.items()):
                    if not is_down:
                        continue
                    if lgpio.gpio_read(h, gpio) == 1:
                        ups[gpio] = ups.get(gpio, 0) + 1
                        if ups[gpio] >= 2:
                            ups[gpio] = 0
                            actions += logic.release(gpio, now)
                    else:
                        ups[gpio] = 0
                actions += logic.tick(now)
            dispatch(actions)

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()

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
