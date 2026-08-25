#!/usr/bin/env python3

# ####################################
# brightness_control.py
#
# Rotary encoder brightness control for Waveshare 2.8" DPI LCD.
# Encoder CLK on GPIO 11, DT on GPIO 10, decoded by the kernel rotary-encoder
# driver. Controls backlight via the kernel pwm-gpio driver on GPIO 18.
#
# March 26, 2026 - http://wells.ee/journal/macintosh-mini
# ####################################

import os
import select
import signal
import struct
import sys
import time

# --- Config ---
PWM_PERIOD_NS = 1_000_000  # 1 kHz
MIN_DUTY = 5               # never let the screen go fully dark
MAX_DUTY = 100

# The dial is small, barely exposed, and its detents are mush, so it gets
# flicked through an arc rather than clicked. Brightness tracks how far it
# turned: a flick of roughly 70 degrees crosses most of the range, and a
# nudge moves it a little. DEADBAND swallows the odd stray count from
# contact bounce without stalling a real turn.
LEVEL_PER_COUNT = 3
DEADBAND = 2

# ENC_A and ENC_B have no pull-up or filter cap on the breakout board, so one
# channel can drop out mid-flick and the driver then reports the wrong
# direction. Committing to a direction and demanding a much stronger run to
# reverse keeps a flick going the way it started.
REVERSE_DEADBAND = 6

# Perceived brightness is closer to the square of the duty cycle, so map the
# dial through a curve. Without it most of the arc is spent up at the bright
# end, where the eye can barely tell the difference.
GAMMA = 2.2

# The encoder is electrically noisy. Contact bounce throws single events in
# both directions, while a real click lands five or six the same way, so
# events accumulate and only a run past THRESHOLD moves the brightness.
# Stray counts cancel instead of stepping. The accumulator resets once the
# dial has been still for IDLE_RESET_S, so noise cannot add up over time.
IDLE_RESET_S = 0.4

PWM_SYSFS = "/sys/class/pwm"
PWM_DEVICE = "pwm_gpio"     # dtoverlay=pwm-gpio,gpio=18
INPUT_SYSFS = "/sys/class/input"
INPUT_DEVICE = "rotary@"    # dtoverlay=rotary-encoder,pin_a=11,pin_b=10

# struct input_event: two longs of timestamp, then type, code, value
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EV_REL = 0x02

level = 100    # dial position, 0-100
pwm_dir = None


def write(path, value):
    with open(path, "w") as f:
        f.write(str(value))


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
            if os.path.basename(device).startswith(PWM_DEVICE):
                return os.path.join(PWM_SYSFS, chip)
        if time.monotonic() > deadline:
            return None
        time.sleep(0.2)


def find_encoder(timeout=30):
    """Return the /dev/input node for the kernel rotary-encoder device.

    The event number moves around between boots, so match on the device name.
    This service starts before the driver probes, so wait for it to appear.
    """
    deadline = time.monotonic() + timeout
    while True:
        for entry in sorted(os.listdir(INPUT_SYSFS)):
            name_file = os.path.join(INPUT_SYSFS, entry, "name")
            if not entry.startswith("input") or not os.path.exists(name_file):
                continue
            with open(name_file) as f:
                if not f.read().strip().startswith(INPUT_DEVICE):
                    continue
            for sub in os.listdir(os.path.join(INPUT_SYSFS, entry)):
                if sub.startswith("event"):
                    return f"/dev/input/{sub}"
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
    return channel


def set_backlight(level):
    duty = MIN_DUTY + (MAX_DUTY - MIN_DUTY) * (level / 100.0) ** GAMMA
    write(os.path.join(pwm_dir, "duty_cycle"),
          int(duty * PWM_PERIOD_NS / 100))
    write(os.path.join(pwm_dir, "enable"), 1)


def cleanup(*_):
    # Leave the backlight on — an unexported channel drives GPIO 18 low, which
    # reads as a dead screen.
    if pwm_dir is not None:
        set_backlight(100)
    sys.exit(0)


def main():
    global level, pwm_dir

    pwm_dir = open_backlight()
    set_backlight(level)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    path = find_encoder()
    if path is None:
        print(f"No {INPUT_DEVICE} input device found. Is "
              "dtoverlay=rotary-encoder,pin_a=11,pin_b=10,relative_axis=1 in "
              "/boot/firmware/config.txt?", flush=True)
        sys.exit(1)

    print(f"Brightness control running. level={level} encoder={path}",
          flush=True)

    accum = 0
    last_dir = 0
    with open(path, "rb", buffering=0) as f:
        poll = select.poll()
        poll.register(f, select.POLLIN)
        while True:
            # Wait indefinitely when the accumulator is empty, otherwise only
            # until the dial has been still long enough to discard the count.
            if not poll.poll(IDLE_RESET_S * 1000 if accum else None):
                accum = 0
                last_dir = 0
                continue

            data = f.read(EVENT_SIZE)
            if not data:
                break
            _sec, _usec, etype, _code, value = struct.unpack(EVENT_FORMAT, data)
            if etype != EV_REL or value == 0:
                continue

            accum += value
            reversing = last_dir and accum * last_dir < 0
            if abs(accum) < (REVERSE_DEADBAND if reversing else DEADBAND):
                continue

            last_dir = 1 if accum > 0 else -1
            level = max(0, min(100, level + accum * LEVEL_PER_COUNT))
            accum = 0
            set_backlight(level)
            print(f"Level: {level}", flush=True)

    cleanup()


if __name__ == "__main__":
    main()
