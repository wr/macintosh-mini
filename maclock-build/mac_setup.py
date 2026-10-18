#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# mac_setup.py
#
# Wi-Fi setup from a phone. When the Mac has no saved Wi-Fi, or someone holds
# the left button for 10 seconds, it offers an open "Macintosh Mini XXXX"
# hotspot. Joining it opens a setup page (mac_setup_web.py) for the Wi-Fi, a
# password and, once the Mac is on that network, a ROM. The Mac's own screen
# shows what to do next (mac_setup_screen.py), drawn from status.json.
#
#   mac-setup serve     the service (root, mac-setup.service)
#   mac-setup needed    exit 0 if the launcher should show the setup screen
#                       (answered by the /usr/local/bin/mac-setup wrapper in
#                       shell, so the launcher never waits for Python)
#   mac-setup request   start setup now (the left button's 10-second hold)
#   mac-setup cancel    stop a setup started by the button
#   mac-setup screen    draw the setup screen on tty1
# ####################################

import json
import os
import pwd
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from mac_setup_rom import RomError, extract_rom

RUN_DIR = Path('/run/mac-setup')
STATE_DIR = Path('/var/lib/mac-setup')
CONF = '/etc/mac-setup.conf'
SERIAL = '/sys/firmware/devicetree/base/serial-number'
ZONE_TAB = '/usr/share/zoneinfo/zone.tab'

HOTSPOT_CON = 'mac-setup-hotspot'
NEW_CON = 'mac-setup-new'      # a network being tried, until it connects
HOTSPOT_IP = '10.42.0.1'
GIVE_UP_S = 300        # a button-started hotspot with nobody on it gives up
TRIAL_S = 60           # a new ROM counts once the emulator has run this long
TRIAL_ABANDON_S = 180  # ...or is forgotten if the emulator never started
NM_POLL_S = 5          # how often to ask NetworkManager while waiting
JOIN_DELAY_S = 3       # let the phone get the "Connecting…" page first
WIRED_GRACE_S = 30     # with a USB Ethernet adapter, wait this long for a wired address
SCAN_TRIES = 3         # Wi-Fi may not be ready at boot: scan again if nothing turns up
# The phases with a page to serve. Outside them nothing listens on port 80.
SERVE_PHASES = ('hotspot', 'connecting', 'rom', 'starting')


@dataclass
class Config:
    user: str
    home: str
    emulator: str   # basilisk | sheepshaver
    prefs: str


@dataclass
class ConnectRequest:
    ssid: str
    wifi_password: str
    hidden: bool
    mac_password: str | None
    timezone: str | None


def load_config(path=CONF):
    values = {}
    for line in Path(path).read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            values[k.strip()] = v.strip()
    return Config(values['USER'], values['HOME'], values['EMULATOR'], values['PREFS'])


def serial_suffix(path=SERIAL):
    try:
        serial = Path(path).read_bytes().strip(b'\0\n ').decode().lower()
    except OSError:
        serial = ''
    if len(serial) < 4:
        serial = Path('/etc/machine-id').read_text().strip()
    return serial[-4:]


def hotspot_ssid(suffix):
    return f'Macintosh Mini {suffix.upper()}'


def wifi_qr(ssid):
    # The Wi-Fi QR format phones' cameras understand; \ ; , : " are escaped.
    return 'WIFI:T:nopass;S:' + re.sub(r'([\\;,:"])', r'\\\1', ssid) + ';;'


def country_for_timezone(tz, zone_tab):
    if not tz:
        return None
    for line in zone_tab.splitlines():
        if line.startswith('#'):
            continue
        fields = line.split('\t')
        if len(fields) >= 3 and fields[2] == tz:
            return fields[0]
    return None


def _split_terse(line):
    # nmcli -t separates fields with ':' and escapes ':' and '\' in values.
    fields, cur, i = [], '', 0
    while i < len(line):
        ch = line[i]
        if ch == '\\' and i + 1 < len(line):
            cur += line[i + 1]
            i += 2
            continue
        if ch == ':':
            fields.append(cur)
            cur = ''
        else:
            cur += ch
        i += 1
    fields.append(cur)
    return fields


def parse_scan(out):
    """nmcli -t -f SSID,SIGNAL output -> SSIDs, strongest first, no repeats."""
    best = {}
    for line in out.splitlines():
        fields = _split_terse(line)
        if len(fields) < 2 or not fields[0]:
            continue
        try:
            signal = int(fields[1])
        except ValueError:
            signal = 0
        best[fields[0]] = max(signal, best.get(fields[0], -1))
    return sorted(best, key=lambda s: -best[s])


def parse_saved(out):
    """nmcli -t -f NAME,TYPE connection show -> saved Wi-Fi names."""
    names = []
    for line in out.splitlines():
        fields = _split_terse(line)
        if len(fields) >= 2 and fields[1] == '802-11-wireless' and fields[0] != HOTSPOT_CON:
            names.append(fields[0])
    return names


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _describe(e):
    # Never log a command line: joining a network puts its password on one.
    if isinstance(e, subprocess.SubprocessError) and getattr(e, 'cmd', None):
        return f'{type(e).__name__} running {e.cmd[0]}'
    return type(e).__name__ if isinstance(e, subprocess.SubprocessError) else repr(e)


class NM:
    """NetworkManager, through nmcli. Never restarts NetworkManager."""

    def saved_wifi(self):
        r = _run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'])
        if r.returncode:
            # Not "no networks": NetworkManager may just be restarting.
            raise RuntimeError('nmcli could not list connections')
        return parse_saved(r.stdout)

    def has_wired(self):
        out = _run(['nmcli', '-t', '-f', 'TYPE,STATE', 'device']).stdout
        return any(f[0] == 'ethernet' and f[1] not in ('unavailable', 'unmanaged')
                   for f in (_split_terse(line) for line in out.splitlines()) if len(f) >= 2)

    def scan(self):
        try:
            out = _run(['nmcli', '-t', '-f', 'SSID,SIGNAL', 'device', 'wifi', 'list',
                        '--rescan', 'yes'], timeout=30).stdout
        except (subprocess.SubprocessError, OSError):
            return []
        return parse_scan(out)

    def start_hotspot(self, ssid):
        _run(['nmcli', 'connection', 'delete', HOTSPOT_CON])
        add = _run(['nmcli', 'connection', 'add', 'save', 'no', 'type', 'wifi', 'ifname', 'wlan0',
                    'con-name', HOTSPOT_CON, 'autoconnect', 'no', 'ssid', ssid,
                    '802-11-wireless.mode', 'ap', '802-11-wireless.band', 'bg',
                    'ipv4.method', 'shared', 'ipv4.addresses', f'{HOTSPOT_IP}/24',
                    'ipv6.method', 'disabled'])
        up = _run(['nmcli', '--wait', '20', 'connection', 'up', HOTSPOT_CON])
        if add.returncode or up.returncode:
            raise RuntimeError(f'hotspot failed: {add.stderr.strip()} {up.stderr.strip()}')

    def stop_hotspot(self):
        _run(['nmcli', 'connection', 'down', HOTSPOT_CON])
        _run(['nmcli', 'connection', 'delete', HOTSPOT_CON])

    def join(self, ssid, password, hidden, timeout=45):
        # Tried under a temporary name, so a typo doesn't throw away a saved
        # profile that works. Only once it connects does it replace any saved
        # one of the same name (same network, new password). NetworkManager
        # works out WPA2/WPA3/open from the scan.
        _run(['nmcli', 'connection', 'delete', 'id', NEW_CON])
        _run(['nmcli', 'device', 'wifi', 'rescan'])
        time.sleep(4)
        cmd = ['nmcli', '--wait', str(timeout), 'device', 'wifi', 'connect', ssid,
               'ifname', 'wlan0', 'name', NEW_CON]
        if password:
            cmd += ['password', password]
        if hidden:
            cmd += ['hidden', 'yes']
        try:
            ok = _run(cmd, timeout=timeout + 15).returncode == 0
        except (subprocess.SubprocessError, OSError):
            ok = False
        if not ok:
            _run(['nmcli', 'connection', 'delete', 'id', NEW_CON])
            return False
        _run(['nmcli', 'connection', 'delete', 'id', ssid])
        _run(['nmcli', 'connection', 'modify', NEW_CON, 'connection.id', ssid])
        return True

    def client_count(self):
        out = _run(['iw', 'dev', 'wlan0', 'station', 'dump']).stdout
        return sum(1 for line in out.splitlines() if line.startswith('Station '))

    def ip(self):
        out = _run(['ip', '-4', '-o', 'addr', 'show', 'scope', 'global']).stdout
        for m in re.finditer(r'inet (\d+\.\d+\.\d+\.\d+)/', out):
            if m.group(1) != HOTSPOT_IP:
                return m.group(1)
        return None


class System:

    def set_password(self, user, password):
        if _run(['chpasswd'], input=f'{user}:{password}\n').returncode:
            return False
        _run(['passwd', '-u', user])
        return True

    def set_timezone(self, tz):
        _run(['timedatectl', 'set-timezone', tz])
        # Night dimming works out sunset from the time zone.
        _run(['systemctl', 'try-restart', 'brightness-control.service'])

    def set_country(self, cc):
        _run(['iw', 'reg', 'set', cc])
        if os.path.exists('/usr/bin/raspi-config'):
            _run(['raspi-config', 'nonint', 'do_wifi_country', cc])

    def restart_tty1(self):
        _run(['systemctl', 'restart', 'getty@tty1.service'])

    def emulator_running(self):
        return any(_run(['pgrep', '-x', name]).returncode == 0
                   for name in ('BasiliskII', 'SheepShaver'))

    def beep(self):
        self.sound('beep')

    def sound(self, name):
        # Short tones made here (no Apple sounds), so setup can be heard as
        # well as seen: the screen alone can look as if nothing happened.
        path = RUN_DIR / f'{name}.wav'
        if not path.exists():
            write_tones(path, SOUNDS[name])
        # One at a time and to the end: the Pi's audio plays one sound at once,
        # and "connected" is followed straight away by "next".
        try:
            subprocess.run(['aplay', '-q', str(path)], timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.SubprocessError, OSError):
            pass


# (frequency in Hz, seconds); 0 Hz is a rest.
SOUNDS = {
    'beep': ((880, .15),),                                         # button hold registered
    'ready': ((659, .12), (988, .22)),                             # setup network is up
    'connected': ((523, .1), (659, .1), (784, .1), (1047, .3)),    # joined the Wi-Fi
    'next': ((0, .3), (1319, .12), (0, .06), (1319, .2)),          # ...and there's a step 2
    'failed': ((392, .2), (262, .4)),                              # didn't work
}


def write_tones(path, notes, rate=22050):
    import math
    import wave
    frames = bytearray()
    for freq, secs in notes:
        n = int(rate * secs)
        for i in range(n):
            env = min(1.0, i / (rate * .005)) * (1 - i / n) ** 1.5 if freq else 0
            v = int(9000 * env * math.sin(2 * math.pi * freq * i / rate))
            frames += v.to_bytes(2, 'little', signed=True)
    tmp = Path(str(path) + '.tmp')
    with wave.open(str(tmp), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    tmp.replace(path)


class Controller:
    """Decides what setup is doing. tick() runs about once a second; the web
    pages call submit_wifi() and submit_rom() from their own threads."""

    def __init__(self, config, nm, system, clock=time.monotonic, run_dir=RUN_DIR,
                 state_dir=STATE_DIR, hostname=None, suffix=None, spawn=None,
                 sleep=time.sleep, zone_tab=None, chown=None):
        self.config = config
        self.nm = nm
        self.system = system
        self.clock = clock
        self.run_dir = Path(run_dir)
        self.state_dir = Path(state_dir)
        self.hostname = hostname or socket.gethostname()
        self.ssid = hotspot_ssid(suffix or serial_suffix())
        self.spawn = spawn or (lambda fn: threading.Thread(target=fn, daemon=True).start())
        self.sleep = sleep
        self._zone_tab = zone_tab
        self.chown = chown or self._chown_to_user
        self.lock = threading.RLock()

        self.phase = None      # set by the first tick()
        self.reason = None     # first-run | button
        self.error = None
        self.network = None
        self.networks = []
        self.ip = None
        self.hotspot_since = 0.0
        self.last_client = 0.0
        self.trial_started = 0.0
        self.last_nm_poll = -1e9
        self.started_at = None
        self._last_status = None

    # --- files -------------------------------------------------------------
    def _flag(self, name):
        return (self.run_dir / name).exists()

    def _clear(self, name):
        try:
            (self.run_dir / name).unlink()
        except FileNotFoundError:
            pass

    def needs_password(self):
        return (self.state_dir / 'needs-password').exists()

    def rom_path(self):
        try:
            for line in Path(self.config.prefs).read_text().splitlines():
                if line.startswith('rom '):
                    p = line[4:].strip()
                    return Path(p if p.startswith('/') else os.path.join(self.config.home, p))
        except OSError:
            pass
        return Path(self.config.home) / 'ROM'

    def has_rom(self):
        return self.rom_path().is_file()

    def zone_tab(self):
        if self._zone_tab is None:
            try:
                self._zone_tab = Path(ZONE_TAB).read_text()
            except OSError:
                self._zone_tab = ''
        return self._zone_tab

    def _chown_to_user(self, path):
        pw = pwd.getpwnam(self.config.user)
        os.chown(path, pw.pw_uid, pw.pw_gid)

    # --- state ---------------------------------------------------------------
    def state(self):
        with self.lock:
            return {
                'phase': self.phase or 'preparing',
                'reason': self.reason,
                'ssid': self.ssid,
                'networks': list(self.networks),
                'needs_password': self.needs_password(),
                'error': self.error,
                'network': self.network,
                'hostname': self.hostname,
                'url': f'http://{self.hostname}.local/',
                'ip': self.ip,
            }

    def screen_for(self, s):
        phase = s['phase']
        ssid = s['ssid']
        blank = {'title': '', 'step': None, 'icon': None, 'lines': [], 'qr': None, 'note': None}

        def screen(**kw):
            return dict(blank, **kw)
        note = 'Press left button to cancel' if s['reason'] == 'button' else None
        if phase == 'hotspot':
            if s['error']:
                return screen(title="Couldn't join", step=1, qr=wifi_qr(ssid), note=note,
                              lines=[f"Couldn't join {s['network']}.", 'Check the password and',
                                     'join this network again:', '**' + ssid])
            return screen(title='Set up Wi-Fi', step=1, qr=wifi_qr(ssid), note=note,
                          lines=['Join this Wi-Fi network', 'on your phone:', '**' + ssid, '',
                                 'or scan the code.'])
        if phase == 'connecting':
            return screen(title='Connecting…', step=1, icon='wifi',
                          lines=['Joining', '**' + (s['network'] or ''), '', 'One moment…'])
        if phase == 'waiting':
            return screen(title='Looking for Wi-Fi…', icon='wifi',
                          lines=['To use a different', 'network, hold the left', 'button for 10 seconds.'])
        if phase == 'rom':
            if s['error']:
                lines = ["That ROM didn't start", 'the Mac. Try another.', '']
            else:
                lines = ['++Wi-Fi connected.', '']
            if s['ip']:
                # The code opens the page by address: .local names don't
                # resolve on every network.
                return screen(title='Add a ROM', step=2, qr=f"http://{s['ip']}/",
                              lines=lines + ['Scan the code, or open', f"**http://{s['ip']}",
                                             'on a computer.'])
            return screen(title='Add a ROM', step=2, icon='wifi',
                          lines=lines + ['On a computer, open', f"**{s['hostname']}.local"])
        if phase == 'starting':
            return screen(title='Starting up…', icon='check',
                          lines=['Got the ROM.', 'Listen for the chime!'])
        if phase == 'preparing':
            return screen(title='Wi-Fi setup', icon='wifi', lines=['One moment…'])
        return blank

    def _write_status(self):
        s = self.state()
        s['screen'] = self.screen_for(s)
        text = json.dumps(s, sort_keys=True)
        if text == self._last_status:
            return
        tmp = self.run_dir / 'status.json.tmp'
        tmp.write_text(text)
        os.chmod(tmp, 0o644)
        tmp.replace(self.run_dir / 'status.json')
        self._last_status = text

    # --- decisions -----------------------------------------------------------
    def tick(self):
        with self.lock:
            now = self.clock()
            if self.started_at is None:
                self.started_at = now
                self._clear('rom-trial')   # left over from before a restart
            if self._flag('cancel'):
                self._clear('cancel')
                if self.phase == 'hotspot' and self.reason == 'button':
                    self._end_button_setup()
            if self._flag('requested') and self.phase not in ('hotspot', 'connecting'):
                self._start_setup('button')
            elif self.phase == 'hotspot':
                if self.reason == 'button':
                    if self.nm.client_count() > 0:
                        self.last_client = now
                    if now - max(self.hotspot_since, self.last_client) > GIVE_UP_S:
                        self._end_button_setup()
            elif self.phase == 'starting':
                self._check_trial(now)
            elif self.phase == 'off':
                if not self.has_rom():          # deleted, or moved aside by the launcher
                    self.last_nm_poll = now
                    self._settle()
            elif self.phase in (None, 'preparing', 'waiting', 'rom'):
                if now - self.last_nm_poll >= NM_POLL_S or self.phase is None:
                    self.last_nm_poll = now
                    self._settle()
            self._write_status()

    def _settle(self):
        try:
            saved = self.nm.saved_wifi()
        except Exception as e:  # ask again at the next poll
            print(f'mac-setup: {_describe(e)}', file=sys.stderr, flush=True)
            return
        if not saved:
            # No Wi-Fi saved, but a wired connection (USB Ethernet) is not a first run.
            ip = self.nm.ip()
            if ip:
                self.ip = ip
                self.phase = 'off' if self.has_rom() else 'rom'
                return
            if self.nm.has_wired() and self.clock() - self.started_at < WIRED_GRACE_S:
                self.phase = 'preparing'
                return
            self._start_setup('first-run')
            return
        if self.has_rom():
            self.phase = 'off'
            return
        self.ip = self.nm.ip()
        self.phase = 'rom' if self.ip else 'waiting'

    def _start_setup(self, reason, error=None):
        self.reason = reason
        self.error = error
        self._clear('rom-trial')     # a ROM still on trial is abandoned
        self.phase = 'preparing'
        self._write_status()         # the screen says "One moment…" during the scan
        self.networks = []
        for attempt in range(SCAN_TRIES):
            try:
                self.networks = self.nm.scan()
            except Exception as e:
                print(f'mac-setup: scan: {_describe(e)}', file=sys.stderr, flush=True)
            if self.networks:
                break
            if attempt < SCAN_TRIES - 1:
                self.sleep(3)
        try:
            self.nm.start_hotspot(self.ssid)
        except Exception as e:  # tried again on the next tick
            print(f'mac-setup: {_describe(e)}', file=sys.stderr, flush=True)
            return
        self.phase = 'hotspot'
        self.hotspot_since = self.last_client = self.clock()
        self.system.sound('ready')

    def _end_button_setup(self):
        self.nm.stop_hotspot()
        self._clear('requested')
        self.reason = None
        self.error = None
        self.phase = None
        self._settle()

    def _check_trial(self, now):
        if not self.has_rom():
            # The launcher moved it aside: the emulator quit straight away.
            self._clear('rom-trial')
            self.phase = 'rom'
            self.error = "That ROM didn't start the Mac. Try another."
            self.system.sound('failed')
            self.ip = self.nm.ip()
        elif now - self.trial_started >= TRIAL_S and self.system.emulator_running():
            self._clear('rom-trial')
            self.phase = 'off'
            self.error = None
        elif now - self.trial_started >= TRIAL_ABANDON_S:
            self._clear('rom-trial')
            self.phase = 'off'

    # --- from the web pages -------------------------------------------------
    def submit_wifi(self, req):
        with self.lock:
            if self.phase != 'hotspot':
                return
            if self.needs_password() and req.mac_password:
                if not self.system.set_password(self.config.user, req.mac_password):
                    self.error = "Couldn't set the Mac's password. Try again."
                    self._write_status()
                    return self.error
                (self.state_dir / 'needs-password').unlink()
            self.phase = 'connecting'
            self.network = req.ssid
            self.error = None
            self._write_status()
        self.spawn(lambda: self._join(req))
        return None

    def _join(self, req):
        try:
            self.sleep(JOIN_DELAY_S)
            self.nm.stop_hotspot()
            # After the hotspot is down: a new Wi-Fi country can reset the radio.
            if req.timezone:
                self.system.set_timezone(req.timezone)
                cc = country_for_timezone(req.timezone, self.zone_tab())
                if cc:
                    self.system.set_country(cc)
            ok = self.nm.join(req.ssid, req.wifi_password, req.hidden)
        except Exception as e:
            print(f'mac-setup: joining failed: {_describe(e)}', file=sys.stderr, flush=True)
            ok = False
        with self.lock:
            if ok:
                self._clear('requested')
                self.reason = None
                self.system.sound('connected')
                if self.has_rom():
                    self.phase = 'off'
                else:
                    self.ip = self.nm.ip()
                    self.phase = 'rom'
                    self.system.sound('next')    # there's a second step
            else:
                self.system.sound('failed')
                self._start_setup(self.reason or 'first-run',
                                  error=f"Couldn't join {req.ssid}. Check the password and try again.")
            self._write_status()

    def submit_rom(self, data):
        with self.lock:
            if self.phase != 'rom':
                return 'This Mac already has a ROM.'
            try:
                rom = extract_rom(data, self.config.emulator)
            except RomError as e:
                return str(e)
            path = self.rom_path()
            tmp = path.with_name(path.name + '.part')
            tmp.write_bytes(rom)
            os.chmod(tmp, 0o644)
            self.chown(tmp)
            tmp.replace(path)
            (self.run_dir / 'rom-trial').touch()
            self.trial_started = self.clock()
            self.phase = 'starting'
            self.error = None
            self._write_status()
            return None


class WebServer:
    """The setup pages' web server, listening only while setup has a page to
    show (SERVE_PHASES). sync() starts or stops it to match; it runs after
    every tick."""

    def __init__(self, controller, factory, port=80):
        self.controller = controller
        self.factory = factory      # (controller, port) -> a server with serve_forever()
        self.port = port
        self.server = None

    def sync(self):
        wanted = self.controller.state()['phase'] in SERVE_PHASES
        if wanted and self.server is None:
            try:
                self.server = self.factory(self.controller, self.port)
            except OSError as e:    # port busy: try again on the next tick
                print(f'mac-setup: web server: {e}', file=sys.stderr, flush=True)
                return
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        elif not wanted and self.server is not None:
            server, self.server = self.server, None
            server.shutdown()
            server.server_close()


# --- command line ------------------------------------------------------------
def serve():
    import mac_setup_web
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    controller = Controller(load_config(), NM(), System())
    web = WebServer(controller, mac_setup_web.make_server)
    print(f'mac-setup running, hotspot name "{controller.ssid}"', flush=True)
    while True:
        try:
            controller.tick()
            web.sync()
        except Exception as e:  # keep going; the next tick tries again
            print(f'mac-setup: {_describe(e)}', file=sys.stderr, flush=True)
        time.sleep(1)


def request():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / 'requested').touch()
    system = System()
    system.restart_tty1()   # quit Mac OS; the launcher then shows the setup screen
    system.beep()
    return 0


def cancel():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / 'cancel').touch()
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd == 'serve':
        return serve()
    if cmd == 'request':
        return request()
    if cmd == 'cancel':
        return cancel()
    if cmd == 'screen':
        import mac_setup_screen
        return mac_setup_screen.main(RUN_DIR / 'status.json', RUN_DIR / 'requested')
    print('usage: mac-setup serve|request|cancel|screen', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
