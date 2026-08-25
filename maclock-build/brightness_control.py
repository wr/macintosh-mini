#!/usr/bin/env python3

# ####################################
# brightness_control.py
#
# Rotary encoder brightness control for Waveshare 2.8" DPI LCD.
# Encoder CLK on GPIO 11, DT on GPIO 10.
# Controls backlight via the kernel pwm-gpio driver on GPIO 18.
#
# March 26, 2026 - http://wells.ee/journal/macintosh-mini
# ####################################

import os
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
PWM_PERIOD_NS = 1_000_000  # 1 kHz

# The backlight is driven from an hrtimer, which cannot hold a pulse of much
# under 10 us. Gamma compresses the dark end hard enough that a naive mapping
# asks for 39 ns at the first step, so the bottom of the dial is floored here
# rather than silently landing wherever the timer happens to fire. Level 0
# still turns the backlight fully off.
MIN_PULSE_NS = 20_000

# Sampling the pins beats reacting to every edge. The encoder bounces hard —
# one turn throws hundreds of transitions — and a 1 ms sample steps over the
# chatter. Decoding every edge instead, as the kernel rotary-encoder driver
# does, gets the direction wrong on about one turn in five.
POLL_S = 0.001

# The dial is small, barely exposed, and its detents are mush, so it gets
# flicked through an arc rather than clicked. Brightness tracks how far it
# turned: a flick lands 8 to 10 counts, so it crosses about a third of the
# range. DEADBAND drops the odd stray count, and reversing takes a longer
# run than continuing, which keeps a flick going the way it started.
LEVEL_PER_COUNT = 4
DEADBAND = 1
REVERSE_DEADBAND = 4
IDLE_RESET_S = 0.4

# Move to a new level over a few milliseconds instead of jumping to it. A
# flick only yields 8 to 10 counts, so without this the backlight arrives in
# visible steps however small they are.
RAMP_PER_TICK = 1.0

# Perceived brightness is closer to the square of the duty cycle, so map the
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
    return channel


def duty_for(dial):
    """Map a dial position to a duty cycle in nanoseconds."""
    if dial <= 0:
        return 0
    span = PWM_PERIOD_NS - MIN_PULSE_NS
    return int(MIN_PULSE_NS + span * (dial / 100.0) ** GAMMA)


def set_backlight(dial):
    write(os.path.join(pwm_dir, "duty_cycle"), duty_for(dial))
    write(os.path.join(pwm_dir, "enable"), 1)


def cleanup(*_):
    # Reachable twice on SIGTERM: once from the handler, then again from the
    # finally block as SystemExit unwinds. Only the first pass should run.
    global cleaning
    if cleaning:
        return
    cleaning = True

    # Leave the backlight on — an unexported channel drives GPIO 18 low, which
    # reads as a dead screen.
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

    print(f"Brightness control running. level={level}", flush=True)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    encoded = (lgpio.gpio_read(h, CLK_PIN) << 1) | lgpio.gpio_read(h, DT_PIN)
    accum = 0
    last_dir = 0
    last_move = time.monotonic()
    shown = float(level)      # where the backlight is, chasing level
    last_duty = duty_for(level)

    try:
        while True:
            sample = ((lgpio.gpio_read(h, CLK_PIN) << 1)
                      | lgpio.gpio_read(h, DT_PIN))
            if sample != encoded:
                accum += TRANSITION[(encoded << 2) | sample]
                encoded = sample
                last_move = time.monotonic()

                reversing = last_dir and accum * last_dir < 0
                threshold = REVERSE_DEADBAND if reversing else DEADBAND
                if abs(accum) >= threshold:
                    last_dir = 1 if accum > 0 else -1
                    moved = max(0, min(100, level + accum * LEVEL_PER_COUNT))
                    accum = 0
                    if moved != level:   # already at a rail
                        level = moved
                        print(f"Level: {level}", flush=True)

            elif accum and time.monotonic() - last_move > IDLE_RESET_S:
                # The dial settled mid-count. Drop it rather than let stray
                # counts add up into a step later.
                accum = 0
                last_dir = 0

            if shown != level:
                if abs(level - shown) <= RAMP_PER_TICK:
                    shown = float(level)
                else:
                    shown += RAMP_PER_TICK if level > shown else -RAMP_PER_TICK
                duty = duty_for(shown)
                if duty != last_duty:
                    write(os.path.join(pwm_dir, "duty_cycle"), duty)
                    last_duty = duty

            time.sleep(POLL_S)
    except Exception as e:
        failed = True
        print(f"Error: {e}", flush=True)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
