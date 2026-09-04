#!/usr/bin/env python3
"""Tests for the night-dimming logic in brightness_control.py.

Run: python3 -m unittest test_brightness_control
The lgpio module only exists on the Pi, so it is stubbed out here; nothing
under test touches GPIO.
"""

import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

sys.modules.setdefault("lgpio", types.ModuleType("lgpio"))

import brightness_control as bc  # noqa: E402

UTC = timezone.utc


def minutes_apart(a, b):
    return abs((a - b).total_seconds()) / 60


class SunTimes(unittest.TestCase):
    # Reference values from the NOAA solar calculator.

    def test_new_york_summer_solstice(self):
        rise, set_ = bc.sun_times(40.7128, -74.0060, date(2024, 6, 21))
        self.assertLess(minutes_apart(rise, datetime(2024, 6, 21, 9, 25, tzinfo=UTC)), 5)
        self.assertLess(minutes_apart(set_, datetime(2024, 6, 22, 0, 31, tzinfo=UTC)), 5)

    def test_london_winter_solstice(self):
        rise, set_ = bc.sun_times(51.5074, -0.1278, date(2024, 12, 21))
        self.assertLess(minutes_apart(rise, datetime(2024, 12, 21, 8, 4, tzinfo=UTC)), 5)
        self.assertLess(minutes_apart(set_, datetime(2024, 12, 21, 15, 53, tzinfo=UTC)), 5)

    def test_sydney_southern_hemisphere(self):
        # 2024-06-21: sunrise 07:01 AEST, sunset 16:54 AEST (UTC+10)
        rise, set_ = bc.sun_times(-33.8688, 151.2093, date(2024, 6, 21))
        self.assertLess(minutes_apart(rise, datetime(2024, 6, 20, 21, 1, tzinfo=UTC)), 5)
        self.assertLess(minutes_apart(set_, datetime(2024, 6, 21, 6, 54, tzinfo=UTC)), 5)

    def test_midnight_sun_returns_none(self):
        self.assertIsNone(bc.sun_times(69.6492, 18.9553, date(2024, 6, 21)))

    def test_polar_night_returns_none(self):
        self.assertIsNone(bc.sun_times(69.6492, 18.9553, date(2024, 12, 21)))


class NightFactor(unittest.TestCase):
    # A fake location where the sun rises at 06:00 and sets at 18:00 local,
    # every day, so the tests read as clock times.
    TZ = timezone(timedelta(hours=-5))

    def sun(self, lat, lon, day):
        return (datetime.combine(day, time(6), self.TZ).astimezone(UTC),
                datetime.combine(day, time(18), self.TZ).astimezone(UTC))

    def at(self, hh, mm=0, day=date(2026, 3, 10)):
        return datetime.combine(day, time(hh, mm), self.TZ)

    def factor(self, now, off_at=time(22, 0), night=0.5):
        cfg = bc.NightConfig(lat=0, lon=0, factor=night, off_at=off_at)
        return bc.night_factor(now, cfg, sun_times=self.sun)

    def test_day_is_full_brightness(self):
        self.assertEqual(self.factor(self.at(12)), 1.0)

    def test_after_sunset_dims(self):
        self.assertEqual(self.factor(self.at(19)), 0.5)

    def test_after_cutoff_is_dark(self):
        self.assertEqual(self.factor(self.at(22, 30)), 0.0)

    def test_after_midnight_stays_dark(self):
        self.assertEqual(self.factor(self.at(3)), 0.0)

    def test_sunrise_restores_full_brightness(self):
        self.assertEqual(self.factor(self.at(6, 1)), 1.0)

    def test_cutoff_after_midnight(self):
        self.assertEqual(self.factor(self.at(23), off_at=time(1, 0)), 0.5)
        self.assertEqual(self.factor(self.at(1, 30), off_at=time(1, 0)), 0.0)

    def test_cutoff_before_sunset_goes_dark_at_sunset(self):
        # High-latitude summer: 22:00 comes before a 22:08 sunset. Here the
        # fixture sets at 18:00, so a 17:00 cutoff stands in for it.
        self.assertEqual(self.factor(self.at(18, 30), off_at=time(17, 0)), 0.0)
        self.assertEqual(self.factor(self.at(16, 0), off_at=time(17, 0)), 1.0)

    def test_no_cutoff_dims_all_night(self):
        self.assertEqual(self.factor(self.at(3), off_at=None), 0.5)



def local_now(zone, y, mo, d, hh, mm=0):
    """Build `now` the way the daemon sees it on a Pi set to `zone`: an
    aware datetime carrying a fixed offset, as datetime.now().astimezone()
    returns."""
    dt = datetime(y, mo, d, hh, mm, tzinfo=ZoneInfo(zone))
    return dt.astimezone(timezone(dt.utcoffset()))


class NightFactorRealSun(unittest.TestCase):
    """Real sun_times at places where clock time and solar time disagree."""

    def factor(self, zone, lat, lon, *when, off_at=time(22, 0)):
        cfg = bc.NightConfig(lat=lat, lon=lon, factor=0.5, off_at=off_at)
        return bc.night_factor(local_now(zone, *when), cfg)

    def test_stockholm_midsummer_dark_after_late_sunset(self):
        # Sunset 22:08 CEST is after the 22:00 cutoff: dark from sunset on
        stockholm = ("Europe/Stockholm", 59.33, 18.07)
        self.assertEqual(self.factor(*stockholm, 2024, 6, 21, 21, 30), 1.0)
        self.assertEqual(self.factor(*stockholm, 2024, 6, 21, 22, 30), 0.0)
        self.assertEqual(self.factor(*stockholm, 2024, 6, 22, 1, 0), 0.0)
        self.assertEqual(self.factor(*stockholm, 2024, 6, 22, 4, 0), 1.0)

    def test_nome_sunset_after_local_midnight(self):
        # Alaska's clock runs ~3 h ahead of the sun: June sunset is 01:47
        nome = ("America/Nome", 64.50, -165.41)
        self.assertEqual(self.factor(*nome, 2024, 6, 22, 0, 30), 1.0)
        self.assertEqual(self.factor(*nome, 2024, 6, 22, 2, 30), 0.5)
        self.assertEqual(self.factor(*nome, 2024, 6, 22, 5, 0), 1.0)

    def test_utc_plus_14_midday_is_day(self):
        self.assertEqual(self.factor("Pacific/Kiritimati", 1.87, -157.4,
                                     2024, 6, 21, 12, 0), 1.0)

    def test_polar_night_dims(self):
        # No sunrise to end a cutoff, so polar night only dims, all day
        tromso = ("Europe/Oslo", 69.65, 18.96)
        self.assertEqual(self.factor(*tromso, 2024, 12, 21, 12, 0), 0.5)
        self.assertEqual(self.factor(*tromso, 2024, 12, 21, 23, 0), 0.5)

    def test_midnight_sun_never_dims(self):
        self.assertEqual(self.factor("Europe/Oslo", 69.65, 18.96,
                                     2024, 6, 21, 23, 0), 1.0)


class DialOverride(unittest.TestCase):
    def test_dial_at_night_wakes_until_next_sunset(self):
        state = bc.NightState()
        self.assertEqual(state.update(0.5), 0.5)
        state.dial_moved()
        self.assertEqual(state.update(0.5), 1.0)   # woken
        self.assertEqual(state.update(0.0), 1.0)   # still woken past cutoff
        self.assertEqual(state.update(1.0), 1.0)   # sunrise
        self.assertEqual(state.update(0.5), 0.5)   # next sunset dims again

    def test_dial_during_day_does_not_pin(self):
        state = bc.NightState()
        state.update(1.0)
        state.dial_moved()
        self.assertEqual(state.update(0.5), 0.5)


ZONE_TAB = """\
# comment line
#codes\tcoordinates\tTZ\tcomments
US\t+404251-0740023\tAmerica/New_York\tEastern (most areas)
JP\t+353916+1394441\tAsia/Tokyo
AU\t-3133+15905\tAustralia/Lord_Howe\tLord Howe Island
"""


class ZoneCoords(unittest.TestCase):
    def test_degrees_minutes_seconds(self):
        lat, lon = bc.zone_coords("America/New_York", ZONE_TAB)
        self.assertAlmostEqual(lat, 40.714, places=3)
        self.assertAlmostEqual(lon, -74.006, places=3)

    def test_degrees_minutes(self):
        lat, lon = bc.zone_coords("Australia/Lord_Howe", ZONE_TAB)
        self.assertAlmostEqual(lat, -31.55, places=3)
        self.assertAlmostEqual(lon, 159.083, places=3)

    def test_unknown_zone(self):
        self.assertIsNone(bc.zone_coords("Etc/UTC", ZONE_TAB))

    def test_zone_only_in_second_table_is_found(self):
        # Since 2022 zone1970.tab folds Oslo, Stockholm, Amsterdam and ~100
        # others into one representative zone; only zone.tab still lists them.
        with tempfile.TemporaryDirectory() as d:
            first = os.path.join(d, "zone1970.tab")
            second = os.path.join(d, "zone.tab")
            open(first, "w").write(ZONE_TAB)
            open(second, "w").write("NO\t+5955+01045\tEurope/Oslo\n")
            lat, lon = bc.zone_coords("Europe/Oslo", bc.read_zone_tab((first, second)))
        self.assertAlmostEqual(lat, 59.917, places=3)
        self.assertAlmostEqual(lon, 10.75, places=3)

    def test_real_tzdata_has_coordinates(self):
        # tzdata ships the table this relies on; make sure the parser copes
        # with the real thing, not just the fixture.
        tab = bc.read_zone_tab()
        if tab is None:
            self.skipTest("no tzdata zone table on this machine")
        lat, lon = bc.zone_coords("Asia/Tokyo", tab)
        self.assertAlmostEqual(lat, 35.65, places=1)
        self.assertAlmostEqual(lon, 139.74, places=1)


class Config(unittest.TestCase):
    def load(self, env, zone="America/New_York"):
        return bc.load_night_config(env, zone=zone, zone_tab=ZONE_TAB)

    def test_disabled_by_default(self):
        self.assertIsNone(self.load({}))

    def test_location_from_timezone(self):
        cfg = self.load({"NIGHT_DIM": "1"}, zone="Asia/Tokyo")
        self.assertAlmostEqual(cfg.lat, 35.654, places=3)
        self.assertAlmostEqual(cfg.lon, 139.745, places=3)

    def test_explicit_location_overrides_timezone(self):
        cfg = self.load({"NIGHT_DIM": "1", "LAT": "40.7", "LON": "-74.0",
                         "NIGHT_FACTOR": "0.4", "NIGHT_OFF_AT": "23:15"}, zone="Asia/Tokyo")
        self.assertEqual((cfg.lat, cfg.lon, cfg.factor, cfg.off_at),
                         (40.7, -74.0, 0.4, time(23, 15)))

    def test_blank_location_falls_back_to_timezone(self):
        cfg = self.load({"NIGHT_DIM": "1", "LAT": "", "LON": ""})
        self.assertAlmostEqual(cfg.lat, 40.714, places=3)

    def test_defaults(self):
        cfg = self.load({"NIGHT_DIM": "1"})
        self.assertEqual((cfg.factor, cfg.off_at), (0.5, time(22, 0)))

    def test_blank_off_at_disables_cutoff(self):
        cfg = self.load({"NIGHT_DIM": "1", "NIGHT_OFF_AT": ""})
        self.assertIsNone(cfg.off_at)

    def test_bad_values_disable_instead_of_crashing(self):
        # A typo in the config must not take the dial down with a crash loop
        for bad in ({"NIGHT_FACTOR": "half"}, {"NIGHT_OFF_AT": "10pm"},
                    {"LAT": "40,7", "LON": "1"}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertIsNone(self.load({"NIGHT_DIM": "1", **bad}), bad)
            self.assertIn("night dimming off", out.getvalue())

    def test_unknown_timezone_and_no_location_disables(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(self.load({"NIGHT_DIM": "1"}, zone="Etc/UTC"))


if __name__ == "__main__":
    unittest.main()
