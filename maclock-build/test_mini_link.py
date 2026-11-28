#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for mini_link.py, which answers the Mini's Mac OS software.

Run: python3 -m unittest test_mini_link
The replies are checked byte for byte against the contract in the Macintosh
Mini ESP32's mac/MiniLink.h.
"""

import os
import re
import select
import socket
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import mini_link as ml
import night_schedule as ns

HERE = Path(__file__).resolve().parent
SETUP = (HERE.parent / "setup.sh").read_text()

ZONE_TAB = ("# comment\n"
            "US\t+404251-0740023\tAmerica/New_York\tEastern (most areas)\n"
            "JP\t+353916+1394441\tAsia/Tokyo\n"
            "NO\t+7814+01540\tArctic/Longyearbyen\n")
ZONES = ["America/New_York", "Arctic/Longyearbyen", "Asia/Tokyo"]
NOON = datetime(2024, 3, 20, 12, tzinfo=ZoneInfo("America/New_York"))


def code(text):
    return struct.unpack(">H", text.encode())[0]


def request(text, p0=0, p1=0, p2=0):
    return b"Mi" + text.encode() + struct.pack(">hhh", p0, p1, p2)


class Framing(unittest.TestCase):

    def test_one_request(self):
        self.assertEqual(ml.Requests().feed(request("Mt", 1440, 1441, 7)),
                         [(code("Mt"), 1440, 1441, 7)])

    def test_parameters_are_signed(self):
        self.assertEqual(ml.Requests().feed(request("Ml", -1)), [(code("Ml"), -1, 0, 0)])

    def test_bytes_before_the_request_are_skipped(self):
        for junk in (b"\0\0", b"AT\r", b"M", b"MM", b"iM", b"Mx" * 5):
            self.assertEqual(ml.Requests().feed(junk + request("MS")),
                             [(code("MS"), 0, 0, 0)], junk)

    def test_a_request_in_pieces(self):
        whole = b"zz" + request("Mb", 55)
        for cut in range(1, len(whole)):
            r = ml.Requests()
            self.assertEqual(r.feed(whole[:cut]), [])
            self.assertEqual(r.feed(whole[cut:]), [(code("Mb"), 55, 0, 0)], cut)

    def test_one_byte_at_a_time(self):
        r, found = ml.Requests(), []
        for byte in b"\xff" + request("MC") + b"M" + request("MP"):
            found += r.feed(bytes([byte]))
        self.assertEqual(found, [(code("MC"), 0, 0, 0), (code("MP"), 0, 0, 0)])

    def test_several_at_once(self):
        self.assertEqual(ml.Requests().feed(request("MS") + b"??" + request("Md", 1)),
                         [(code("MS"), 0, 0, 0), (code("Md"), 1, 0, 0)])

    def test_junk_does_not_pile_up(self):
        r = ml.Requests()
        for _ in range(100):
            r.feed(b"x" * 1000)
        self.assertEqual(r.buf, b"")

    def test_reply_layout(self):
        self.assertEqual(ml.reply(code("MC"), b"abc"), b"MiMC\x00\x03abc")
        self.assertEqual(ml.reply(code("Mq")), b"MiMq\x00\x00")


def fake_power(tree):
    """A /sys/class/power_supply with the given {name: {file: text}}."""
    root = Path(tempfile.mkdtemp())
    for name, files in tree.items():
        (root / name).mkdir()
        for file, text in files.items():
            (root / name / file).write_text(text + "\n")
    return str(root)


class Battery(unittest.TestCase):

    def test_none_on_todays_boards(self):
        self.assertEqual(ml.read_battery(fake_power({})), (None, False))
        self.assertEqual(ml.read_battery("/nonexistent/power_supply"), (None, False))

    def test_a_gauge(self):
        root = fake_power({"max17048": {"type": "Battery", "capacity": "73",
                                        "status": "Discharging"}})
        self.assertEqual(ml.read_battery(root), (73, False))

    def test_charging(self):
        root = fake_power({"battery": {"type": "Battery", "capacity": "41",
                                       "status": "Charging"}})
        self.assertEqual(ml.read_battery(root), (41, True))

    def test_full_is_not_charging(self):
        root = fake_power({"battery": {"type": "Battery", "capacity": "100", "status": "Full"}})
        self.assertEqual(ml.read_battery(root), (100, False))

    def test_no_status_file(self):
        root = fake_power({"battery": {"type": "Battery", "capacity": "5"}})
        self.assertEqual(ml.read_battery(root), (5, False))

    def test_other_supplies_are_not_the_battery(self):
        root = fake_power({"ac": {"type": "Mains", "online": "1"},
                           "usb": {"type": "USB", "online": "1"},
                           "z-gauge": {"type": "Battery", "capacity": "88", "status": "Charging"}})
        self.assertEqual(ml.read_battery(root), (88, True))

    def test_a_bluetooth_keyboards_battery_is_not_the_minis(self):
        root = fake_power({"hid-00:11-battery": {"type": "Battery", "scope": "Device",
                                                 "capacity": "60", "status": "Discharging"}})
        self.assertEqual(ml.read_battery(root), (None, False))

    def test_a_reading_that_is_not_a_number(self):
        root = fake_power({"battery": {"type": "Battery", "capacity": "", "status": "Charging"}})
        self.assertEqual(ml.read_battery(root), (None, False))

    def test_kept_to_0_to_100(self):
        root = fake_power({"battery": {"type": "Battery", "capacity": "104"}})
        self.assertEqual(ml.read_battery(root), (100, False))


class Recorder:
    def __init__(self, result=True):
        self.calls, self.result = [], result

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        return self.result


class Replies(unittest.TestCase):

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.run_dir = Path(tempfile.mkdtemp())
        self.night_conf = self.home / "brightness-control"
        self.state = self.home / "macintosh-mini.conf"
        self.state.write_text("VERSION=1.12.0\nMACLOCK=1\nEMULATOR=basilisk\n")
        self.apply, self.spawn, self.send = Recorder(), Recorder(), Recorder()
        self.wifi = (b"Home Wi-Fi", -52, "192.168.1.23")
        self.power = fake_power({})
        self.zone = "America/New_York"

    def mini(self):
        return ml.Mini(home=str(self.home), power_supply=self.power,
                       run_dir=str(self.run_dir), install_state=str(self.state),
                       night_conf=str(self.night_conf), wifi=lambda: self.wifi,
                       apply=self.apply, spawn=self.spawn, send_level=self.send,
                       zone=self.zone, zone_tabs=(ZONE_TAB, ZONE_TAB), now=NOON)

    def ask(self, text, p0=0, p1=0, p2=0):
        """The reply's data, once its header is checked."""
        answer = self.mini().answer(code(text), p0, p1, p2)
        self.assertEqual(answer[:4], b"Mi" + text.encode())
        self.assertEqual(struct.unpack(">H", answer[4:6])[0], len(answer) - 6)
        return answer[6:]

    def result(self, text, p0=0, p1=0):
        data = self.ask(text, p0, p1)
        self.assertEqual(len(data), 2)
        return struct.unpack(">h", data)[0]

    def night(self, cfg):
        self.night_conf.write_text(ns.format_config(cfg))

    # 'MS'

    def test_status_with_no_battery(self):
        (self.home / ".macintosh_chime").write_text("Quadra\n")
        self.assertEqual(self.ask("MS"),
                         bytes.fromhex("0001" "0008" "ffff" "ffcc" "0004" "0008")
                         + b"\x0aHome Wi-Fi" + bytes(22) + b"\0"
                         + b"\x0c192.168.1.23" + bytes(3))

    def test_status_is_62_bytes(self):
        self.assertEqual(len(self.ask("MS")), 62)

    def test_status_flags(self):
        self.power = fake_power({"gauge": {"type": "Battery", "capacity": "73",
                                           "status": "Charging"}})
        self.night(ns.NightConfig(on=True))
        version, flags, battery, signal, chime, count = struct.unpack(">6h", self.ask("MS")[:12])
        self.assertEqual((version, flags, battery, signal, chime, count),
                         (1, 1 | 2 | 8 | 16, 73, -52, 0, 8))

    def test_battery_made_up_is_never_set(self):
        for power in ({}, {"g": {"type": "Battery", "capacity": "9", "status": "Charging"}}):
            self.power = fake_power(power)
            self.assertEqual(struct.unpack(">h", self.ask("MS")[2:4])[0] & 4, 0)

    def test_status_without_wifi(self):
        self.wifi = (b"", 0, "")
        data = self.ask("MS")
        self.assertEqual(struct.unpack(">6h", data[:12]), (1, 0, -1, 0, 0, 8))
        self.assertEqual(data[12:], bytes(50))

    def test_long_names_are_cut_to_fit(self):
        self.wifi = ("é".encode() * 40, -60, "255.255.255.255")
        data = self.ask("MS")
        self.assertEqual(len(data), 62)
        self.assertEqual(data[12:45], b"\x20" + b"\x8e" * 32)    # é in Mac OS's encoding
        self.assertEqual(data[46:62], b"\x0f255.255.255.255")

    # 'MC'

    def test_chimes(self):
        names = [b"Macintosh I (1984)", b"Macintosh II (1987)", b"Macintosh LC (1990)",
                 b"Quadra (1991)", b"Quadra AV (1993)", b"Power Mac (1994)",
                 b"Power Mac PCI", b"Twentieth Anniversary (1997)"]
        self.assertEqual(self.ask("MC"),
                         b"\x08" + b"".join(bytes([len(n)]) + n for n in names))

    def test_chimes_fit_the_menu_bar_items_buffer(self):
        self.assertLessEqual(len(self.ask("MC")), 512)

    # 'MP'

    def test_settings_defaults(self):
        (self.run_dir / "level").write_text("64")
        (self.home / ".macintosh_chime").write_text("Macintosh II\n")
        data = self.ask("MP")
        self.assertEqual(len(data), 136)
        self.assertEqual(struct.unpack(">10h", data[:20]),
                         (1, 64, 32, 22 * 60, 7 * 60, 20, 0, 3, 2, 8))
        self.assertEqual(data[20:36], b"\x061.12.0" + bytes(9))
        self.assertEqual(data[36:132], bytes(96))       # no update news
        sunset, sunrise = struct.unpack(">hh", data[132:])
        # New York, 20 March 2024: sunset 19:09, the next sunrise 06:57
        self.assertAlmostEqual(sunset, 19 * 60 + 9, delta=4)
        self.assertAlmostEqual(sunrise, 6 * 60 + 57, delta=4)

    def test_settings_as_set(self):
        self.night(ns.NightConfig(True, ns.SUNSET, ns.SUNRISE, 0))
        self.zone = "Asia/Tokyo"
        fields = struct.unpack(">10h", self.ask("MP")[:20])
        self.assertEqual(fields, (1, 100, 16 | 32, 1440, 1441, 0, 2, 3, 0, 8))

    def test_a_zone_without_a_place(self):
        self.zone = "Etc/UTC"
        data = self.ask("MP")
        flags, zone = struct.unpack(">h", data[4:6])[0], struct.unpack(">h", data[12:14])[0]
        self.assertEqual((flags & 32, zone), (0, -1))
        self.assertEqual(struct.unpack(">hh", data[132:]), (-1, -1))

    def test_polar_day_has_a_place_but_no_sun_times(self):
        self.zone = "Arctic/Longyearbyen"
        mini = self.mini()
        mini.now = datetime(2024, 6, 21, 12, tzinfo=ZoneInfo("Arctic/Longyearbyen"))
        data = mini.answer(code("MP"))[6:]
        self.assertEqual(struct.unpack(">h", data[4:6])[0] & 32, 32)
        self.assertEqual(struct.unpack(">hh", data[132:]), (-1, -1))

    def test_brightness_without_the_backlight_service(self):
        self.assertEqual(struct.unpack(">h", self.ask("MP")[2:4])[0], 100)

    def test_a_broken_settings_file_reads_as_off(self):
        self.night_conf.write_text("NIGHT_DIM=1\nNIGHT_LEVEL=lots\n")
        self.assertEqual(struct.unpack(">10h", self.ask("MP")[:20])[2:6],
                         (32, 22 * 60, 7 * 60, 20))

    def test_settings_from_before_1_12(self):
        self.night_conf.write_text("NIGHT_DIM=1\nLAT=\nLON=\nNIGHT_FACTOR=0.5\nNIGHT_OFF_AT=22:00\n")
        self.assertEqual(struct.unpack(">10h", self.ask("MP")[:20])[2:6],
                         (16 | 32, 1440, 1441, 50))

    # 'MZ'

    def test_zones(self):
        self.assertEqual(self.ask("MZ"), b"\x00\x03" + b"\x10America/New_York"
                         + b"\x13Arctic/Longyearbyen" + b"\x0aAsia/Tokyo")

    def test_the_real_zone_list_fits_the_control_panels_buffer(self):
        tab = ns.read_zone_tab((ns.ZONE_TAB,))
        if tab is None:
            self.skipTest("no tzdata zone table on this machine")
        mini = ml.Mini(home=str(self.home), zone_tabs=(tab, tab))
        data = mini.answer(code("MZ"))[6:]
        count = struct.unpack(">H", data[:2])[0]
        self.assertGreater(count, 300)
        self.assertLess(len(data), 12000)
        self.assertEqual(mini.zones(), sorted(mini.zones()))

    # 'Mc'

    def test_set_chime(self):
        (self.home / ".macintosh_chime").write_text("Macintosh II\n")
        self.assertEqual(self.result("Mc", 4), 0)
        self.assertEqual((self.home / ".macintosh_chime").read_text(), "Quadra\n")
        self.assertEqual(self.spawn.calls, [("--chime", "4", "Macintosh II")])
        self.assertEqual(struct.unpack(">h", self.ask("MS")[8:10])[0], 4)

    def test_set_no_chime(self):
        self.assertEqual(self.result("Mc", 0), 0)
        self.assertEqual((self.home / ".macintosh_chime").read_text(), "None\n")
        self.assertEqual(self.spawn.calls, [("--chime", "0", "")])
        self.assertEqual(struct.unpack(">h", self.ask("MS")[8:10])[0], 0)

    def test_a_chime_change_that_could_not_start_leaves_the_name_alone(self):
        (self.home / ".macintosh_chime").write_text("Macintosh II\n")
        self.spawn.result = False
        self.assertEqual(self.result("Mc", 4), ml.IO_ERR)
        self.assertEqual((self.home / ".macintosh_chime").read_text(), "Macintosh II\n")

    def test_set_chime_out_of_range(self):
        for bad in (-1, 9, 300):
            self.assertEqual(self.result("Mc", bad), -50)
        self.assertEqual(self.spawn.calls, [])
        self.assertFalse((self.home / ".macintosh_chime").exists())

    # 'Md', 'Mt', 'Ml'

    def test_set_dimming_on_and_off(self):
        self.assertEqual(self.result("Md", 1), 0)
        self.assertEqual(self.result("Md", 0), 0)
        self.assertEqual(self.apply.calls, [("night", 1, 22 * 60, 7 * 60, 20),
                                            ("night", 0, 22 * 60, 7 * 60, 20)])

    def test_set_dimming_out_of_range(self):
        for bad in (-1, 2):
            self.assertEqual(self.result("Md", bad), -50)
        self.assertEqual(self.apply.calls, [])

    def test_set_times_keeps_the_rest(self):
        self.night(ns.NightConfig(True, 60, 120, 35))
        self.assertEqual(self.result("Mt", 1440, 1441), 0)
        self.assertEqual(self.result("Mt", 0, 1439), 0)
        self.assertEqual(self.apply.calls, [("night", 1, 1440, 1441, 35),
                                            ("night", 1, 0, 1439, 35)])

    def test_set_times_out_of_range(self):
        for start, end in ((-1, 60), (1441, 60), (1442, 60), (60, -1), (60, 1440),
                           (60, 1442), (2000, 2000)):
            self.assertEqual(self.result("Mt", start, end), -50, (start, end))
        self.assertEqual(self.apply.calls, [])

    def test_set_how_dim(self):
        self.night(ns.NightConfig(True, ns.SUNSET, 300, 35))
        for level in (0, 100):
            self.assertEqual(self.result("Ml", level), 0)
        self.assertEqual(self.apply.calls, [("night", 1, 1440, 300, 0),
                                            ("night", 1, 1440, 300, 100)])

    def test_set_how_dim_out_of_range(self):
        for bad in (-1, 101):
            self.assertEqual(self.result("Ml", bad), -50)
        self.assertEqual(self.apply.calls, [])

    def test_a_setting_that_could_not_be_saved(self):
        self.apply.result = False
        self.assertEqual(self.result("Md", 1), ml.IO_ERR)

    # 'Mz'

    def test_set_zone_sends_the_name_the_list_numbers(self):
        self.assertEqual(self.result("Mz", 2), 0)
        self.assertEqual(self.result("Mz", 0), 0)
        self.assertEqual(self.apply.calls, [("zone", "Asia/Tokyo"), ("zone", "America/New_York")])

    def test_set_zone_out_of_range(self):
        for bad in (-1, 3):
            self.assertEqual(self.result("Mz", bad), -50)
        self.assertEqual(self.apply.calls, [])

    # 'Mb'

    def test_set_brightness(self):
        mini = self.mini()
        for level in (2, 100):
            self.assertEqual(mini.answer(code("Mb"), level), b"MiMb\x00\x02\x00\x00")
        self.assertEqual(self.send.calls, [(2, str(self.run_dir)), (100, str(self.run_dir))])
        # Read back at once, before the backlight service has written it down
        self.assertEqual(struct.unpack(">h", mini.answer(code("MP"))[8:10])[0], 100)

    def test_set_brightness_out_of_range(self):
        for bad in (-1, 0, 1, 101):
            self.assertEqual(self.result("Mb", bad), -50)
        self.assertEqual(self.send.calls, [])

    def test_set_brightness_without_the_backlight_service(self):
        self.send.result = False
        self.assertEqual(self.result("Mb", 50), ml.IO_ERR)

    def test_brightness_reaches_the_backlight_service(self):
        sys.modules.setdefault("lgpio", types.ModuleType("lgpio"))
        import brightness_control as bc
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            control = bc.open_control(d)
            self.addCleanup(control.close)
            self.assertTrue(ml.send_level(42, d))
            self.assertEqual(bc.read_control(control), 42)
        self.assertFalse(ml.send_level(42, "/nonexistent"))

    # 'Mp'

    def test_play_chime(self):
        self.assertEqual(self.result("Mp", 8), 0)
        self.assertEqual(self.spawn.calls, [("--play", "8")])

    def test_play_chime_out_of_range(self):
        for bad in (-1, 0, 9):
            self.assertEqual(self.result("Mp", bad), -50)
        self.assertEqual(self.spawn.calls, [])

    # Anything else

    def test_unknown_codes_get_an_empty_reply(self):
        for text in ("MX", "Mi", "ZZ", "\0\0"):
            self.assertEqual(self.mini().answer(code(text)), b"Mi" + text.encode() + b"\0\0")

    def test_an_error_inside_gets_an_empty_reply_not_silence(self):
        mini = self.mini()
        mini.wifi = lambda: 1 / 0
        self.assertEqual(mini.answer(code("MS")), b"MiMS\0\0")


class InstallerAgrees(unittest.TestCase):
    """The chimes are listed in setup.sh too; the numbers Mac OS uses come
    from the order."""

    def test_same_chimes_in_the_same_order(self):
        block = re.search(r"^CHIMES_DATA=\(\n(.*?)^\)", SETUP, re.S | re.M).group(1)
        listed = [tuple(line.strip().strip('"').split("|")) for line in block.splitlines()]
        self.assertEqual([(name, file) for name, _, file in ml.CHIMES],
                         [(name, file) for name, _, file in listed])
        for (_, year, _), (_, described, _) in zip(ml.CHIMES, listed):
            self.assertEqual(year, described if described.isdigit() else "")

    def test_same_crash_sounds(self):
        fn = re.search(r"^crash_for_chime\(\) \{\n.*?^\}\n", SETUP, re.S | re.M).group(0)
        for _, _, file in ml.CHIMES:
            out = subprocess.run(["bash", "-c", fn + f"crash_for_chime {file}"],
                                 capture_output=True, text=True).stdout.strip()
            self.assertEqual(ml.CRASHES[file], out)

    def test_every_sound_is_in_the_repository(self):
        chimes = HERE.parent / "emulators" / "chimes"
        for name in [c[2] for c in ml.CHIMES] + list(ml.CRASHES.values()):
            self.assertTrue((chimes / f"{name}.wav").is_file(), name)
        self.assertTrue(ml.CHIME_URL.endswith("/wr/macintosh-mini/main/emulators/chimes/"))


WAV = b"RIFF\x24\0\0\0WAVEfmt " + bytes(24)


class Chimes(unittest.TestCase):

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.cache = os.path.join(self.home, ".cache", "mini-link")
        self.apply = Recorder()
        self.fetched = []

    def fetch(self, name, cache):
        self.fetched.append(name)
        os.makedirs(cache, exist_ok=True)
        path = os.path.join(cache, name + ".wav")
        Path(path).write_bytes(WAV + name.encode())
        return path

    def no_network(self, name, cache):
        raise OSError("offline")

    def test_install_puts_the_chime_and_its_crash_sound_in_place(self):
        ok = ml.install_chime(3, "Macintosh II", self.home, self.cache, self.fetch, self.apply)
        self.assertTrue(ok)
        self.assertEqual(self.fetched, ["StartupMacLC", "CrashMacLC"])
        self.assertEqual(Path(self.home, "chime.wav").read_bytes(), WAV + b"StartupMacLC")
        self.assertEqual(Path(self.home, "crash.wav").read_bytes(), WAV + b"CrashMacLC")
        self.assertEqual(self.apply.calls, [("sounds",)])

    def test_no_chime_removes_it(self):
        Path(self.home, "chime.wav").write_bytes(WAV)
        self.assertTrue(ml.install_chime(0, "Quadra", self.home, self.cache, self.fetch, self.apply))
        self.assertFalse(Path(self.home, "chime.wav").exists())
        self.assertEqual((self.fetched, self.apply.calls), ([], [("sounds",)]))

    def test_a_failed_download_puts_the_name_back(self):
        tag = Path(self.home, ".macintosh_chime")
        tag.write_text("Quadra\n")      # what 'Mc' wrote before starting this
        Path(self.home, "chime.wav").write_bytes(WAV + b"old")
        ok = ml.install_chime(4, "Macintosh II", self.home, self.cache, self.no_network, self.apply)
        self.assertFalse(ok)
        self.assertEqual(tag.read_text(), "Macintosh II\n")
        self.assertEqual(Path(self.home, "chime.wav").read_bytes(), WAV + b"old")
        self.assertEqual(self.apply.calls, [])

    def test_a_failed_install_puts_the_name_back(self):
        tag = Path(self.home, ".macintosh_chime")
        tag.write_text("Quadra\n")
        self.apply.result = False
        self.assertFalse(ml.install_chime(4, "", self.home, self.cache, self.fetch, self.apply))
        self.assertFalse(tag.exists())      # there was no name before
        self.assertFalse(Path(self.home, "chime.wav").exists())

    def test_a_failed_install_puts_the_home_folders_chime_back(self):
        Path(self.home, "chime.wav").write_bytes(WAV + b"old")
        self.apply.result = False
        for n in (4, 0):
            self.assertFalse(ml.install_chime(n, "Quadra", self.home, self.cache, self.fetch, self.apply))
            self.assertEqual(Path(self.home, "chime.wav").read_bytes(), WAV + b"old")

    def test_a_downloaded_sound_is_kept(self):
        os.makedirs(self.cache)
        Path(self.cache, "StartupMacI.wav").write_bytes(WAV)
        self.assertEqual(ml.fetch_sound("StartupMacI", self.cache),
                         os.path.join(self.cache, "StartupMacI.wav"))

    def test_only_a_wav_counts(self):
        good, bad = Path(self.home, "a.wav"), Path(self.home, "b.wav")
        good.write_bytes(WAV)
        bad.write_bytes(b"<html>404</html>")
        self.assertTrue(ml.is_wav(str(good)))
        self.assertFalse(ml.is_wav(str(bad)))
        self.assertFalse(ml.is_wav(os.path.join(self.home, "missing.wav")))

    def test_a_download_that_is_not_a_wav_is_thrown_away(self):
        bin_dir = Path(tempfile.mkdtemp())
        (bin_dir / "curl").write_text('#!/bin/sh\nwhile [ "$1" != -o ]; do shift; done\n'
                                      'echo "<html>" > "$2"\n')
        (bin_dir / "curl").chmod(0o755)
        path = os.environ["PATH"]
        os.environ["PATH"] = f"{bin_dir}:{path}"
        try:
            with self.assertRaises(OSError):
                ml.fetch_sound("StartupMacI", self.cache)
        finally:
            os.environ["PATH"] = path
        self.assertEqual(os.listdir(self.cache), [])


class WifiReading(unittest.TestCase):

    PROC = ("Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n"
            " face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n"
            " wlan0: 0000   58.  -52.  -256        0      0      0      0      0        0\n")

    def test_signal_from_the_kernels_table(self):
        path = Path(tempfile.mkdtemp(), "wireless")
        path.write_text(self.PROC)
        self.assertEqual(ml.wifi_signal("wlan0", str(path)), -52)
        self.assertEqual(ml.wifi_signal("wlan1", str(path)), 0)
        self.assertEqual(ml.wifi_signal("wlan0", "/nonexistent"), 0)

    def test_interface_is_the_one_with_a_wireless_folder(self):
        root = Path(tempfile.mkdtemp())
        for name in ("eth0", "lo", "wlan0"):
            (root / name).mkdir()
        (root / "wlan0" / "wireless").mkdir()
        self.assertEqual(ml.wifi_interface(str(root)), "wlan0")
        self.assertIsNone(ml.wifi_interface("/nonexistent"))


class OnAPty(unittest.TestCase):
    """The whole program, run the way Basilisk II runs it: on a pty in raw
    mode that is its stdin, stdout and stderr."""

    def setUp(self):
        import pty
        import tty
        self.master, slave = pty.openpty()
        tty.setraw(slave)       # serial_unix.cpp does this before the Mac can write
        env = dict(os.environ, HOME=tempfile.mkdtemp())
        self.child = subprocess.Popen([sys.executable, "-SE", str(HERE / "mini_link.py")],
                                      stdin=slave, stdout=slave, stderr=slave, env=env,
                                      start_new_session=True)
        os.close(slave)
        self.addCleanup(self.child.kill)

    def read(self, n):
        data = b""
        while len(data) < n:
            ready, _, _ = select.select([self.master], [], [], 10)
            self.assertTrue(ready, f"no reply; got {data!r}")
            data += os.read(self.master, n - len(data))
        return data

    def test_answers_and_ends_when_the_port_closes(self):
        # The first request is already waiting when the program starts
        os.write(self.master, b"\r\n\x03" + request("MC") + request("M?") + request("Mb", 1))
        header = self.read(6)
        self.assertEqual(header[:4], b"MiMC")
        data = self.read(struct.unpack(">H", header[4:])[0])
        self.assertEqual(data[0], 8)
        self.assertEqual(self.read(6), b"MiM?\0\0")
        self.assertEqual(self.read(8), b"MiMb\x00\x02\xff\xce")
        os.write(self.master, request("MS"))
        self.assertEqual(self.read(6), b"MiMS\x00\x3e")
        self.assertEqual(len(self.read(62)), 62)
        # Nothing else was ever written: no echo, no messages
        self.assertEqual(select.select([self.master], [], [], 0.2)[0], [])
        os.close(self.master)
        self.child.wait(10)     # serial_unix.cpp waits for it too


if __name__ == "__main__":
    unittest.main()
