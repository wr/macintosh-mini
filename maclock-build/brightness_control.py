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
import signal
import struct
import sys
import time

# --- Config ---
PWM_PERIOD_NS = 1_000_000  # 1 kHz
MIN_DUTY = 5
MAX_DUTY = 100
STEP = 20

# The encoder is electrically noisy — a single click produces a burst of
# roughly a hundred edges. Take the first event of a burst and ignore the
# rest, so one click moves brightness one step.
LOCKOUT_S = 0.05

PWM_SYSFS = "/sys/class/pwm"
PWM_DEVICE = "pwm_gpio"     # dtoverlay=pwm-gpio,gpio=18
INPUT_SYSFS = "/sys/class/input"
INPUT_DEVICE = "rotary@"    # dtoverlay=rotary-encoder,pin_a=11,pin_b=10

# struct input_event: two longs of timestamp, then type, code, value
EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EV_REL = 0x02

brightness = MAX_DUTY
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


def set_backlight(duty):
    write(os.path.join(pwm_dir, "duty_cycle"), duty * PWM_PERIOD_NS // 100)
    write(os.path.join(pwm_dir, "enable"), 1)


def cleanup(*_):
    # Leave the backlight on — an unexported channel drives GPIO 18 low, which
    # reads as a dead screen.
    if pwm_dir is not None:
        set_backlight(MAX_DUTY)
    sys.exit(0)


def main():
    global brightness, pwm_dir

    pwm_dir = open_backlight()
    set_backlight(brightness)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    path = find_encoder()
    if path is None:
        print(f"No {INPUT_DEVICE} input device found. Is "
              "dtoverlay=rotary-encoder,pin_a=11,pin_b=10,relative_axis=1 in "
              "/boot/firmware/config.txt?", flush=True)
        sys.exit(1)

    print(f"Brightness control running. brightness={brightness}% "
          f"encoder={path}", flush=True)

    last_step = 0.0
    with open(path, "rb") as f:
        while True:
            data = f.read(EVENT_SIZE)
            if not data:
                break
            _sec, _usec, etype, _code, value = struct.unpack(EVENT_FORMAT, data)
            if etype != EV_REL or value == 0:
                continue

            now = time.monotonic()
            if now - last_step < LOCKOUT_S:
                continue
            last_step = now

            if value > 0:
                brightness = min(MAX_DUTY, brightness + STEP)
            else:
                brightness = max(MIN_DUTY, brightness - STEP)
            set_backlight(brightness)
            print(f"Brightness: {brightness}%", flush=True)

    cleanup()


if __name__ == "__main__":
    main()
