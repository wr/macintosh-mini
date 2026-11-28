#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for mini_link_apply.py, the one program mini-link may run as root.

Run: python3 -m unittest test_mini_link_apply
Everything it's given is checked as if a stranger had typed it.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

import mini_link_apply as apply
import night_schedule as ns

ZONE_TAB = ("# comment\n"
            "US\t+404251-0740023\tAmerica/New_York\tEastern (most areas)\n"
            "JP\t+353916+1394441\tAsia/Tokyo\n")
WAV = b"RIFF\x24\0\0\0WAVEfmt " + bytes(24)


class Zone(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.tab = self.dir / "zone.tab"
        self.tab.write_text(ZONE_TAB)
        self.zoneinfo = self.dir / "zoneinfo"
        for name in ("America/New_York", "Asia/Tokyo", "Etc/UTC"):
            (self.zoneinfo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.zoneinfo / name).write_text("TZif")
        self.localtime = self.dir / "localtime"
        self.localtime.symlink_to(self.zoneinfo / "Etc/UTC")
        self.timezone = self.dir / "timezone"

    def set(self, name):
        apply.set_zone(name, str(self.tab), str(self.zoneinfo), str(self.localtime),
                       str(self.timezone))

    def test_points_localtime_at_the_zone(self):
        self.set("Asia/Tokyo")
        self.assertEqual(os.readlink(self.localtime), str(self.zoneinfo / "Asia/Tokyo"))
        self.assertEqual(os.listdir(self.dir).count("localtime"), 1)
        self.assertFalse(self.timezone.exists())    # not made where there's none

    def test_keeps_etc_timezone_in_step_where_there_is_one(self):
        self.timezone.write_text("Etc/UTC\n")
        self.set("America/New_York")
        self.assertEqual(self.timezone.read_text(), "America/New_York\n")

    def test_only_a_zone_in_the_table(self):
        for bad in ("Etc/UTC", "../../etc/shadow", "/etc/passwd", "", "Asia/Tokyo\n",
                    "Asia/Tokyo/../../Etc/UTC", "asia/tokyo", "Asia"):
            with self.assertRaises(apply.Refused, msg=bad):
                self.set(bad)
        self.assertEqual(os.readlink(self.localtime), str(self.zoneinfo / "Etc/UTC"))

    def test_a_listed_zone_with_no_file_is_refused(self):
        (self.zoneinfo / "Asia/Tokyo").unlink()
        with self.assertRaises(apply.Refused):
            self.set("Asia/Tokyo")


class Night(unittest.TestCase):

    def setUp(self):
        self.path = Path(tempfile.mkdtemp(), "brightness-control")

    def test_saves_the_four_settings(self):
        apply.set_night("1", "1440", "1441", "0", str(self.path))
        self.assertEqual(ns.load_config(str(self.path)),
                         ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 0))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o644)
        self.assertEqual(os.listdir(self.path.parent), ["brightness-control"])

    def test_keeps_a_place_set_by_hand(self):
        self.path.write_text("NIGHT_DIM=0\nLAT=51.5\nLON=-0.13\n")
        apply.set_night("1", "1320", "420", "20", str(self.path))
        self.assertEqual(ns.load_config(str(self.path)),
                         ns.NightConfig(True, 1320, 420, 20, 51.5, -0.13))

    def test_moves_a_file_from_before_1_12(self):
        self.path.write_text("NIGHT_DIM=1\nLAT=\nLON=\nNIGHT_FACTOR=0.5\nNIGHT_OFF_AT=22:00\n")
        apply.set_night("0", "1440", "1441", "50", str(self.path))
        text = self.path.read_text()
        self.assertNotIn("NIGHT_FACTOR", text)
        self.assertIn("NIGHT_FROM=sunset", text)

    def test_replaces_a_broken_file(self):
        self.path.write_text("NIGHT_DIM=1\nNIGHT_LEVEL=lots\n")
        apply.set_night("1", "60", "120", "5", str(self.path))
        self.assertEqual(ns.load_config(str(self.path)), ns.NightConfig(True, 60, 120, 5))

    def test_refuses_anything_out_of_range(self):
        good = ["1", "1320", "420", "20"]
        for at, bad in ((0, "2"), (0, "-1"), (0, "yes"), (0, ""),
                        (1, "1441"), (1, "1442"), (1, "-1"), (1, "22:00"),
                        (2, "1440"), (2, "1442"), (2, "sunrise"),
                        (3, "101"), (3, "-1"), (3, "1e1"), (3, "20\nLAT=1"), (3, "٢٠"),
                        (3, "00020"), (3, " 20")):
            args = list(good)
            args[at] = bad
            with self.assertRaises(apply.Refused, msg=(at, bad)):
                apply.set_night(*args, str(self.path))
        self.assertFalse(self.path.exists())


class Sounds(unittest.TestCase):

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.dest = Path(tempfile.mkdtemp())
        self.me = os.getuid()

    def install(self, owner=None):
        apply.install_sounds(str(self.home), self.me if owner is None else owner,
                             str(self.dest))

    def test_installs_both(self):
        (self.home / "chime.wav").write_bytes(WAV + b"chime")
        (self.home / "crash.wav").write_bytes(WAV + b"crash")
        self.install()
        self.assertEqual((self.dest / "chime.wav").read_bytes(), WAV + b"chime")
        self.assertEqual((self.dest / "crash.wav").read_bytes(), WAV + b"crash")
        self.assertEqual((self.dest / "chime.wav").stat().st_mode & 0o777, 0o644)
        self.assertEqual(sorted(os.listdir(self.dest)), ["chime.wav", "crash.wav"])

    def test_no_chime_removes_the_installed_one_and_keeps_the_crash_sound(self):
        (self.dest / "chime.wav").write_bytes(WAV)
        (self.dest / "crash.wav").write_bytes(WAV)
        self.install()
        self.assertEqual(os.listdir(self.dest), ["crash.wav"])

    def test_refuses_what_is_not_a_wav(self):
        (self.home / "chime.wav").write_bytes(b"#!/bin/sh\nrm -rf /\n")
        with self.assertRaises(apply.Refused):
            self.install()
        self.assertEqual(os.listdir(self.dest), [])

    def test_refuses_a_link_to_someone_elses_file(self):
        secret = self.dest / "secret"
        secret.write_bytes(WAV + b"not yours")
        (self.home / "chime.wav").symlink_to(secret)
        with self.assertRaises(apply.Refused):
            self.install()
        self.assertEqual(os.listdir(self.dest), ["secret"])

    def test_refuses_a_file_the_caller_does_not_own(self):
        (self.home / "chime.wav").write_bytes(WAV)
        with self.assertRaises(apply.Refused):
            self.install(owner=self.me + 1)

    def test_refuses_a_folder_and_a_huge_file(self):
        (self.home / "chime.wav").mkdir()
        with self.assertRaises(apply.Refused):
            self.install()
        (self.home / "chime.wav").rmdir()
        with open(self.home / "chime.wav", "wb") as f:
            f.write(WAV)
            f.truncate(apply.MOST_SOUND_BYTES + 1)
        with self.assertRaises(apply.Refused):
            self.install()

    def test_every_chime_in_the_repository_is_small_enough(self):
        chimes = Path(__file__).resolve().parent.parent / "emulators" / "chimes"
        for wav in chimes.glob("*.wav"):
            self.assertLess(wav.stat().st_size, apply.MOST_SOUND_BYTES, wav.name)


class CommandLine(unittest.TestCase):

    def run_main(self, *args, env=None):
        old = dict(os.environ)
        os.environ.pop("SUDO_UID", None)
        os.environ.update(env or {})
        try:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                return apply.main(["mini-link-apply", *args]), err.getvalue()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_refuses_anything_else(self):
        for args in ((), ("zone",), ("zone", "a", "b"), ("night", "1", "2", "3"),
                     ("sounds", "/etc/shadow"), ("shell",), ("night", "1", "2", "3", "4", "5")):
            status, err = self.run_main(*args)
            self.assertEqual(status, 2, args)
            self.assertIn("usage", err)

    def test_bad_values_exit_2_and_say_why(self):
        status, err = self.run_main("night", "1", "9999", "420", "20")
        self.assertEqual(status, 2)
        self.assertIn("out of range", err)
        status, err = self.run_main("zone", "../../etc/shadow")
        self.assertEqual(status, 2)

    def test_sounds_needs_sudo(self):
        status, err = self.run_main("sounds")
        self.assertEqual((status, err), (2, "mini-link-apply: run this through sudo\n"))

    def test_asks_only_for_what_mini_link_sends(self):
        # mini_link.py's calls, spelled here so a change to either shows up
        import mini_link
        calls = []
        mini = mini_link.Mini(home=tempfile.mkdtemp(), night_conf="/nonexistent",
                              apply=lambda *a, **k: calls.append(a) or True,
                              zone_tabs=(ZONE_TAB, ZONE_TAB))
        mini.set_dim(1)
        mini.set_zone(1)
        self.assertEqual(calls, [("night", 1, 1320, 420, 20), ("zone", "Asia/Tokyo")])


if __name__ == "__main__":
    unittest.main()
