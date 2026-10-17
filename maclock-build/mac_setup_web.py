#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# mac_setup_web.py
#
# The two setup pages, served by mac_setup.py on port 80.
#   - On the Mac's own hotspot: the page phones pop up by themselves, asking
#     for the Wi-Fi network, its password and (first time) a Mac password.
#     Every other address a phone asks for is sent here.
#   - On the owner's Wi-Fi, while there's no ROM: the ROM page.
# Everything is inline: phones on the hotspot have no internet.
# ####################################

import html
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mac_setup import ConnectRequest

HOTSPOT_IP = '10.42.0.1'
PORTAL_URL = f'http://{HOTSPOT_IP}/'
MAX_ROM_BYTES = 16 * 1024 * 1024
GUIDE_URL = 'https://www.redundantrobot.com/sheepshaver'
GUIDE = ('Need a ROM? <a href="https://www.redundantrobot.com/sheepshaver">Redundant Robot\'s '
         'emulator guide</a> explains which one to use and where to find it. The Performa ROM works best.')


class FormError(Exception):
    """A form was refused; str(e) is the message for the owner."""


def parse_connect_form(body, needs_password):
    f = urllib.parse.parse_qs(body.decode('utf-8', 'replace'), keep_blank_values=True)

    def get(name):
        return f.get(name, [''])[0]

    other = get('other').strip()
    ssid = other or get('network')
    hidden = bool(other)
    if not ssid:
        raise FormError('Pick your Wi-Fi network, or type its name.')
    if len(ssid.encode()) > 32:
        raise FormError('That network name is too long.')
    password = get('password')
    hex_psk = len(password) == 64 and re.fullmatch(r'[0-9a-fA-F]+', password)
    if password and not hex_psk and not 8 <= len(password) <= 63:
        raise FormError('Wi-Fi passwords are 8 to 63 characters. '
                        'Leave it blank if your network has none.')
    mac_password = None
    if needs_password:
        mac_password = get('mac_password')
        if not mac_password:
            raise FormError('Choose a password for your Mac.')
        if len(mac_password) < 4:
            raise FormError("Make the Mac's password at least 4 characters.")
        if mac_password != get('mac_password2'):
            raise FormError("The two Mac passwords don't match.")
    if any(c in s for s in (password, mac_password or '') for c in '\r\n\0'):
        raise FormError("Passwords can't contain line breaks.")
    tz = get('tz')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+)*', tz) or len(tz) > 64:
        tz = None
    return ConnectRequest(ssid, password, hidden, mac_password, tz)


def fetch_url(url, limit=MAX_ROM_BYTES):
    if urllib.parse.urlsplit(url).scheme not in ('http', 'https'):
        raise FormError("That link doesn't look right. It should start with http:// or https://.")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'macintosh-mini-setup'})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(limit + 1)
    except (urllib.error.URLError, OSError, ValueError):
        raise FormError("Couldn't download that link. Check it and try again.")
    if len(data) > limit:
        raise FormError('That file is too big to be a ROM.')
    return data


# --- pages -----------------------------------------------------------------
STYLE = """
*{box-sizing:border-box}
html{background:#a8a8a8;background-image:radial-gradient(#8c8c8c 1px,transparent 1px);background-size:4px 4px}
body{margin:0;padding:16px;font:17px/1.4 "Chicago","ChicagoFLF",-apple-system,system-ui,sans-serif;color:#000}
.win{max-width:460px;margin:0 auto;background:#fff;border:2px solid #000;box-shadow:3px 3px 0 #000}
.bar{position:relative;height:26px;border-bottom:2px solid #000;
 background:repeating-linear-gradient(#000 0 1px,#fff 1px 3px);background-clip:content-box;padding:4px 4px}
.bar h1{position:absolute;left:50%;top:1px;transform:translateX(-50%);margin:0;padding:0 10px;
 background:#fff;font-size:16px;line-height:22px;white-space:nowrap}
.body{padding:18px}
p{margin:0 0 14px}
label{display:block;margin:14px 0 6px;font-weight:600}
input,select{width:100%;font:inherit;padding:10px;border:2px solid #000;border-radius:0;background:#fff;min-height:46px}
button{display:block;width:100%;margin-top:22px;font:inherit;font-weight:600;min-height:50px;background:#fff;
 border:2px solid #000;border-radius:12px;box-shadow:0 0 0 3px #fff,0 0 0 5px #000}
button:active{background:#000;color:#fff}
.err{border:2px solid #000;padding:10px;margin-bottom:14px;background:#fff6c8}
.small{font-size:14px;color:#333}
a{color:#000}
.or{text-align:center;margin:18px 0 0}
"""


def page(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>'
            f'<div class="win"><div class="bar"><h1>{html.escape(title)}</h1></div>'
            f'<div class="body">{body}</div></div></body></html>')


def _error(msg):
    return f'<div class="err">{html.escape(msg)}</div>' if msg else ''


def portal_page(state, error=None):
    options = ''.join(f'<option>{html.escape(n)}</option>' for n in state['networks'])
    mac = ''
    if state['needs_password']:
        mac = ('<label for="mp">A new password for this Mac</label>'
               '<input id="mp" name="mac_password" type="password" autocomplete="new-password" required>'
               '<label for="mp2">Type it again</label>'
               '<input id="mp2" name="mac_password2" type="password" autocomplete="new-password" required>'
               '<p class="small">You\'ll only need it for advanced things, like copying a new disk '
               'image onto the Mac.</p>')
    body = (_error(error or state.get('error'))
            + '<form method="post" action="/connect">'
            '<label for="n">Your Wi-Fi network</label>'
            f'<select id="n" name="network">{options}<option value="">Other…</option></select>'
            '<label for="o">Not listed? Type its name</label>'
            '<input id="o" name="other" autocapitalize="off" autocorrect="off" spellcheck="false">'
            '<label for="p">Wi-Fi password</label>'
            '<input id="p" name="password" type="password" autocomplete="off">'
            + mac
            + '<input type="hidden" name="tz" id="tz">'
            '<button type="submit">Connect</button></form>'
            '<script>try{document.getElementById("tz").value='
            'Intl.DateTimeFormat().resolvedOptions().timeZone||""}catch(e){}</script>')
    return page('Set up Wi-Fi', body)


def connecting_page(network):
    return page('Connecting…', f'<p>Connecting to <b>{html.escape(network)}</b>… look at your '
                'Mac\'s screen to see how it went.</p><p>You can close this page.</p>')


def rom_page(state, error=None):
    body = (_error(error or state.get('error'))
            + f'<p>{GUIDE}</p>'
            '<label for="f">Upload the ROM (or the .zip you downloaded)</label>'
            '<input id="f" type="file">'
            '<button id="up" type="button">Use this file</button>'
            '<p class="or">or</p>'
            '<form method="post" action="/rom-url">'
            '<label for="u">Paste its download link</label>'
            '<input id="u" name="url" type="url" inputmode="url" autocapitalize="off" '
            'autocorrect="off" spellcheck="false" placeholder="https://…">'
            '<button type="submit">Download it</button></form>'
            '<script>document.getElementById("up").onclick=async function(){'
            'var f=document.getElementById("f").files[0];if(!f)return;'
            'this.disabled=true;this.textContent="Checking…";'
            'var r=await fetch("/rom",{method:"POST",body:f});'
            'document.open();document.write(await r.text());document.close();}</script>')
    return page('Add a ROM', body)


def rom_done_page():
    return page('All set', '<p>Got it. Your Mac is starting up: listen for the chime.</p>'
                '<p>If the Mac comes back to this step instead, that ROM didn\'t work. '
                'Reload this page and try another.</p>')


# --- server ----------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'macintosh-mini'
    sys_version = ''

    def log_message(self, fmt, *args):
        pass   # nothing secret, but nothing worth keeping either

    def _send(self, status, body='', headers=None):
        data = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def _redirect(self):
        self._send(302, '', {'Location': PORTAL_URL})

    def _body(self, limit):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length > limit:
            self.close_connection = True
            return None
        return self.rfile.read(length)

    def _host(self):
        return (self.headers.get('Host') or '').split(':')[0]

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        ctl = self.server.controller
        s = ctl.state()
        path = urllib.parse.urlsplit(self.path).path
        if s['phase'] == 'hotspot':
            if self._host() != HOTSPOT_IP or path != '/':
                return self._redirect()
            return self._send(200, portal_page(s))
        if s['phase'] == 'connecting' and path == '/':
            return self._send(200, connecting_page(s['network'] or ''))
        if s['phase'] == 'rom' and path == '/':
            return self._send(200, rom_page(s))
        if s['phase'] == 'starting' and path == '/':
            return self._send(200, rom_done_page())
        return self._send(404, page('Not here', '<p>Nothing to set up right now.</p>'))

    def do_POST(self):
        ctl = self.server.controller
        s = ctl.state()
        path = urllib.parse.urlsplit(self.path).path
        if s['phase'] == 'hotspot' and path == '/connect':
            body = self._body(64 * 1024)
            if body is None:
                return self._send(413, portal_page(s, 'That was too much to send.'))
            try:
                req = parse_connect_form(body, s['needs_password'])
            except FormError as e:
                return self._send(200, portal_page(s, str(e)))
            ctl.submit_wifi(req)
            return self._send(200, connecting_page(req.ssid))
        if s['phase'] == 'rom' and path == '/rom':
            data = self._body(MAX_ROM_BYTES)
            if data is None:
                return self._send(413, rom_page(s, 'That file is too big to be a ROM.'))
            return self._rom_result(ctl, s, data)
        if s['phase'] == 'rom' and path == '/rom-url':
            body = self._body(8 * 1024)
            url = urllib.parse.parse_qs((body or b'').decode('utf-8', 'replace')).get('url', [''])[0].strip()
            try:
                data = fetch_url(url)
            except FormError as e:
                return self._send(200, rom_page(s, str(e)))
            return self._rom_result(ctl, s, data)
        return self._send(404, page('Not here', '<p>Nothing to set up right now.</p>'))

    def _rom_result(self, ctl, s, data):
        error = ctl.submit_rom(data)
        if error:
            return self._send(200, rom_page(s, error))
        return self._send(200, rom_done_page())


def make_server(controller, port=80, host=''):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.controller = controller
    return server
