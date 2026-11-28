#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# brightness_control.py
#
# Rotary encoder brightness control for Waveshare 2.8" DPI LCD.
# Encoder CLK on GPIO 11, DT on GPIO 10.
# Controls backlight via the kernel pwm-gpio driver on GPIO 18.
#
# March 26, 2026 - https://wells.ee/projects/macintosh-mini/
# ####################################

import os
import signal
import socket
import sys
import time
import traceback
from datetime import datetime

import night_schedule
from night_schedule import (  # noqa: F401 - also used through this module
    read_zone_tab, sun_times, system_timezone, zone_coords)

try:
    import lgpio
except ImportError:
    print("lgpio not found. Install: sudo apt-get install python3-lgpio")
    sys.exit(1)

# --- Config ---
CLK_PIN = 11
DT_PIN = 10
PWM_PERIOD_NS = 1_000_000  # 1 kHz

# Gamma compresses the dark end hard: a plain mapping asks for a 39 ns pulse
# at level 1. The driver accepts that, but nothing can hold a pulse so short
# repeatably, so the bottom of the dial is floored to something a timer can
# actually produce. Level 0 still goes fully dark.
MIN_PULSE_NS = 20_000

# Sampling the pins beats reacting to every edge. The encoder bounces hard —
# one turn throws hundreds of transitions — and a 1 ms sample steps over the
# chatter. Decoding every edge instead, as the kernel rotary-encoder driver
# does, gets the direction wrong on about one turn in five.
POLL_S = 0.001

# The dial gets flicked through an arc rather than clicked detent by detent,
# so brightness follows how far it turned. DEADBAND drops the odd stray count;
# reversing needs a longer run than continuing, so a flick holds the direction
# it started in.
LEVEL_PER_COUNT = 4
DIAL_DIRECTION = -1    # clockwise brightens, as on a compact Mac
DEADBAND = 1
REVERSE_DEADBAND = 4
IDLE_RESET_S = 0.4

# Ease into a new level over a few milliseconds. A flick only lands 8 to 10
# counts, so without this the backlight arrives in visible steps.
RAMP_PER_TICK = 1.0

# Perceived brightness is roughly the square of the duty cycle, so map the
# dial through a curve. Without it most of the arc is spent up at the bright
# end, where the eye can barely tell the difference.
GAMMA = 2.2

PWM_SYSFS = "/sys/class/pwm"
PWM_DEVICE = "pwm_gpio@12"  # dtoverlay=pwm-gpio,gpio=18 — 0x12 is GPIO 18

# Gray code transitions, indexed by the previous state and the current one
TRANSITION = [
     0, -1,  1,  0,
     1,  0,  0, -1,
    -1,  0,  0,  1,
     0,  1, -1,  0,
]

level = 100    # dial position, 0-100
h = None
pwm_dir = None
failed = False
cleaning = False


# --- Night dimming ---
# Off unless /etc/default/brightness-control turns it on. night_schedule.py
# describes the file and holds the schedule. Scheduled changes move the dial's
# level, so the dial still works from wherever the schedule left it.
NIGHT_FADE_S = 30      # scheduled changes ease in over this long
NIGHT_CHECK_S = 0.5    # how often the schedule and its settings are checked

# The Zero has no clock battery, so until NTP answers the time is whatever
# fake-hwclock saved at the last shutdown. Dimming on that would be a guess,
# so the schedule waits for timesyncd to raise this flag.
CLOCK_SYNCED_FLAG = "/run/systemd/timesync/synchronized"

# --- For other programs ---
# The level, kept in a file anyone may read, and a socket anyone may send a
# level to (2-100, as text), as if the dial had turned. mini-link uses both
# for Mac OS's brightness slider.
RUN_DIR = "/run/brightness-control"
LEVEL_FILE = "level"
LEVEL_SOCKET = "level.sock"
CONTROL_POLL_S = 0.02


def write(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def clock_synced():
    return os.path.exists(CLOCK_SYNCED_FLAG)


class NightSettings:
    """Night dimming's settings, read again whenever the file changes, and
    the place sunset and sunrise are worked out for, looked up again whenever
    the time zone changes."""

    def __init__(self, path=night_schedule.CONFIG, zone_tab=None):
        self.path = path
        self.zone_tab = read_zone_tab() if zone_tab is None else zone_tab
        self.stamp = ()
        self.zone = None
        self.cfg = night_schedule.NightConfig()
        self.coords = None

    def refresh(self, zone=None):
        """True when the settings or the time zone changed since last time."""
        changed = False
        try:
            st = os.stat(self.path)
            stamp = (st.st_mtime_ns, st.st_ino, st.st_size)
        except OSError:
            stamp = None
        if stamp != self.stamp:
            self.stamp = stamp
            try:
                cfg = night_schedule.load_config(self.path)
            except (OSError, ValueError) as e:
                # A typo here must not take the dial down in a restart loop
                print(f"Bad value in night config ({e}); night dimming off", flush=True)
                cfg = night_schedule.NightConfig()
            changed = cfg != self.cfg
            self.cfg = cfg
        zone = zone or system_timezone()
        if zone != self.zone:
            self.zone = zone
            changed = True
        if changed:
            self.coords = night_schedule.place(self.cfg, self.zone, self.zone_tab)
        return changed


def parse_level(data):
    """A level sent to the socket: 2 to 100 as text, or None."""
    text = data.strip()
    if not 1 <= len(text) <= 3 or not text.isdigit():
        return None
    value = int(text)
    return value if 2 <= value <= 100 else None


def open_control(run_dir=RUN_DIR):
    """The socket other programs send a level to, or None if it can't be made."""
    path = os.path.join(run_dir, LEVEL_SOCKET)
    try:
        os.makedirs(run_dir, mode=0o755, exist_ok=True)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(path)
        os.chmod(path, 0o666)
        sock.setblocking(False)
        return sock
    except OSError as e:
        print(f"No level socket ({e}); the dial still works", flush=True)
        return None


def read_control(sock):
    """The newest level waiting on the socket, or None."""
    newest = None
    for _ in range(32):     # a flood of them must not hold up the dial
        try:
            data = sock.recv(16)
        except OSError:
            break
        value = parse_level(data)
        if value is not None:
            newest = value
    return newest


def publish_level(value, run_dir=RUN_DIR):
    path = os.path.join(run_dir, LEVEL_FILE)
    try:
        write(path + ".new", value)
        os.replace(path + ".new", path)
    except OSError:
        pass


def find_pwmchip(timeout=30):
    """Locate the pwmchip backed by the pwm-gpio driver, not the PWM peripheral.

    The peripheral (3f20c000.pwm) is owned by the analogue audio firmware, so
    the backlight must use the software chip. Chip numbering is not stable, so
    match on the backing device instead of assuming pwmchip0.

    This service starts before the driver probes, so wait for it to appear.
    """
    deadline = time.monotonic() + timeout
    while True:
        for chip in sorted(os.listdir(PWM_SYSFS)):
            device = os.path.realpath(os.path.join(PWM_SYSFS, chip, "device"))
            if os.path.basename(device) == PWM_DEVICE:
                return os.path.join(PWM_SYSFS, chip)
        if time.monotonic() > deadline:
            return None
        time.sleep(0.2)


def open_backlight():
    """Export PWM channel 0 and return its sysfs directory."""
    chip = find_pwmchip()
    if chip is None:
        print(f"No {PWM_DEVICE} pwmchip found. Is dtoverlay=pwm-gpio,gpio=18 "
              "in /boot/firmware/config.txt?", flush=True)
        sys.exit(1)

    channel = os.path.join(chip, "pwm0")
    if not os.path.isdir(channel):
        write(os.path.join(chip, "export"), 0)

    # udev creates the attributes a moment after export
    for _ in range(50):
        if os.access(os.path.join(channel, "duty_cycle"), os.W_OK):
            break
        time.sleep(0.1)
    else:
        print(f"Timed out waiting for {channel}", flush=True)
        sys.exit(1)

    # Duty must never exceed period, so zero it before changing the period
    write(os.path.join(channel, "duty_cycle"), 0)
    write(os.path.join(channel, "period"), PWM_PERIOD_NS)
    write(os.path.join(channel, "enable"), 1)
    return channel


def duty_for(dial):
    """Map a dial position to a duty cycle in nanoseconds."""
    if dial <= 0:
        return 0
    span = PWM_PERIOD_NS - MIN_PULSE_NS
    return int(MIN_PULSE_NS + span * (dial / 100.0) ** GAMMA)


def set_backlight(dial):
    write(os.path.join(pwm_dir, "duty_cycle"), duty_for(dial))


def cleanup(*_):
    # Reachable twice on SIGTERM: once from the handler, then again from the
    # finally block as SystemExit unwinds. Only the first pass should run.
    global cleaning
    if cleaning:
        return
    cleaning = True

    # Stopping at a low level would hand back a dark screen, so leave it lit.
    if pwm_dir is not None:
        set_backlight(100)
    if h is not None:
        lgpio.gpiochip_close(h)
    sys.exit(1 if failed else 0)


def main():
    global level, h, pwm_dir, failed

    pwm_dir = open_backlight()
    set_backlight(level)

    h = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(h, CLK_PIN, lgpio.SET_PULL_UP)
    lgpio.gpio_claim_input(h, DT_PIN, lgpio.SET_PULL_UP)

    settings = NightSettings()
    schedule = night_schedule.Schedule()
    settings_changed = settings.refresh()
    control = open_control()
    publish_level(level)
    published = level
    print(f"Brightness control running. level={level} "
          f"night={'on' if settings.cfg.on else 'off'}", flush=True)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    encoded = (lgpio.gpio_read(h, CLK_PIN) << 1) | lgpio.gpio_read(h, DT_PIN)
    accum = 0
    last_dir = 0
    last_move = time.monotonic()
    shown = float(level)      # where the backlight is, chasing level
    fade = None               # levels a second while a scheduled change eases
                              # in; None for the dial's own quick ramp
    next_check = 0.0
    next_control = 0.0
    last_tick = time.monotonic()
    last_duty = duty_for(level)

    try:
        while True:
            sample = ((lgpio.gpio_read(h, CLK_PIN) << 1)
                      | lgpio.gpio_read(h, DT_PIN))
            if sample != encoded:
                accum += DIAL_DIRECTION * TRANSITION[(encoded << 2) | sample]
                encoded = sample
                last_move = time.monotonic()

                reversing = last_dir and accum * last_dir < 0
                threshold = REVERSE_DEADBAND if reversing else DEADBAND
                if abs(accum) >= threshold:
                    last_dir = 1 if accum > 0 else -1
                    target = max(0, min(100, level + accum * LEVEL_PER_COUNT))
                    accum = 0
                    if target != level:   # unchanged when pinned at 0 or 100
                        level = target
                        fade = None
                        print(f"Level: {level}", flush=True)

            elif accum and time.monotonic() - last_move > IDLE_RESET_S:
                # The dial settled mid-count. Drop it rather than let stray
                # counts add up into a step later.
                accum = 0
                last_dir = 0

            now = time.monotonic()
            if now >= next_control:
                next_control = now + CONTROL_POLL_S
                sent = read_control(control) if control else None
                if sent is not None and sent != level:
                    level = sent
                    fade = None
                    print(f"Level: {level} (set from Mac OS)", flush=True)
                if level != published:
                    publish_level(level)
                    published = level

            if now >= next_check:
                next_check = now + NIGHT_CHECK_S
                time.tzset()    # the time zone can change under us
                settings_changed |= settings.refresh()
                if clock_synced():
                    night = night_schedule.is_night(
                        settings.cfg, settings.coords, datetime.now().astimezone())
                    target = schedule.update(night, level, settings.cfg.level,
                                             settings_changed)
                    settings_changed = False
                    if target is not None and target != level:
                        fade = abs(target - shown) / NIGHT_FADE_S
                        level = target
                        print(f"{'Night' if night else 'Day'}: level {level}",
                              flush=True)

            if shown != level:
                step = RAMP_PER_TICK if fade is None else fade * (now - last_tick)
                if abs(level - shown) <= step:
                    shown = float(level)
                    fade = None
                else:
                    shown += step if level > shown else -step
            last_tick = now

            duty = duty_for(shown)
            if duty != last_duty:
                set_backlight(shown)
                last_duty = duty

            time.sleep(POLL_S)
    except Exception:
        failed = True
        print(traceback.format_exc(), flush=True)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
