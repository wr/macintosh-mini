#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for night_schedule.py: the settings file, sunset and sunrise, and
when the screen dims.

Run: python3 -m unittest test_night_schedule
"""

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import night_schedule as ns

ZONE_TAB = """\
# comment line
#codes\tcoordinates\tTZ\tcomments
US\t+404251-0740023\tAmerica/New_York\tEastern (most areas)
NO\t+7814+01540\tArctic/Longyearbyen
JP\t+353916+1394441\tAsia/Tokyo
AU\t-3133+15905\tAustralia/Lord_Howe\tLord Howe Island
"""

NEW_YORK = ZoneInfo("America/New_York")
NY_PLACE = (40.714, -74.006)


def at(hour, minute=0, day=(2024, 3, 20), tz=NEW_YORK):
    return datetime(*day, hour, minute, tzinfo=tz)


class Config(unittest.TestCase):

    def test_no_settings_is_off_with_the_defaults(self):
        cfg = ns.parse_config("")
        self.assertEqual((cfg.on, cfg.from_, cfg.until, cfg.level, cfg.lat, cfg.lon),
                         (False, 22 * 60, 7 * 60, 20, None, None))

    def test_reads_every_setting(self):
        cfg = ns.parse_config("# a comment\nNIGHT_DIM=1\nNIGHT_FROM=21:30\n"
                              "NIGHT_UNTIL=06:05\nNIGHT_LEVEL=0\nLAT=40.7\nLON=-74.0\n")
        self.assertEqual((cfg.on, cfg.from_, cfg.until, cfg.level, cfg.lat, cfg.lon),
                         (True, 21 * 60 + 30, 6 * 60 + 5, 0, 40.7, -74.0))

    def test_sunset_and_sunrise(self):
        cfg = ns.parse_config("NIGHT_DIM=1\nNIGHT_FROM=sunset\nNIGHT_UNTIL=Sunrise\n")
        self.assertEqual((cfg.from_, cfg.until), (ns.SUNSET, ns.SUNRISE))

    def test_what_is_written_reads_back_the_same(self):
        for cfg in (ns.NightConfig(),
                    ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 50),
                    ns.NightConfig(True, 0, 23 * 60 + 59, 0, 59.917, 10.75),
                    ns.NightConfig(False, 5, 65, 100, -33.5, 151.25)):
            self.assertEqual(ns.parse_config(ns.format_config(cfg)), cfg)

    def test_bad_values_are_refused(self):
        for bad in ("NIGHT_FROM=10pm", "NIGHT_FROM=24:00", "NIGHT_FROM=sunrise",
                    "NIGHT_UNTIL=sunset", "NIGHT_UNTIL=7:00", "NIGHT_UNTIL=07:60",
                    "NIGHT_LEVEL=101", "NIGHT_LEVEL=-1", "NIGHT_LEVEL=half",
                    "LAT=91\nLON=0", "LAT=north\nLON=0"):
            with self.assertRaises(ValueError, msg=bad):
                ns.parse_config("NIGHT_DIM=1\n" + bad + "\n")

    def test_blank_values_mean_the_defaults(self):
        cfg = ns.parse_config("NIGHT_DIM=1\nNIGHT_FROM=\nNIGHT_UNTIL=\nNIGHT_LEVEL=\nLAT=\nLON=\n")
        self.assertEqual(cfg, ns.NightConfig(on=True))


class Migration(unittest.TestCase):
    """Before 1.12 the file held NIGHT_FACTOR and NIGHT_OFF_AT: half the dial
    level from sunset, dark from a set time until an hour before sunrise."""

    OLD = ("NIGHT_DIM=%s\nLAT=%s\nLON=%s\n# Sunset to sunrise, the dial level is "
           "multiplied by this\nNIGHT_FACTOR=0.5\nNIGHT_OFF_AT=%s\n")

    def test_on_becomes_sunset_to_sunrise_at_50(self):
        for off_at in ("22:00", "01:00", ""):
            cfg = ns.parse_config(self.OLD % (1, "", "", off_at))
            self.assertEqual(cfg, ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 50))

    def test_off_stays_off_with_the_defaults(self):
        self.assertEqual(ns.parse_config(self.OLD % (0, "", "", "22:00")), ns.NightConfig())

    def test_a_place_set_by_hand_is_kept(self):
        cfg = ns.parse_config(self.OLD % (1, "51.5", "-0.13", "22:00"))
        self.assertEqual((cfg.lat, cfg.lon), (51.5, -0.13))

    def test_a_file_already_moved_is_left_alone(self):
        text = ns.format_config(ns.NightConfig(True, 23 * 60, 6 * 60, 10))
        self.assertEqual(ns.parse_config(text + "NIGHT_FACTOR=0.5\n"),
                         ns.NightConfig(True, 23 * 60, 6 * 60, 10))


class Zones(unittest.TestCase):

    def test_names_sorted_without_comments(self):
        self.assertEqual(ns.zone_names(ZONE_TAB),
                         ["America/New_York", "Arctic/Longyearbyen", "Asia/Tokyo",
                          "Australia/Lord_Howe"])

    def test_no_table_no_names(self):
        self.assertEqual(ns.zone_names(None), [])

    def test_place_is_the_zones_unless_set_by_hand(self):
        cfg = ns.NightConfig()
        self.assertAlmostEqual(ns.place(cfg, "Asia/Tokyo", ZONE_TAB)[0], 35.654, places=3)
        self.assertIsNone(ns.place(cfg, "Etc/UTC", ZONE_TAB))
        cfg.lat, cfg.lon = 1.5, 2.5
        self.assertEqual(ns.place(cfg, "Etc/UTC", ZONE_TAB), (1.5, 2.5))


class SunMinutes(unittest.TestCase):
    # New York at the March equinox, 2024: sunrise 06:59, sunset 19:09 EDT
    # (NOAA solar calculator).

    def test_sunset_and_sunrise_in_local_minutes(self):
        now = at(12)
        self.assertAlmostEqual(ns.sun_minutes(NY_PLACE, now, True), 19 * 60 + 9, delta=4)
        self.assertAlmostEqual(ns.sun_minutes(NY_PLACE, now, False), 6 * 60 + 59, delta=4)

    def test_tomorrows_sunrise(self):
        # A day on, sunrise is a minute or two earlier
        today = ns.sun_minutes(NY_PLACE, at(12), False)
        tomorrow = ns.sun_minutes(NY_PLACE, at(12), False, 1)
        self.assertIn(today - tomorrow, (1, 2))

    def test_not_known_without_a_place(self):
        self.assertIsNone(ns.sun_minutes(None, at(12), True))

    def test_not_known_in_polar_day_and_night(self):
        svalbard = ns.zone_coords("Arctic/Longyearbyen", ZONE_TAB)
        tz = ZoneInfo("Arctic/Longyearbyen")
        for day in ((2024, 6, 21), (2024, 12, 21)):
            now = at(12, day=day, tz=tz)
            self.assertIsNone(ns.sun_minutes(svalbard, now, True))
            self.assertIsNone(ns.sun_minutes(svalbard, now, False))


class Window(unittest.TestCase):

    def test_inside_one_day(self):
        self.assertFalse(ns.in_window(59, 60, 120))
        self.assertTrue(ns.in_window(60, 60, 120))
        self.assertTrue(ns.in_window(119, 60, 120))
        self.assertFalse(ns.in_window(120, 60, 120))

    def test_crossing_midnight(self):
        start, end = 22 * 60, 7 * 60
        self.assertFalse(ns.in_window(21 * 60 + 59, start, end))
        self.assertTrue(ns.in_window(22 * 60, start, end))
        self.assertTrue(ns.in_window(23 * 60 + 59, start, end))
        self.assertTrue(ns.in_window(0, start, end))
        self.assertTrue(ns.in_window(6 * 60 + 59, start, end))
        self.assertFalse(ns.in_window(7 * 60, start, end))
        self.assertFalse(ns.in_window(12 * 60, start, end))

    def test_same_start_and_end_is_never(self):
        self.assertFalse(ns.in_window(300, 300, 300))


class IsNight(unittest.TestCase):

    def test_off_is_never_night(self):
        self.assertFalse(ns.is_night(ns.NightConfig(on=False), NY_PLACE, at(23)))

    def test_default_times_cross_midnight(self):
        cfg = ns.NightConfig(on=True)
        self.assertEqual([ns.is_night(cfg, None, at(h, m)) for h, m in
                          ((21, 59), (22, 0), (0, 0), (3, 30), (6, 59), (7, 0), (12, 0))],
                         [False, True, True, True, True, False, False])

    def test_sunset_to_sunrise_follows_the_sun(self):
        cfg = ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 50)
        # Sunset 19:09, sunrise 06:59 that day
        self.assertFalse(ns.is_night(cfg, NY_PLACE, at(19, 0)))
        self.assertTrue(ns.is_night(cfg, NY_PLACE, at(19, 20)))
        self.assertTrue(ns.is_night(cfg, NY_PLACE, at(2, 0)))
        self.assertTrue(ns.is_night(cfg, NY_PLACE, at(6, 50)))
        self.assertFalse(ns.is_night(cfg, NY_PLACE, at(7, 10)))

    def test_sunset_to_a_clock_time(self):
        cfg = ns.NightConfig(True, ns.SUNSET, 5 * 60, 50)
        self.assertTrue(ns.is_night(cfg, NY_PLACE, at(4, 59)))
        self.assertFalse(ns.is_night(cfg, NY_PLACE, at(5, 0)))

    def test_no_place_means_19_00_and_07_00(self):
        cfg = ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 50)
        self.assertEqual([ns.is_night(cfg, None, at(h, m)) for h, m in
                          ((18, 59), (19, 0), (6, 59), (7, 0))],
                         [False, True, True, False])

    def test_polar_day_and_night_mean_19_00_and_07_00(self):
        cfg = ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 50)
        svalbard = ns.zone_coords("Arctic/Longyearbyen", ZONE_TAB)
        tz = ZoneInfo("Arctic/Longyearbyen")
        for day in ((2024, 6, 21), (2024, 12, 21)):
            self.assertEqual([ns.is_night(cfg, svalbard, at(h, m, day=day, tz=tz))
                              for h, m in ((18, 59), (19, 0), (6, 59), (7, 0))],
                             [False, True, True, False])

    def test_fallbacks_are_19_00_and_07_00(self):
        self.assertEqual((ns.FALLBACK_SUNSET, ns.FALLBACK_SUNRISE), (19 * 60, 7 * 60))


class ScheduleTest(unittest.TestCase):
    """Acts when night starts and ends; the dial wins in between."""

    def test_night_starts_dims_and_remembers(self):
        s = ns.Schedule()
        self.assertIsNone(s.update(False, 80, 20))
        self.assertEqual(s.update(True, 80, 20), 20)
        self.assertEqual(s.day_level, 80)

    def test_night_ends_goes_back_to_the_remembered_level(self):
        s = ns.Schedule()
        s.update(False, 80, 20)
        s.update(True, 80, 20)
        self.assertIsNone(s.update(True, 20, 20))
        self.assertEqual(s.update(False, 20, 20), 80)

    def test_already_dimmer_than_how_dim_is_left_alone(self):
        s = ns.Schedule()
        s.update(False, 10, 20)
        self.assertIsNone(s.update(True, 10, 20))
        self.assertEqual(s.update(False, 10, 20), 10)

    def test_level_0_turns_the_screen_off(self):
        s = ns.Schedule()
        s.update(False, 60, 0)
        self.assertEqual(s.update(True, 60, 0), 0)
        self.assertEqual(s.update(False, 0, 0), 60)

    def test_the_dial_wins_until_the_next_night_starts(self):
        s = ns.Schedule()
        s.update(False, 80, 20)
        self.assertEqual(s.update(True, 80, 20), 20)
        # Turned up at night: every later check leaves it alone
        for _ in range(5):
            self.assertIsNone(s.update(True, 65, 20))
        # Morning: back to what it was when night started
        self.assertEqual(s.update(False, 65, 20), 80)
        for _ in range(5):
            self.assertIsNone(s.update(False, 80, 20))
        # The next night starts: dimmed again
        self.assertEqual(s.update(True, 80, 20), 20)

    def test_starting_up_at_night_dims(self):
        s = ns.Schedule()
        self.assertEqual(s.update(True, 100, 20), 20)
        self.assertEqual(s.update(False, 20, 20), 100)

    def test_starting_up_by_day_changes_nothing(self):
        s = ns.Schedule()
        self.assertIsNone(s.update(False, 100, 20, changed=True))
        self.assertIsNone(s.update(False, 100, 20))

    def test_turned_off_at_night_goes_back_at_once(self):
        s = ns.Schedule()
        s.update(False, 80, 20)
        s.update(True, 80, 20)
        self.assertEqual(s.update(False, 20, 20, changed=True), 80)
        self.assertIsNone(s.update(False, 80, 20))

    def test_starting_up_at_night_with_off_leaves_the_screen_alone(self):
        s = ns.Schedule()
        self.assertIsNone(s.update(True, 100, 0))
        for _ in range(5):
            self.assertIsNone(s.update(True, 100, 0))
        self.assertIsNone(s.update(False, 100, 0))
        # The next night starts: off, as set
        self.assertEqual(s.update(True, 100, 0), 0)
        self.assertEqual(s.update(False, 0, 0), 100)

    def test_how_dim_changed_at_night_applies_at_once(self):
        s = ns.Schedule()
        s.update(False, 80, 20)
        s.update(True, 80, 20)
        self.assertEqual(s.update(True, 20, 10, changed=True), 10)
        self.assertIsNone(s.update(True, 10, 10))
        self.assertEqual(s.update(True, 10, 0), 0)
        self.assertEqual(s.update(False, 0, 0), 80)

    def test_how_dim_raised_at_night_does_not_brighten(self):
        s = ns.Schedule()
        s.update(False, 80, 20)
        s.update(True, 80, 20)
        self.assertIsNone(s.update(True, 20, 50, changed=True))
        # The dial then wins as usual: 50 is not applied again
        self.assertIsNone(s.update(True, 70, 50))
        self.assertEqual(s.update(False, 70, 50), 80)

    def test_off_chosen_after_starting_up_at_night_turns_the_screen_off(self):
        s = ns.Schedule()
        self.assertEqual(s.update(True, 100, 20), 20)
        self.assertEqual(s.update(True, 20, 0, changed=True), 0)

    def test_other_changes_at_night_leave_the_backlight_alone(self):
        # The chime, the zone, the times (still inside the window)
        s = ns.Schedule()
        s.update(False, 80, 20)
        s.update(True, 80, 20)
        for _ in range(3):
            self.assertIsNone(s.update(True, 65, 20, changed=True))

    def test_times_moved_so_night_starts_now_dims_even_to_off(self):
        s = ns.Schedule()
        s.update(False, 80, 0)
        self.assertEqual(s.update(True, 80, 0, changed=True), 0)

    def test_a_whole_day_through_the_clock(self):
        # 22:00 to 07:00 at 20, checked every minute from noon to noon
        cfg = ns.NightConfig(on=True)
        s, level, moves = ns.Schedule(), 90, []
        now = at(12)
        for _ in range(24 * 60):
            target = s.update(ns.is_night(cfg, None, now), level, cfg.level)
            if target is not None and target != level:
                level = target
                moves.append((now.hour, now.minute, level))
            now += timedelta(minutes=1)
        self.assertEqual(moves, [(22, 0, 20), (7, 0, 90)])


class Times(unittest.TestCase):

    def test_format(self):
        self.assertEqual([ns.format_time(t) for t in (0, 7 * 60 + 5, 1439, ns.SUNSET, ns.SUNRISE)],
                         ["00:00", "07:05", "23:59", "sunset", "sunrise"])

    def test_utc_offsets_do_not_matter_to_clock_times(self):
        cfg = ns.NightConfig(on=True)
        tokyo = timezone(timedelta(hours=9))
        self.assertTrue(ns.is_night(cfg, None, at(22, 30, tz=tokyo)))


if __name__ == "__main__":
    unittest.main()
