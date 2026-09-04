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

import math
import os
import re
import signal
import sys
import time
import traceback
from collections import namedtuple
from datetime import datetime, time as dtime, timedelta, timezone

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
# Off unless /etc/default/brightness-control turns it on; the systemd unit
# hands that file over as environment variables:
#   NIGHT_DIM=1             enable
#   LAT=40.71 LON=-74.01    optional. Left blank, the location is the system
#                           timezone's reference city from tzdata, which puts
#                           sunrise within a few minutes for most people
#   NIGHT_FACTOR=0.5        sunset to sunrise, the dial level is scaled by this
#   NIGHT_OFF_AT=22:00      from here until sunrise the backlight goes fully
#                           dark. Leave blank to only ever dim.
# Turning the dial at night wakes the screen until the next sunset.
NIGHT_FADE_S = 30      # scheduled changes ease in over this long
NIGHT_CHECK_S = 1.0    # how often the schedule is consulted

# The Zero has no clock battery, so until NTP answers the time is whatever
# fake-hwclock saved at the last shutdown. Dimming on that would be a guess,
# so the schedule waits for timesyncd to raise this flag.
CLOCK_SYNCED_FLAG = "/run/systemd/timesync/synchronized"

J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

ZONE_TABS = ("/usr/share/zoneinfo/zone1970.tab", "/usr/share/zoneinfo/zone.tab")

NightConfig = namedtuple("NightConfig", "lat lon factor off_at")


def write(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def read_zone_tab(paths=ZONE_TABS):
    """Every zone table tzdata ships, joined. zone1970.tab alone is not
    enough: since 2022 it folds Oslo, Stockholm, Amsterdam and a hundred
    others into one representative zone, and only zone.tab still lists
    them."""
    tabs = []
    for path in paths:
        try:
            with open(path) as f:
                tabs.append(f.read())
        except OSError:
            continue
    return "\n".join(tabs) if tabs else None


def zone_coords(zone, tab):
    """Latitude and longitude of a timezone's reference city, from tzdata's
    zone1970.tab, or None if the zone is not listed (Etc/UTC, for one)."""
    if not zone or not tab:
        return None
    for line in tab.splitlines():
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) >= 3 and cols[2] == zone:
            return _iso6709(cols[1])
    return None


def _iso6709(text):
    """Decode +DDMM+DDDMM or +DDMMSS+DDDMMSS into decimal degrees."""
    m = re.fullmatch(r"([+-])(\d{2})(\d{2})(\d{2})?([+-])(\d{3})(\d{2})(\d{2})?", text)
    if not m:
        return None

    def decode(sign, d, mi, sec):
        value = int(d) + int(mi) / 60 + (int(sec) if sec else 0) / 3600
        return -value if sign == "-" else value

    return (decode(m[1], m[2], m[3], m[4]), decode(m[5], m[6], m[7], m[8]))


def system_timezone():
    # The symlink is what libc and timedatectl agree on; /etc/timezone is a
    # Debian extra that can lag behind it.
    target = os.path.realpath("/etc/localtime")
    if "/zoneinfo/" in target:
        return target.split("/zoneinfo/", 1)[1]
    try:
        with open("/etc/timezone") as f:
            return f.read().strip() or None
    except OSError:
        return None


def load_night_config(env, zone=None, zone_tab=None):
    """Read the night schedule from the environment, or None when it is off."""
    if env.get("NIGHT_DIM", "0").strip().lower() not in ("1", "true", "yes"):
        return None
    try:
        return _parse_night_config(env, zone, zone_tab)
    except ValueError as e:
        # A typo here must not take the dial down in a restart loop
        print(f"Bad value in night config ({e}); night dimming off", flush=True)
        return None


def _parse_night_config(env, zone, zone_tab):
    if env.get("LAT", "").strip() and env.get("LON", "").strip():
        lat, lon = float(env["LAT"]), float(env["LON"])
    else:
        zone = zone or system_timezone()
        coords = zone_coords(zone, zone_tab if zone_tab is not None
                             else read_zone_tab())
        if coords is None:
            print(f"No location for timezone {zone!r} and LAT/LON unset; "
                  "night dimming off. Set the timezone: "
                  "sudo timedatectl set-timezone <Area/City>", flush=True)
            return None
        lat, lon = coords
    factor = float(env.get("NIGHT_FACTOR", "0.5"))
    off = env.get("NIGHT_OFF_AT", "22:00").strip()
    off_at = dtime.fromisoformat(off) if off else None
    return NightConfig(lat, lon, factor, off_at)


def _sun_geometry(lat, lon, day):
    """Solar transit on `day` in days since J2000, and the cosine of the
    sunrise hour angle: outside [-1, 1] the sun never crosses the horizon.

    This is the sunrise equation with NOAA's corrections: good to a couple
    of minutes, which is plenty for a backlight.
    """
    sin, cos, rad = math.sin, math.cos, math.radians
    # Days since J2000, shifted so the numbers below refer to local solar noon
    n = (day - J2000.date()).days - lon / 360
    mean_anomaly = (357.5291 + 0.98560028 * n) % 360
    centre = (1.9148 * sin(rad(mean_anomaly))
              + 0.0200 * sin(rad(2 * mean_anomaly))
              + 0.0003 * sin(rad(3 * mean_anomaly)))
    ecliptic_lon = (mean_anomaly + centre + 180 + 102.9372) % 360
    transit = (n + 0.0053 * sin(rad(mean_anomaly))
               - 0.0069 * sin(rad(2 * ecliptic_lon)))
    declination = math.asin(sin(rad(ecliptic_lon)) * sin(rad(23.4397)))
    # -0.833 degrees: the sun's upper limb at the horizon, through refraction
    cos_hour = ((sin(rad(-0.833)) - sin(rad(lat)) * sin(declination))
                / (cos(rad(lat)) * cos(declination)))
    return transit, cos_hour


def sun_times(lat, lon, day):
    """Sunrise and sunset on `day` as aware UTC datetimes, or None where
    the sun never rises or never sets that day."""
    transit, cos_hour = _sun_geometry(lat, lon, day)
    if not -1 <= cos_hour <= 1:
        return None
    half_day = math.degrees(math.acos(cos_hour)) / 360
    return (J2000 + timedelta(days=transit - half_day),
            J2000 + timedelta(days=transit + half_day))


def midnight_sun(lat, lon, day):
    """True when the sun stays above the horizon all of `day`."""
    return _sun_geometry(lat, lon, day)[1] < -1


def night_factor(now, cfg, sun_times=sun_times):
    """Scale for the dial level at `now` (an aware local datetime).

    1.0 by day, cfg.factor after sunset, 0.0 from cfg.off_at until sunrise.
    """
    # Work from the most recent sunrise and sunset instants rather than
    # "today's": where the clock runs far from solar time (Alaska, UTC+14)
    # the sun can set after local midnight, on the next calendar date.
    rises, sets = [], []
    for days in (-1, 0, 1):
        times = sun_times(cfg.lat, cfg.lon, now.date() + timedelta(days=days))
        if times is not None:
            rises.append(times[0])
            sets.append(times[1])
    last_rise = max((t for t in rises if t <= now), default=None)
    last_set = max((t for t in sets if t <= now), default=None)
    if last_rise is None and last_set is None:
        # Polar: nothing crossed the horizon for days
        return 1.0 if midnight_sun(cfg.lat, cfg.lon, now.date()) else cfg.factor
    if last_set is None or (last_rise is not None and last_rise > last_set):
        return 1.0

    if cfg.off_at is None:
        return cfg.factor
    # The cutoff belongs to the night that began at last_set: the first
    # occurrence of that clock time from a few hours before sunset on, so a
    # time after midnight lands in this night and one before sunset (a 22:00
    # cutoff under a 22:08 midsummer sunset) means dark from sunset.
    sunset = last_set.astimezone(now.tzinfo)
    off = min(t for t in (datetime.combine(sunset.date() + timedelta(days=days),
                                           cfg.off_at, now.tzinfo)
                          for days in (0, 1))
              if t > sunset - timedelta(hours=6))
    return 0.0 if now >= max(off, sunset) else cfg.factor


def clock_synced():
    return os.path.exists(CLOCK_SYNCED_FLAG)


class NightState:
    """Applies the schedule, but lets the dial win: a turn at night wakes the
    screen, and it stays awake until the next sunset."""

    def __init__(self):
        self.scheduled = 1.0
        self.awake = False

    def dial_moved(self):
        if self.scheduled < 1.0:
            self.awake = True

    def update(self, scheduled):
        if scheduled == 1.0:
            self.awake = False
        self.scheduled = scheduled
        return 1.0 if self.awake else scheduled


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

    night = load_night_config(os.environ)
    state = NightState()
    print(f"Brightness control running. level={level} "
          f"night={'on' if night else 'off'}", flush=True)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    encoded = (lgpio.gpio_read(h, CLK_PIN) << 1) | lgpio.gpio_read(h, DT_PIN)
    accum = 0
    last_dir = 0
    last_move = time.monotonic()
    shown = float(level)      # where the backlight is, chasing level
    factor = 1.0              # what the schedule wants the level scaled by
    eased = 1.0               # where the scaling is, chasing factor
    next_check = 0.0
    last_tick = time.monotonic()
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
                    target = max(0, min(100, level + accum * LEVEL_PER_COUNT))
                    accum = 0
                    # Any turn wakes the screen at night, even one pinned at
                    # the end of the dial that leaves the level where it was.
                    state.dial_moved()
                    next_check = 0.0
                    if target != level:   # unchanged when pinned at 0 or 100
                        level = target
                        print(f"Level: {level}", flush=True)

            elif accum and time.monotonic() - last_move > IDLE_RESET_S:
                # The dial settled mid-count. Drop it rather than let stray
                # counts add up into a step later.
                accum = 0
                last_dir = 0

            if night and time.monotonic() >= next_check:
                next_check = time.monotonic() + NIGHT_CHECK_S
                scheduled = 1.0
                if clock_synced():
                    scheduled = night_factor(datetime.now().astimezone(), night)
                wanted = state.update(scheduled)
                if wanted != factor:
                    factor = wanted
                    print(f"Night: x{factor:g}", flush=True)
                if state.awake and eased != factor:
                    # The dial was touched: skip the slow fade and let the
                    # dial's own quick ramp bring the backlight up
                    shown *= eased
                    eased = factor

            now = time.monotonic()
            if eased != factor:
                step = (now - last_tick) / NIGHT_FADE_S
                if abs(factor - eased) <= step:
                    eased = factor
                else:
                    eased += step if factor > eased else -step
            last_tick = now

            if shown != level:
                if abs(level - shown) <= RAMP_PER_TICK:
                    shown = float(level)
                else:
                    shown += RAMP_PER_TICK if level > shown else -RAMP_PER_TICK

            duty = duty_for(shown * eased)
            if duty != last_duty:
                set_backlight(shown * eased)
                last_duty = duty

            time.sleep(POLL_S)
    except Exception:
        failed = True
        print(traceback.format_exc(), flush=True)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
