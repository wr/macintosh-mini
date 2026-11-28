#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# night_schedule.py
#
# Night dimming: the settings file, the time zone's place, sunset and sunrise,
# and when the screen dims. Shared by brightness_control.py (which dims),
# mini_link.py (which shows the settings to Mac OS) and mini_link_apply.py
# (which saves them). Nothing here touches hardware.
#
# The schedule is the Macintosh Mini ESP32's (main/settings.c there), so both
# builds behave the same.
# ####################################

import math
import os
from datetime import datetime, timedelta, timezone

# Night dimming's settings, /etc/default/brightness-control:
#   NIGHT_DIM=1             on
#   NIGHT_FROM=22:00        when it starts: HH:MM, or sunset
#   NIGHT_UNTIL=07:00       when it ends: HH:MM, or sunrise
#   NIGHT_LEVEL=20          how dim, 0-100; 0 turns the backlight off
#   LAT=40.71 LON=-74.01    optional. Left blank, sunset and sunrise are worked
#                           out for the time zone's place in tzdata, which is
#                           within a few minutes for most people
CONFIG = "/etc/default/brightness-control"

# "From" and "until" are minutes after midnight, or one of these
SUNSET = 24 * 60
SUNRISE = 24 * 60 + 1

# What Sunset and Sunrise mean where the sun's times aren't known: no place
# for the time zone, or the sun stays up or down all day
FALLBACK_SUNSET = 19 * 60
FALLBACK_SUNRISE = 7 * 60

J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

ZONE_TAB = "/usr/share/zoneinfo/zone.tab"
ZONE_TABS = ("/usr/share/zoneinfo/zone1970.tab", ZONE_TAB)


class NightConfig:
    """Night dimming as set: on, from_ and until (minutes after midnight, or
    SUNSET and SUNRISE), level (0-100), and lat and lon when set by hand."""

    __slots__ = ("on", "from_", "until", "level", "lat", "lon")

    def __init__(self, on=False, from_=22 * 60, until=7 * 60, level=20,
                 lat=None, lon=None):
        self.on, self.from_, self.until, self.level = on, from_, until, level
        self.lat, self.lon = lat, lon

    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in self.__slots__)

    def __repr__(self):
        return "NightConfig(%s)" % ", ".join(
            f"{k}={getattr(self, k)!r}" for k in self.__slots__)


# --- The time zone's place -------------------------------------------------

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


def zone_names(tab):
    """The time zones in a zone table, sorted: the list Mac OS picks from,
    numbered from 0."""
    names = set()
    for line in (tab or "").splitlines():
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) >= 3 and cols[2]:
            names.add(cols[2])
    return sorted(names)


def zone_coords(zone, tab):
    """Latitude and longitude of a timezone's reference city, from tzdata's
    zone tables, or None if the zone is not listed (Etc/UTC, for one)."""
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
    import re
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


def place(cfg, zone, tab):
    """Where sunset and sunrise are worked out for: the place set by hand,
    else the time zone's. None when the zone has no place."""
    if cfg.lat is not None and cfg.lon is not None:
        return (cfg.lat, cfg.lon)
    return zone_coords(zone, tab)


# --- The settings file -----------------------------------------------------

def parse_time(text, word, value):
    """A NIGHT_FROM or NIGHT_UNTIL value: HH:MM, or the word that stands for
    `value` (sunset, sunrise)."""
    text = text.strip().lower()
    if text == word:
        return value
    hours, sep, minutes = text.partition(":")
    if (not sep or len(hours) != 2 or len(minutes) != 2
            or not (hours + minutes).isdigit()
            or int(hours) > 23 or int(minutes) > 59):
        raise ValueError(f"{text!r} is not HH:MM or {word}")
    return int(hours) * 60 + int(minutes)


def format_time(t):
    if t == SUNSET:
        return "sunset"
    if t == SUNRISE:
        return "sunrise"
    return f"{t // 60:02d}:{t % 60:02d}"


def parse_config(text):
    """Night dimming's settings from the file's text. A file from before 1.12
    (NIGHT_FACTOR, NIGHT_OFF_AT) with dimming on becomes sunset to sunrise at
    50, the nearest thing to what it did. Raises ValueError on a bad value."""
    env = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.lstrip().startswith("#"):
            env[key.strip()] = value.strip()
    cfg = NightConfig()
    cfg.on = env.get("NIGHT_DIM", "0").lower() in ("1", "true", "yes")
    if "NIGHT_FROM" not in env and ("NIGHT_FACTOR" in env or "NIGHT_OFF_AT" in env):
        if cfg.on:
            cfg.from_, cfg.until, cfg.level = SUNSET, SUNRISE, 50
    else:
        if env.get("NIGHT_FROM"):
            cfg.from_ = parse_time(env["NIGHT_FROM"], "sunset", SUNSET)
        if env.get("NIGHT_UNTIL"):
            cfg.until = parse_time(env["NIGHT_UNTIL"], "sunrise", SUNRISE)
        if env.get("NIGHT_LEVEL"):
            cfg.level = int(env["NIGHT_LEVEL"])
            if not 0 <= cfg.level <= 100:
                raise ValueError(f"NIGHT_LEVEL {cfg.level} is not 0 to 100")
    if env.get("LAT") and env.get("LON"):
        cfg.lat, cfg.lon = float(env["LAT"]), float(env["LON"])
        if not (-90 <= cfg.lat <= 90 and -180 <= cfg.lon <= 180):
            raise ValueError("LAT or LON is out of range")
    return cfg


def format_config(cfg):
    def degrees(v):
        return "" if v is None else f"{v:g}"

    return (
        "# Night dimming for the Macintosh Mini's backlight. brightness-control\n"
        "# reads this file again whenever it changes.\n"
        f"NIGHT_DIM={1 if cfg.on else 0}\n"
        "# When the screen dims and when it comes back: HH:MM, or sunset and sunrise\n"
        f"NIGHT_FROM={format_time(cfg.from_)}\n"
        f"NIGHT_UNTIL={format_time(cfg.until)}\n"
        "# How dim, 0 to 100. 0 turns the screen off.\n"
        f"NIGHT_LEVEL={cfg.level}\n"
        "# Optional. Blank, sunset and sunrise are those of the time zone's city.\n"
        "# Set both in decimal degrees (north and east positive) for a closer fix.\n"
        f"LAT={degrees(cfg.lat)}\n"
        f"LON={degrees(cfg.lon)}\n")


def load_config(path=CONFIG):
    """The settings in the file; dimming off when there's no file. Raises
    ValueError on a bad value."""
    try:
        with open(path) as f:
            return parse_config(f.read())
    except FileNotFoundError:
        return NightConfig()


# --- Sunset and sunrise ----------------------------------------------------

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


def sun_minutes(coords, now, sunset, offset=0):
    """Sunset (or sunrise) on the day of `now` (an aware local datetime) plus
    `offset` days, in local minutes after midnight, or None when it isn't
    known: no place, or the sun doesn't cross the horizon that day."""
    if coords is None:
        return None
    times = sun_times(coords[0], coords[1], now.date() + timedelta(days=offset))
    if times is None:
        return None
    local = times[1 if sunset else 0].astimezone(now.tzinfo)
    return local.hour * 60 + local.minute


def clock_time(t, coords, now):
    """A dimming time as today's clock time, in minutes after midnight."""
    if t == SUNSET:
        t = sun_minutes(coords, now, True)
        return FALLBACK_SUNSET if t is None else t
    if t == SUNRISE:
        t = sun_minutes(coords, now, False)
        return FALLBACK_SUNRISE if t is None else t
    return t


# --- When the screen dims --------------------------------------------------

def in_window(now, start, end):
    """Whether `now` is inside a window that may cross midnight. All three
    are minutes after midnight."""
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def is_night(cfg, coords, now):
    """Whether night dimming's window is open at `now`, an aware local
    datetime."""
    return cfg.on and in_window(now.hour * 60 + now.minute,
                                clock_time(cfg.from_, coords, now),
                                clock_time(cfg.until, coords, now))


class Schedule:
    """Acts when night starts or ends, and when "how dim" changes during the
    night, so the dial wins in between: turning it at night holds until the
    next night starts.

    When night starts it remembers the level and, if that's brighter than
    "how dim", goes to "how dim". When night ends it goes back to the level
    it remembered. Starting up at night with "how dim" at 0 leaves the screen
    alone, so it never goes black seconds after power-on."""

    def __init__(self):
        self.was = None          # None not known yet, False day, True night
        self.day_level = None    # the level remembered when night started
        self.applied = None      # the "how dim" last acted on

    def update(self, night, level, dim_level, changed=False):
        """Call regularly with whether it's night, the level now and "how
        dim"; `changed` when the settings just changed. Returns the level to
        go to, or None to leave it alone."""
        target = None
        if changed and not night and self.was and self.day_level is not None:
            # Dimming was turned off, or its times moved
            target = self.day_level
            self.was = False
        if night != self.was:
            if night:
                self.day_level = level
                starting_up = self.was is None
                if level > dim_level and not (starting_up and dim_level == 0):
                    target = dim_level
                self.applied = dim_level
            elif self.was and self.day_level is not None:
                target = self.day_level
            self.was = night
        elif night and dim_level != self.applied:
            # "How dim" changed during the night: it applies at once
            if level > dim_level:
                target = dim_level
            self.applied = dim_level
        return target
