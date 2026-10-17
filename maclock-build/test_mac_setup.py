#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the setup service's decisions in mac_setup.py.

Run: python3 -m unittest test_mac_setup
NetworkManager and the system are faked; nothing here touches the network.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import mac_setup as ms
from test_mac_setup_rom import make_rom

ZONE_TAB = """# tz zone descriptions
US\t+404251-0740023\tAmerica/New_York\tEastern (most areas)
DE\t+5230+01322\tEurope/Berlin\tmost of Germany
GB\t+513030-0000731\tEurope/London
"""


class FakeNM:
    def __init__(self, saved=(), ip=None, scan=('Home', 'Cafe'), join_ok=True):
        self.saved = list(saved)
        self._ip = ip
        self._scan = list(scan)
        self.scans = None        # optional list of results, one per scan
        self.on_scan = None      # optional hook run at scan time
        self.join_ok = join_ok
        self.join_error = None   # exception join() raises
        self.saved_error = None  # exception saved_wifi() raises
        self.wired = False
        self.calls = []
        self.hotspot = None
        self.clients = 0

    def saved_wifi(self):
        self.calls.append('saved')
        if self.saved_error:
            raise self.saved_error
        return list(self.saved)

    def has_wired(self):
        return self.wired

    def scan(self):
        self.calls.append('scan')
        if self.on_scan:
            self.on_scan()
        if self.scans is not None:
            return list(self.scans.pop(0)) if self.scans else []
        return list(self._scan)

    def start_hotspot(self, ssid):
        self.calls.append('start')
        self.hotspot = ssid

    def stop_hotspot(self):
        self.calls.append('stop')
        self.hotspot = None

    def join(self, ssid, password, hidden, timeout=45):
        self.calls.append(('join', ssid, password, hidden))
        if self.join_error:
            raise self.join_error
        if self.join_ok:
            self.saved.append(ssid)
            self._ip = '192.168.1.23'
            return True
        return False

    def client_count(self):
        return self.clients

    def ip(self):
        return self._ip


class FakeSystem:
    def __init__(self):
        self.calls = []
        self.emulator = False
        self.password_ok = True

    def set_password(self, user, password):
        self.calls.append(('password', user, password))
        return self.password_ok

    def set_timezone(self, tz):
        self.calls.append(('tz', tz))

    def set_country(self, cc):
        self.calls.append(('country', cc))

    def restart_tty1(self):
        self.calls.append('restart_tty1')

    def emulator_running(self):
        return self.emulator

    def beep(self):
        self.calls.append('beep')


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def req(ssid='Home', wifi_password='hunter22', hidden=False, mac_password=None, timezone=None):
    return ms.ConnectRequest(ssid, wifi_password, hidden, mac_password, timezone)


class Base(unittest.TestCase):

    def make(self, saved=(), ip=None, rom=True, needs_password=False, join_ok=True):
        tmp = Path(tempfile.mkdtemp())
        self.run_dir = tmp / 'run'
        self.state_dir = tmp / 'state'
        self.home = tmp / 'home'
        for d in (self.run_dir, self.state_dir, self.home):
            d.mkdir()
        self.rom_path = self.home / 'ROM'
        prefs = self.home / '.basilisk_ii_prefs'
        prefs.write_text(f'disk {self.home}/disk.hda\nrom {self.rom_path}\n')
        if rom:
            self.rom_path.write_bytes(make_rom(512 * 1024))
        if needs_password:
            (self.state_dir / 'needs-password').touch()
        config = ms.Config(user='mac', home=str(self.home), emulator='basilisk', prefs=str(prefs))
        self.nm = FakeNM(saved=saved, ip=ip, join_ok=join_ok)
        self.sys = FakeSystem()
        self.clock = Clock()
        self.c = ms.Controller(config, self.nm, self.sys, clock=self.clock,
                               run_dir=self.run_dir, state_dir=self.state_dir,
                               hostname='macintosh-mini-4e2a', suffix='4e2a',
                               spawn=lambda fn: fn(), sleep=lambda s: None,
                               zone_tab=ZONE_TAB, chown=lambda path: None)
        return self.c

    def status(self):
        return json.loads((self.run_dir / 'status.json').read_text())


class Decisions(Base):

    def test_no_saved_networks_starts_first_run_hotspot(self):
        c = self.make(saved=())
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertEqual(c.state()['reason'], 'first-run')
        self.assertEqual(self.nm.hotspot, 'Macintosh Mini 4E2A')
        self.assertLess(self.nm.calls.index('scan'), self.nm.calls.index('start'))
        self.assertEqual(c.state()['networks'], ['Home', 'Cafe'])

    def test_saved_network_offline_never_starts_hotspot(self):
        c = self.make(saved=['Home'], ip=None, rom=True)
        for t in range(0, 3600, 2):
            self.clock.now = t
            c.tick()
        self.assertEqual(c.state()['phase'], 'off')
        self.assertNotIn('start', self.nm.calls)

    def test_off_phase_only_checks_flags(self):
        c = self.make(saved=['Home'], rom=True)
        c.tick()
        calls = len(self.nm.calls)
        for t in range(2, 100, 2):
            self.clock.now = t
            c.tick()
        self.assertEqual(len(self.nm.calls), calls)

    def test_no_rom_offline_waits(self):
        c = self.make(saved=['Home'], ip=None, rom=False)
        c.tick()
        self.assertEqual(c.state()['phase'], 'waiting')

    def test_no_rom_connected_goes_to_rom_phase(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        s = c.state()
        self.assertEqual(s['phase'], 'rom')
        self.assertEqual(s['url'], 'http://macintosh-mini-4e2a.local/')
        self.assertEqual(s['ip'], '192.168.1.23')

    def test_button_request_starts_hotspot_and_cancel_restores(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=True)
        c.tick()
        (self.run_dir / 'requested').touch()
        self.clock.now = 5
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertEqual(c.state()['reason'], 'button')
        (self.run_dir / 'cancel').touch()
        self.clock.now = 10
        c.tick()
        self.assertEqual(c.state()['phase'], 'off')
        self.assertIsNone(self.nm.hotspot)
        self.assertFalse((self.run_dir / 'requested').exists())
        self.assertFalse((self.run_dir / 'cancel').exists())

    def test_button_hotspot_gives_up_after_300s_idle(self):
        c = self.make(saved=['Home'], rom=True)
        (self.run_dir / 'requested').touch()
        c.tick()
        self.nm.clients = 1
        self.clock.now = 100
        c.tick()
        self.nm.clients = 0
        self.clock.now = 350
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.clock.now = 401
        c.tick()
        self.assertEqual(c.state()['phase'], 'off')
        self.assertIsNone(self.nm.hotspot)

    def test_first_run_ignores_cancel_and_never_gives_up(self):
        c = self.make(saved=())
        c.tick()
        (self.run_dir / 'cancel').touch()
        self.clock.now = 5000
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertEqual(self.nm.hotspot, 'Macintosh Mini 4E2A')


class Wifi(Base):

    def test_submit_wifi_sets_password_tz_country_and_clears_marker(self):
        c = self.make(saved=(), rom=True, needs_password=True)
        c.tick()
        self.assertTrue(c.state()['needs_password'])
        c.submit_wifi(req(mac_password='applepie', timezone='Europe/Berlin'))
        self.assertIn(('password', 'mac', 'applepie'), self.sys.calls)
        self.assertIn(('tz', 'Europe/Berlin'), self.sys.calls)
        self.assertIn(('country', 'DE'), self.sys.calls)
        self.assertFalse((self.state_dir / 'needs-password').exists())
        self.assertFalse(c.state()['needs_password'])

    def test_failed_join_forgets_network_and_reopens_hotspot(self):
        c = self.make(saved=(), rom=True, join_ok=False)
        c.tick()
        c.submit_wifi(req())
        s = c.state()
        self.assertEqual(s['phase'], 'hotspot')
        self.assertEqual(s['error'], "Couldn't join Home. Check the password and try again.")
        self.assertEqual(self.nm.hotspot, 'Macintosh Mini 4E2A')
        self.assertEqual(self.nm.saved, [])

    def test_successful_join_with_rom_returns_to_mac_os(self):
        c = self.make(saved=['Old'], rom=True)
        (self.run_dir / 'requested').touch()
        c.tick()
        c.submit_wifi(req(ssid='New', wifi_password='', hidden=True))
        self.assertIn(('join', 'New', '', True), self.nm.calls)
        self.assertEqual(c.state()['phase'], 'off')
        self.assertFalse((self.run_dir / 'requested').exists())
        self.assertIsNone(self.nm.hotspot)

    def test_successful_join_without_rom_goes_to_rom_page(self):
        c = self.make(saved=(), rom=False)
        c.tick()
        c.submit_wifi(req())
        self.assertEqual(c.state()['phase'], 'rom')
        self.assertEqual(c.state()['ip'], '192.168.1.23')

    def test_status_file_written(self):
        c = self.make(saved=())
        c.tick()
        s = self.status()
        self.assertEqual(s['phase'], 'hotspot')
        self.assertEqual(s['screen']['qr'], 'WIFI:T:nopass;S:Macintosh Mini 4E2A;;')


class Rom(Base):

    def test_submit_rom_writes_file_and_starts_trial(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        data = make_rom(1024 * 1024)
        self.assertIsNone(c.submit_rom(data))
        self.assertEqual(self.rom_path.read_bytes(), data)
        self.assertTrue((self.run_dir / 'rom-trial').exists())
        self.assertEqual(c.state()['phase'], 'starting')

    def test_submit_bad_rom_returns_message(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        self.assertEqual(c.submit_rom(b'nope'), "That file isn't a Mac ROM.")
        self.assertFalse(self.rom_path.exists())
        self.assertEqual(c.state()['phase'], 'rom')

    def test_rom_trial_failure_returns_to_rom_page(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        c.submit_rom(make_rom(1024 * 1024))
        self.clock.now = 20
        self.rom_path.rename(self.home / '.ROM.rejected')   # what the launcher does
        c.tick()
        self.assertEqual(c.state()['phase'], 'rom')
        self.assertEqual(c.state()['error'], "That ROM didn't start the Mac. Try another.")
        self.assertFalse((self.run_dir / 'rom-trial').exists())

    def test_rom_trial_success_after_60s(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        c.submit_rom(make_rom(1024 * 1024))
        self.sys.emulator = True
        self.clock.now = 30
        c.tick()
        self.assertEqual(c.state()['phase'], 'starting')
        self.clock.now = 61
        c.tick()
        self.assertEqual(c.state()['phase'], 'off')
        self.assertFalse((self.run_dir / 'rom-trial').exists())


class Screens(Base):

    def test_screen_for_each_phase(self):
        c = self.make(saved=())
        c.tick()
        s = c.state()
        hot = c.screen_for(s)
        self.assertEqual(hot['title'], 'Set up Wi-Fi')
        self.assertIn('Macintosh Mini 4E2A', hot['lines'])
        self.assertEqual(hot['qr'], 'WIFI:T:nopass;S:Macintosh Mini 4E2A;;')
        for phase, title in (('waiting', 'Looking for Wi-Fi'), ('connecting', 'Connecting'),
                             ('rom', 'Almost done'), ('starting', 'Starting up')):
            screen = c.screen_for(dict(s, phase=phase, network='Home',
                                       url='http://macintosh-mini-4e2a.local/', ip='192.168.1.23'))
            self.assertTrue(screen['title'].startswith(title), screen['title'])
            if phase != 'rom':
                self.assertIsNone(screen['qr'])

    def test_rom_screen_shows_name_and_ip(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        lines = c.screen_for(c.state())['lines']
        self.assertIn('macintosh-mini-4e2a.local', lines)
        self.assertIn('or http://192.168.1.23', lines)

    def test_rom_screen_has_qr_to_the_page(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        screen = c.screen_for(c.state())
        self.assertEqual(screen['qr'], 'http://192.168.1.23/')
        self.assertIn('or scan the code.', screen['lines'])

    def test_button_hotspot_says_how_to_cancel(self):
        c = self.make(saved=['Home'], rom=True)
        (self.run_dir / 'requested').touch()
        c.tick()
        self.assertIn('Press the left button to cancel.', ' '.join(c.screen_for(c.state())['lines']))


class Review(Base):
    """Cases from the final review."""

    def test_rom_gone_while_off_resettles(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=True)
        c.tick()
        self.assertEqual(c.state()['phase'], 'off')
        self.rom_path.unlink()
        self.clock.now = 2
        c.tick()
        self.assertEqual(c.state()['phase'], 'rom')

    def test_stale_rom_trial_cleared_on_start(self):
        c = self.make(saved=['Home'], rom=True)
        (self.run_dir / 'rom-trial').touch()
        c.tick()
        self.assertFalse((self.run_dir / 'rom-trial').exists())

    def test_hold_during_trial_clears_trial(self):
        c = self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        c.tick()
        c.submit_rom(make_rom(1024 * 1024))
        (self.run_dir / 'requested').touch()
        self.clock.now = 10
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertFalse((self.run_dir / 'rom-trial').exists())

    def test_join_raising_reopens_hotspot_without_logging_password(self):
        import io
        import subprocess
        from contextlib import redirect_stderr
        c = self.make(saved=(), rom=True)
        c.tick()
        self.nm.join_error = subprocess.TimeoutExpired(
            ['nmcli', 'device', 'wifi', 'connect', 'Home', 'password', 'sekrit-pw'], 60)
        err = io.StringIO()
        with redirect_stderr(err):
            c.submit_wifi(req(wifi_password='sekrit-pw'))
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertEqual(c.state()['error'], "Couldn't join Home. Check the password and try again.")
        self.assertNotIn('sekrit-pw', err.getvalue())

    def test_scan_failure_still_opens_hotspot(self):
        c = self.make(saved=())
        def boom():
            raise OSError('nmcli timed out')
        self.nm.on_scan = boom
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertEqual(c.state()['networks'], [])

    def test_nmcli_failure_never_starts_hotspot(self):
        c = self.make(saved=['Home'], rom=True)
        self.nm.saved_error = RuntimeError('NetworkManager is not running')
        for t in range(0, 60, 5):
            self.clock.now = t
            c.tick()
        self.assertNotIn('start', self.nm.calls)
        self.assertNotEqual(c.state()['phase'], 'hotspot')

    def test_country_and_tz_set_after_hotspot_stops(self):
        c = self.make(saved=(), rom=True)
        self.sys.calls = self.nm.calls     # one shared log, to see the order
        c.tick()
        c.submit_wifi(req(timezone='Europe/Berlin'))
        calls = self.nm.calls
        self.assertLess(calls.index('stop'), calls.index(('country', 'DE')))
        self.assertLess(calls.index('stop'), calls.index(('tz', 'Europe/Berlin')))

    def test_preparing_written_after_hold(self):
        c = self.make(saved=['Home'], rom=True)
        c.tick()
        seen = []
        self.nm.on_scan = lambda: seen.append(self.status()['phase'])
        (self.run_dir / 'requested').touch()
        self.clock.now = 5
        c.tick()
        self.assertEqual(seen, ['preparing'])

    def test_empty_scan_retried(self):
        c = self.make(saved=())
        self.nm.scans = [[], [], ['Home']]
        c.tick()
        self.assertEqual(c.state()['networks'], ['Home'])

    def test_password_failure_keeps_marker_and_does_not_join(self):
        c = self.make(saved=(), rom=True, needs_password=True)
        c.tick()
        self.sys.password_ok = False
        c.submit_wifi(req(mac_password='applepie'))
        self.assertTrue((self.state_dir / 'needs-password').exists())
        self.assertEqual(c.state()['phase'], 'hotspot')
        self.assertEqual(c.state()['error'], "Couldn't set the Mac's password. Try again.")
        self.assertFalse(any(isinstance(x, tuple) and x[0] == 'join' for x in self.nm.calls))

    def test_wired_connection_without_wifi_no_hotspot(self):
        c = self.make(saved=(), ip='192.168.1.5', rom=True)
        c.tick()
        self.assertEqual(c.state()['phase'], 'off')
        self.assertNotIn('start', self.nm.calls)

    def test_wired_device_gets_grace_before_first_run(self):
        c = self.make(saved=(), ip=None, rom=True)
        self.nm.wired = True
        c.tick()
        self.assertNotIn('start', self.nm.calls)
        self.clock.now = 10
        c.tick()
        self.assertNotIn('start', self.nm.calls)
        self.clock.now = 31
        c.tick()
        self.assertEqual(c.state()['phase'], 'hotspot')


class FakeServer:
    def __init__(self, controller, port):
        import threading
        self.port = port
        self.stopped = threading.Event()
        self.closed = False

    def serve_forever(self, poll_interval=0.5):
        self.stopped.wait()

    def shutdown(self):
        self.stopped.set()

    def server_close(self):
        self.closed = True


class WebServerLifetime(Base):
    """Nothing listens on the network unless setup is under way."""

    def make_web(self):
        self.made = []

        def factory(controller, port):
            server = FakeServer(controller, port)
            self.made.append(server)
            return server
        return ms.WebServer(self.c, factory)

    def running(self, web):
        return web.server is not None

    def test_no_server_when_nothing_to_set_up(self):
        self.make(saved=['Home'], rom=True)
        web = self.make_web()
        self.c.tick()
        web.sync()
        self.assertFalse(self.running(web))
        self.assertEqual(self.made, [])

    def test_server_up_for_button_setup_and_down_after_cancel(self):
        self.make(saved=['Home'], rom=True)
        web = self.make_web()
        self.c.tick()
        (self.run_dir / 'requested').touch()
        self.c.tick()
        web.sync()
        self.assertTrue(self.running(web))
        self.assertEqual(self.made[0].port, 80)
        (self.run_dir / 'cancel').touch()
        self.c.tick()
        web.sync()
        self.assertFalse(self.running(web))
        self.assertTrue(self.made[0].stopped.is_set())
        self.assertTrue(self.made[0].closed)

    def test_server_kept_through_rom_trial_then_stopped(self):
        self.make(saved=['Home'], ip='192.168.1.23', rom=False)
        web = self.make_web()
        self.c.tick()
        web.sync()
        self.assertTrue(self.running(web))
        self.c.submit_rom(make_rom(1024 * 1024))
        web.sync()
        self.assertTrue(self.running(web))      # still answering "All set"
        self.sys.emulator = True
        self.clock.now = 61
        self.c.tick()
        web.sync()
        self.assertFalse(self.running(web))
        self.assertEqual(len(self.made), 1)

    def test_bind_failure_retried(self):
        self.make(saved=())
        calls = []

        def factory(controller, port):
            calls.append(port)
            if len(calls) == 1:
                raise OSError('Address already in use')
            return FakeServer(controller, port)
        web = ms.WebServer(self.c, factory)
        self.c.tick()
        web.sync()
        self.assertIsNone(web.server)
        web.sync()
        self.assertIsNotNone(web.server)


class NMJoin(unittest.TestCase):
    """NM.join against a fake nmcli: the commands it runs, in order."""

    def run_join(self, connect_ok):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            ok = not (cmd[:2] == ['nmcli', '--wait'] and not connect_ok)
            return ms.subprocess.CompletedProcess(cmd, 0 if ok else 4, stdout='', stderr='')
        old_run, old_sleep = ms._run, ms.time.sleep
        ms._run, ms.time.sleep = fake_run, (lambda s: None)
        try:
            result = ms.NM().join('Home', 'hunter222', False)
        finally:
            ms._run, ms.time.sleep = old_run, old_sleep
        return result, calls

    def test_failed_join_keeps_existing_profile(self):
        ok, calls = self.run_join(connect_ok=False)
        self.assertFalse(ok)
        self.assertNotIn(['nmcli', 'connection', 'delete', 'id', 'Home'], calls)
        self.assertIn(['nmcli', 'connection', 'delete', 'id', ms.NEW_CON], calls)

    def test_successful_join_replaces_old_profile(self):
        ok, calls = self.run_join(connect_ok=True)
        self.assertTrue(ok)
        delete_old = calls.index(['nmcli', 'connection', 'delete', 'id', 'Home'])
        connect = next(i for i, c in enumerate(calls) if c[:2] == ['nmcli', '--wait'])
        self.assertLess(connect, delete_old)
        self.assertIn(['nmcli', 'connection', 'modify', ms.NEW_CON, 'connection.id', 'Home'], calls)


class Helpers(unittest.TestCase):

    def test_country_for_timezone(self):
        self.assertEqual(ms.country_for_timezone('America/New_York', ZONE_TAB), 'US')
        self.assertEqual(ms.country_for_timezone('Europe/Berlin', ZONE_TAB), 'DE')
        self.assertIsNone(ms.country_for_timezone('Mars/Olympus', ZONE_TAB))
        self.assertIsNone(ms.country_for_timezone('', ZONE_TAB))

    def test_serial_suffix(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'00000000c3b74e2a\x00')
        try:
            self.assertEqual(ms.serial_suffix(f.name), '4e2a')
        finally:
            os.unlink(f.name)

    def test_hotspot_ssid(self):
        self.assertEqual(ms.hotspot_ssid('4e2a'), 'Macintosh Mini 4E2A')

    def test_parse_scan(self):
        out = 'Home:40\nCafe\\:Guest:80\n:90\nHome:70\n'
        self.assertEqual(ms.parse_scan(out), ['Cafe:Guest', 'Home'])

    def test_parse_saved(self):
        out = ('Home:802-11-wireless\nWired connection 1:802-3-ethernet\n'
               'mac-setup-hotspot:802-11-wireless\nA\\:B:802-11-wireless\n')
        self.assertEqual(ms.parse_saved(out), ['Home', 'A:B'])

    def test_wifi_qr_escapes(self):
        self.assertEqual(ms.wifi_qr('a;b'), 'WIFI:T:nopass;S:a\\;b;;')

    def test_load_config(self):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write('USER=mac\nHOME=/home/mac\nEMULATOR=basilisk\nPREFS=/home/mac/.basilisk_ii_prefs\n')
        try:
            c = ms.load_config(f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(c, ms.Config('mac', '/home/mac', 'basilisk', '/home/mac/.basilisk_ii_prefs'))


if __name__ == '__main__':
    unittest.main()
