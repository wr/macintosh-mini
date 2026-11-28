#!/usr/bin/env python3
"""Tests for brightness_control.py: its settings and the level from outside.

The schedule itself is tested in test_night_schedule.py.

Run: python3 -m unittest test_brightness_control
The lgpio module only exists on the Pi, so it is stubbed out here; nothing
under test touches GPIO.
"""

import contextlib
import io
import os
import socket
import sys
import tempfile
import types
import unittest
from datetime import date, datetime, timezone

sys.modules.setdefault("lgpio", types.ModuleType("lgpio"))

import brightness_control as bc  # noqa: E402
import night_schedule as ns  # noqa: E402

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


class Settings(unittest.TestCase):
    """The settings are read again when the file changes, and the place when
    the time zone does."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "brightness-control")

    def save(self, text):
        with open(self.path + ".new", "w") as f:
            f.write(text)
        os.replace(self.path + ".new", self.path)

    def test_no_file_is_off(self):
        s = bc.NightSettings(self.path, ZONE_TAB)
        s.refresh("America/New_York")
        self.assertFalse(s.cfg.on)

    def test_a_changed_file_is_read_again(self):
        s = bc.NightSettings(self.path, ZONE_TAB)
        self.assertTrue(s.refresh("America/New_York"))    # the first look
        self.assertFalse(s.refresh("America/New_York"))
        self.save("NIGHT_DIM=1\nNIGHT_FROM=21:30\nNIGHT_UNTIL=sunrise\nNIGHT_LEVEL=0\n")
        self.assertTrue(s.refresh("America/New_York"))
        self.assertEqual((s.cfg.on, s.cfg.from_, s.cfg.until, s.cfg.level),
                         (True, 21 * 60 + 30, ns.SUNRISE, 0))
        self.assertFalse(s.refresh("America/New_York"))

    def test_place_follows_the_time_zone(self):
        s = bc.NightSettings(self.path, ZONE_TAB)
        s.refresh("America/New_York")
        self.assertAlmostEqual(s.coords[0], 40.714, places=3)
        self.assertTrue(s.refresh("Asia/Tokyo"))
        self.assertAlmostEqual(s.coords[0], 35.654, places=3)
        self.assertTrue(s.refresh("Etc/UTC"))
        self.assertIsNone(s.coords)

    def test_place_set_by_hand_wins(self):
        self.save("NIGHT_DIM=1\nLAT=40.7\nLON=-74.0\n")
        s = bc.NightSettings(self.path, ZONE_TAB)
        s.refresh("Asia/Tokyo")
        self.assertEqual(s.coords, (40.7, -74.0))

    def test_bad_values_turn_dimming_off_instead_of_crashing(self):
        # A typo in the file must not take the dial down with a crash loop
        for bad in ("NIGHT_LEVEL=dim", "NIGHT_FROM=10pm", "NIGHT_UNTIL=25:00",
                    "LAT=40,7\nLON=1", "NIGHT_LEVEL=101"):
            self.save("NIGHT_DIM=1\n" + bad + "\n")
            s = bc.NightSettings(self.path, ZONE_TAB)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                s.refresh("America/New_York")
            self.assertFalse(s.cfg.on, bad)
            self.assertIn("night dimming off", out.getvalue())


class LevelFromOutside(unittest.TestCase):
    """Mac OS's brightness slider: a level sent to the socket."""

    def test_only_2_to_100_as_plain_digits(self):
        for good, value in ((b"2", 2), (b"100", 100), (b"57\n", 57)):
            self.assertEqual(bc.parse_level(good), value)
        for bad in (b"", b"1", b"0", b"101", b"-5", b"5.5", b"0x10", b"1000",
                    b"abc", b"5 5"):
            self.assertIsNone(bc.parse_level(bad), bad)

    def test_socket_takes_the_newest_level_and_anyone_may_send(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            sock = bc.open_control(d)
            self.addCleanup(sock.close)
            path = os.path.join(d, bc.LEVEL_SOCKET)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o666)
            self.assertIsNone(bc.read_control(sock))
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
                for data in (b"40", b"junk", b"73", b"900"):
                    s.sendto(data, path)
            self.assertEqual(bc.read_control(sock), 73)
            self.assertIsNone(bc.read_control(sock))

    def test_level_is_published_for_others_to_read(self):
        with tempfile.TemporaryDirectory() as d:
            bc.publish_level(64, d)
            with open(os.path.join(d, bc.LEVEL_FILE)) as f:
                self.assertEqual(f.read(), "64")


if __name__ == "__main__":
    unittest.main()
