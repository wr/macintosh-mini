#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# audio_gate.py
#
# Lets go of the speaker's audio pin (GPIO 19) while nothing is playing.
#
# The Pi's audio is PWM on GPIO 19, and the PWM runs whether or not anything
# plays: with no sound it sits at half duty, and noise on the Pi's 3.3 V rides
# through it into the amp. On rev 2026.09 boards that is hiss, the setup
# hotspot's ticking, and the burble on battery. With the pin let go (input, no
# pull) the speaker goes quiet. Letting go clicks faintly; taking the pin back
# is silent, because the filter after the pin holds its level meanwhile.
# Driving the pin low instead pops loudly both ways.
#
# Every player goes through the ALSA plugin in audio_gate_plugin.c (see
# /etc/asound.conf), which sends a byte to /run/audio-gate.sock whenever it's
# handed sound. Players write ahead of the hardware, so the pin is back before
# the sound gets there. HOLD_S without a byte lets it go again.
#
# October 26, 2026 - https://wells.ee/projects/macintosh-mini/
# ####################################

import os
import select
import signal
import socket
import subprocess
import sys
import time

PIN = 19
SOCKET = '/run/audio-gate.sock'
ASOUND_CONF = '/etc/asound.conf'
CONNECT = ['a5']        # PWM1, as the audremap-pin19 overlay sets it
LET_GO = ['ip', 'pn']   # input with no pull: a pull would drain the filter and pop

# After a sound, wait this long before letting go. Each let-go clicks faintly,
# so a burst of alerts shouldn't click between every one.
HOLD_S = 3.0

POLL_S = 0.25


class Gate:
    """When the pin should be connected. Starts connected, so a sound already
    playing when this starts isn't cut off."""

    def __init__(self, now, hold_s=HOLD_S):
        self.hold_s = hold_s
        self.connected = True
        self.last_sound = now

    def heard(self, now):
        """A player was handed sound. Returns 'connect' or None."""
        self.last_sound = now
        if self.connected:
            return None
        self.connected = True
        return 'connect'

    def tick(self, now):
        """Time passed. Returns 'let go' or None."""
        if self.connected and now - self.last_sound >= self.hold_s:
            self.connected = False
            return 'let go'
        return None


def set_pin(action):
    mode = CONNECT if action == 'connect' else LET_GO
    subprocess.run(['pinctrl', 'set', str(PIN)] + mode, check=False)


def routed(path=ASOUND_CONF):
    """True while asound.conf sends players through the plugin. Without it
    nothing would take the pin back after letting go, and the Mac would be
    mute."""
    try:
        with open(path) as f:
            return 'audiogate' in f.read()
    except OSError:
        return False


def listen():
    # audio-gate.socket hands the socket over as fd 3 (sd_listen_fds). By hand,
    # bind it here.
    if os.environ.get('LISTEN_PID') == str(os.getpid()) and os.environ.get('LISTEN_FDS') == '1':
        return socket.socket(fileno=3)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        os.unlink(SOCKET)
    except FileNotFoundError:
        pass
    sock.bind(SOCKET)
    return sock


def drain(sock):
    """Read every queued byte; True if there were any."""
    got = False
    while True:
        try:
            sock.recv(64, socket.MSG_DONTWAIT)
        except BlockingIOError:
            return got
        got = True


def main():
    sock = listen()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    gate = Gate(time.monotonic())
    set_pin('connect')
    try:
        while True:
            readable, _, _ = select.select([sock], [], [], POLL_S)
            now = time.monotonic()
            action = gate.heard(now) if readable and drain(sock) else gate.tick(now)
            if action == 'let go' and not routed():
                gate.heard(now)   # stay connected; ask again after another hold
                continue
            if action:
                set_pin(action)
    finally:
        # Stopped or crashed: leave the speaker connected, as without this.
        set_pin('connect')


if __name__ == '__main__':
    main()
