#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the setup pages in mac_setup_web.py, against a real local server.

Run: python3 -m unittest test_mac_setup_web
"""

import http.client
import http.server
import threading
import unittest
import urllib.parse

import mac_setup_web as web
from test_mac_setup_rom import make_rom

GUIDE = ('Need a ROM? <a href="https://www.redundantrobot.com/sheepshaver">Redundant Robot\'s '
         'emulator guide</a> explains which one to use and where to find it. The Performa ROM works best.')


class FakeController:
    def __init__(self, phase='hotspot', needs_password=True, error=None):
        self.s = {'phase': phase, 'reason': 'first-run', 'ssid': 'Macintosh Mini 4E2A',
                  'networks': ['Home', 'Cafe <3'], 'needs_password': needs_password,
                  'error': error, 'network': 'Home', 'hostname': 'macintosh-mini-4e2a',
                  'url': 'http://macintosh-mini-4e2a.local/', 'ip': '192.168.1.23'}
        self.wifi = []
        self.roms = []
        self.rom_error = None

    def state(self):
        return dict(self.s)

    def submit_wifi(self, req):
        self.wifi.append(req)

    def submit_rom(self, data):
        self.roms.append(data)
        return self.rom_error


class Server(unittest.TestCase):

    def start(self, **kw):
        self.ctl = FakeController(**kw)
        self.server = web.make_server(self.ctl, port=0, host='127.0.0.1')
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, args=(0.05,), daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, host='10.42.0.1', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        h = {'Host': host}
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        data = r.read().decode('utf-8', 'replace')
        conn.close()
        return r, data

    def post_form(self, path, fields, **kw):
        body = urllib.parse.urlencode(fields)
        return self.request('POST', path, body, headers={
            'Content-Type': 'application/x-www-form-urlencoded'}, **kw)


class Portal(Server):

    def test_portal_lists_networks(self):
        self.start()
        r, page = self.request('GET', '/')
        self.assertEqual(r.status, 200)
        self.assertIn('Home', page)
        self.assertIn('Cafe &lt;3', page)   # escaped
        self.assertIn('name="mac_password"', page)

    def test_portal_hides_password_fields_when_not_needed(self):
        self.start(needs_password=False)
        _, page = self.request('GET', '/')
        self.assertNotIn('name="mac_password"', page)

    def test_portal_shows_last_error(self):
        self.start(error="Couldn't join Home. Check the password and try again.")
        _, page = self.request('GET', '/')
        self.assertIn('Couldn&#x27;t join Home.', page)

    def test_captive_probe_redirects(self):
        self.start()
        r, _ = self.request('GET', '/hotspot-detect.html', host='captive.apple.com')
        self.assertEqual(r.status, 302)
        self.assertEqual(r.getheader('Location'), 'http://10.42.0.1/')
        r, _ = self.request('GET', '/generate_204', host='connectivitycheck.gstatic.com')
        self.assertEqual(r.status, 302)

    def test_connect_bad_wifi_password_length(self):
        self.start()
        r, page = self.post_form('/connect', {'network': 'Home', 'password': 'short',
                                              'mac_password': 'applepie', 'mac_password2': 'applepie'})
        self.assertEqual(r.status, 200)
        self.assertIn('8 to 63 characters', page)
        self.assertEqual(self.ctl.wifi, [])

    def test_connect_passwords_must_match(self):
        self.start()
        _, page = self.post_form('/connect', {'network': 'Home', 'password': 'hunter222',
                                              'mac_password': 'applepie', 'mac_password2': 'applepiE'})
        self.assertIn('don&#x27;t match', page)
        self.assertEqual(self.ctl.wifi, [])

    def test_connect_ok_calls_controller_and_shows_connecting(self):
        self.start()
        _, page = self.post_form('/connect', {'network': 'Home', 'password': 'hunter222',
                                              'mac_password': 'applepie', 'mac_password2': 'applepie',
                                              'tz': 'Europe/Berlin'})
        self.assertIn("look at your Mac", page)
        req = self.ctl.wifi[0]
        self.assertEqual((req.ssid, req.wifi_password, req.hidden, req.mac_password, req.timezone),
                         ('Home', 'hunter222', False, 'applepie', 'Europe/Berlin'))

    def test_connect_typed_network_is_hidden(self):
        self.start(needs_password=False)
        self.post_form('/connect', {'network': '', 'other': 'Attic', 'password': ''})
        self.assertEqual((self.ctl.wifi[0].ssid, self.ctl.wifi[0].hidden), ('Attic', True))


class ParseForm(unittest.TestCase):

    def parse(self, fields, needs_password=False):
        return web.parse_connect_form(urllib.parse.urlencode(fields).encode(), needs_password)

    def test_no_network(self):
        with self.assertRaises(web.FormError):
            self.parse({'network': '', 'other': ''})

    def test_long_ssid(self):
        with self.assertRaises(web.FormError):
            self.parse({'network': 'x' * 33})

    def test_hex_psk_allowed(self):
        self.assertEqual(self.parse({'network': 'Home', 'password': 'a' * 64}).wifi_password, 'a' * 64)

    def test_mac_password_required(self):
        with self.assertRaises(web.FormError):
            self.parse({'network': 'Home'}, needs_password=True)

    def test_mac_password_newline_rejected(self):
        with self.assertRaises(web.FormError):
            self.parse({'network': 'Home', 'mac_password': 'ab\ncd', 'mac_password2': 'ab\ncd'},
                       needs_password=True)

    def test_bad_timezone_dropped(self):
        self.assertIsNone(self.parse({'network': 'Home', 'tz': '../../etc'}).timezone)


class RomPage(Server):

    def test_rom_page_has_guide_link_copy(self):
        self.start(phase='rom')
        r, page = self.request('GET', '/', host='macintosh-mini-4e2a.local')
        self.assertEqual(r.status, 200)
        self.assertIn(GUIDE, page)

    def test_rom_upload_ok(self):
        self.start(phase='rom')
        data = make_rom(512 * 1024)
        _, page = self.request('POST', '/rom', body=data, host='192.168.1.23')
        self.assertEqual(self.ctl.roms, [data])
        self.assertIn('chime', page)

    def test_rom_upload_error_shown(self):
        self.start(phase='rom')
        self.ctl.rom_error = "That file isn't a Mac ROM."
        _, page = self.request('POST', '/rom', body=b'nope', host='192.168.1.23')
        self.assertIn('That file isn&#x27;t a Mac ROM.', page)

    def test_rom_url_rejects_non_http(self):
        self.start(phase='rom')
        _, page = self.post_form('/rom-url', {'url': 'file:///etc/passwd'}, host='192.168.1.23')
        self.assertIn('http://', page)
        self.assertEqual(self.ctl.roms, [])

    def test_rom_url_fetches(self):
        data = make_rom(512 * 1024)
        url = self.serve_bytes(data)
        self.start(phase='rom')
        self.post_form('/rom-url', {'url': url}, host='192.168.1.23')
        self.assertEqual(self.ctl.roms, [data])

    def test_rom_url_too_big(self):
        url = self.serve_bytes(bytes(17 * 1024 * 1024))
        self.start(phase='rom')
        _, page = self.post_form('/rom-url', {'url': url}, host='192.168.1.23')
        self.assertIn('That file is too big to be a ROM.', page)
        self.assertEqual(self.ctl.roms, [])

    def test_rom_upload_too_big(self):
        self.start(phase='rom')
        r, page = self.request('POST', '/rom', body=b'', host='192.168.1.23',
                               headers={'Content-Length': str(17 * 1024 * 1024)})
        self.assertIn('too big', page)
        self.assertEqual(self.ctl.roms, [])

    def serve_bytes(self, payload):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=srv.serve_forever, args=(0.05,), daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f'http://127.0.0.1:{srv.server_address[1]}/1mbMacrom.zip'


class Phases(Server):

    def test_off_phase_404(self):
        self.start(phase='off')
        r, _ = self.request('GET', '/')
        self.assertEqual(r.status, 404)

    def test_connect_not_allowed_on_rom_phase(self):
        self.start(phase='rom')
        r, _ = self.post_form('/connect', {'network': 'Home'}, host='192.168.1.23')
        self.assertEqual(r.status, 404)
        self.assertEqual(self.ctl.wifi, [])


if __name__ == '__main__':
    unittest.main()
