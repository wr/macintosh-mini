#!/usr/bin/python3 -SE
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# mini_link.py, installed as /usr/local/bin/mini-link
#
# Answers the Mini's Mac OS software (the Maclock Status menu bar item and the
# Maclock Setup control panel) on the Mac's modem port. Basilisk II and
# SheepShaver run it on a pty when Mac OS opens the port, set in their prefs:
#
#   seriala |/usr/local/bin/mini-link
#
# and it ends when Mac OS closes the port. Mac OS opens and closes the port
# twice at every start, so nothing is kept here between requests: settings
# live on disk.
#
# The Mac sends one request and reads its reply before the next. Everything is
# big-endian:
#
#   request  'M' 'i', code (word), three words p0 p1 p2: 10 bytes
#   reply    'M' 'i', the same code (word), length (word), length bytes
#
# The codes and what each answers are in the Macintosh Mini ESP32's
# mac/MiniLink.h, which both builds follow.
#
# stdin, stdout and stderr are all the pty, so nothing is ever printed: every
# byte written is part of a reply. The Mac waits up to a second for each part
# of a reply and does nothing else meanwhile, so nothing slow happens before
# one: downloads and sounds run in a separate process.
# ####################################

import os
import struct
import sys
import time

LINK_VERSION = 1

PARAM_ERR = -50     # a value out of range
IO_ERR = -36        # in range, but it couldn't be done

# The same chimes, in the same order, as CHIMES_DATA in setup.sh: name, year,
# file (without .wav). Mac OS numbers them from 1.
CHIMES = (
    ("Macintosh I", "1984", "StartupMacI"),
    ("Macintosh II", "1987", "StartupMacII"),
    ("Macintosh LC", "1990", "StartupMacLC"),
    ("Quadra", "1991", "StartupMacQuadra"),
    ("Quadra AV", "1993", "StartupMacQuadraAV"),
    ("Power Mac", "1994", "StartupPowerMac"),
    ("Power Mac PCI", "", "StartupPowerMacCard"),
    ("Twentieth Anniversary", "1997", "StartupTwentiethAnniversaryMac"),
)
NO_CHIME = "None"

# The crash sound that goes with each chime, as crash_for_chime in setup.sh
CRASHES = {
    "StartupMacI": "CrashMacII",
    "StartupMacII": "CrashMacII",
    "StartupMacLC": "CrashMacLC",
    "StartupMacQuadra": "CrashMacQuadra",
    "StartupMacQuadraAV": "CrashMacQuadraAV",
    "StartupPowerMac": "CrashMacQuadraAV",
    "StartupPowerMacCard": "CrashMacQuadraAV",
    "StartupTwentiethAnniversaryMac": "CrashMacQuadraAV",
}
CHIME_URL = "https://raw.githubusercontent.com/wr/macintosh-mini/main/emulators/chimes/"

APPLY = "/usr/local/sbin/mini-link-apply"
POWER_SUPPLY = "/sys/class/power_supply"
RUN_DIR = "/run/brightness-control"     # brightness_control.py's level and socket
INSTALL_STATE = "/etc/macintosh-mini.conf"


def log(message):
    """To the journal. Never to stderr: that's the Mac's modem port."""
    try:
        import syslog
        syslog.openlog("mini-link")
        syslog.syslog(message)
    except Exception:
        pass


def read_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except (OSError, ValueError):
        return None


def pstr(text, most=255):
    """A Pascal string of at most `most` characters, in Mac OS's encoding."""
    data = text if isinstance(text, bytes) else text.encode("mac_roman", "replace")
    data = data[:most]
    return bytes([len(data)]) + data


def pstr_field(text, most):
    """A Pascal string in a field that's always most + 1 bytes."""
    return pstr(text, most).ljust(most + 1, b"\0")


def chime_name(entry):
    name, year, _ = entry
    return f"{name} ({year})" if year else name


# --- Requests --------------------------------------------------------------

class Requests:
    """Cuts the bytes from the Mac into requests, skipping anything before
    'M' 'i'."""

    def __init__(self):
        self.buf = b""

    def feed(self, data):
        """The requests completed by `data`, as (code, p0, p1, p2)."""
        self.buf += data
        found = []
        while True:
            at = self.buf.find(b"Mi")
            if at < 0:
                # Keep a last 'M': its 'i' may be the next byte to come
                self.buf = b"M" if self.buf.endswith(b"M") else b""
                break
            if len(self.buf) - at < 10:
                self.buf = self.buf[at:]
                break
            found.append(struct.unpack(">Hhhh", self.buf[at + 2:at + 10]))
            self.buf = self.buf[at + 10:]
        return found


def reply(code, data=b""):
    return b"Mi" + struct.pack(">HH", code, len(data)) + data


# --- The battery -----------------------------------------------------------

def read_battery(root=POWER_SUPPLY):
    """(percent, charging) from the first battery Linux knows of, or
    (None, False). Boards up to rev 2026.11 have no gauge, so there's none to
    find; a board with a gauge the kernel has a driver for shows up here by
    itself."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None, False
    for name in names:
        supply = os.path.join(root, name)
        if read_text(os.path.join(supply, "type")) != "Battery":
            continue
        # A Bluetooth keyboard's or mouse's own battery, not the Mini's
        if read_text(os.path.join(supply, "scope")) == "Device":
            continue
        try:
            percent = int(read_text(os.path.join(supply, "capacity")))
        except (TypeError, ValueError):
            continue
        charging = read_text(os.path.join(supply, "status")) == "Charging"
        return max(0, min(100, percent)), charging
    return None, False


# --- Wi-Fi -----------------------------------------------------------------

SIOCGIWESSID = 0x8B1B


def wifi_interface(root="/sys/class/net"):
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None
    for name in names:
        if os.path.isdir(os.path.join(root, name, "wireless")):
            return name
    return None


def wifi_signal(iface, path="/proc/net/wireless"):
    """Signal in dBm from the kernel's table, or 0."""
    try:
        with open(path) as f:
            for line in f:
                name, sep, rest = line.partition(":")
                if sep and name.strip() == iface:
                    return int(float(rest.split()[2]))
    except (OSError, ValueError, IndexError):
        pass
    return 0


def wifi_name_ioctl(iface):
    """The network's name, asked of the kernel directly (no program to run,
    so it's instant). b"" when not connected. Raises OSError where the kernel
    doesn't answer this."""
    import array
    import fcntl
    import socket
    name = array.array("B", bytes(33))
    request = struct.pack("16sPHH", iface.encode(), name.buffer_info()[0], 32, 0)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        answer = fcntl.ioctl(s.fileno(), SIOCGIWESSID, request.ljust(40, b"\0"))
    length = struct.unpack_from("16sPHH", answer)[2]
    return name.tobytes()[:min(length, 32)].rstrip(b"\0")


def wifi_name_iw(iface):
    """The same from `iw`, for a kernel that doesn't answer the ioctl. Given
    0.4 s at most."""
    import subprocess
    try:
        out = subprocess.run(["iw", "dev", iface, "link"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=0.4).stdout
    except (OSError, subprocess.SubprocessError):
        return b""
    for line in out.splitlines():
        key, sep, value = line.strip().partition(b": ")
        if sep and key == b"SSID":
            return value[:32]
    return b""


def ip_address():
    """The address this Mini has on its network, or ''. Nothing is sent:
    connecting a UDP socket only picks the route."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return ""


class Wifi:
    """(name, signal in dBm, address); the name is b"" when not connected."""

    IW_EVERY_S = 10     # the slow way's answer is kept this long

    def __init__(self):
        self.use_iw = False
        self.iw_name = b""
        self.iw_at = None

    def read(self):
        iface = wifi_interface()
        if iface is None:
            return b"", 0, ip_address()
        name = b""
        if not self.use_iw:
            try:
                name = wifi_name_ioctl(iface)
            except (OSError, ValueError, struct.error):
                self.use_iw = True
        if self.use_iw:
            now = time.monotonic()
            if self.iw_at is None or now - self.iw_at > self.IW_EVERY_S:
                self.iw_name, self.iw_at = wifi_name_iw(iface), now
            name = self.iw_name
        return name, (wifi_signal(iface) if name else 0), ip_address()


# --- Things that need root, or take a while ----------------------------------

def apply(*args, timeout=0.8):
    """Runs mini-link-apply as root (the sudoers rule setup.sh installs allows
    exactly that program). True when it worked. In its own session, so the
    Mac closing the port can't stop it halfway, and so sudo never sees the
    pty. If it's still going at the timeout it's left to finish."""
    import subprocess
    try:
        p = subprocess.Popen(["sudo", "-n", APPLY, *[str(a) for a in args]],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log(f"couldn't run {APPLY}: {e}")
        return False
    try:
        return p.wait(timeout) == 0
    except subprocess.TimeoutExpired:
        return True


def spawn(*args):
    """Starts this program again for a job that takes a while (a download, a
    sound), on its own: it outlives the Mac closing the port, and the reply
    doesn't wait for it."""
    import subprocess
    try:
        subprocess.Popen([sys.executable, "-SE", os.path.abspath(__file__), *args],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError as e:
        log(f"couldn't start {args}: {e}")
        return False


def send_level(value, run_dir=RUN_DIR):
    """Hands brightness_control.py a level, as if the dial had turned."""
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.sendto(str(value).encode(), os.path.join(run_dir, "level.sock"))
        return True
    except OSError:
        return False


# --- The Mini --------------------------------------------------------------

class Mini:
    """Answers each request. Everything it reads or runs can be swapped for
    the tests."""

    def __init__(self, home=None, power_supply=POWER_SUPPLY, run_dir=RUN_DIR,
                 install_state=INSTALL_STATE, night_conf=None, wifi=None,
                 apply=apply, spawn=spawn, send_level=send_level,
                 zone=None, zone_tabs=None, now=None):
        self.home = home or os.path.expanduser("~")
        self.power_supply = power_supply
        self.run_dir = run_dir
        self.install_state = install_state
        self.night_conf = night_conf
        self.wifi = wifi or Wifi().read
        self.apply = apply
        self.spawn = spawn
        self.send_level = send_level
        self.zone = zone                # the time zone's name, for the tests
        self.zone_tabs = zone_tabs      # (zone.tab's text, every table's text)
        self.now = now                  # an aware local datetime, for the tests
        self.zone_list = None
        self.zone_reply = None
        self.sent_level = None

    # What's set now

    def night(self):
        import night_schedule
        try:
            return night_schedule.load_config(self.night_conf or night_schedule.CONFIG)
        except (OSError, ValueError):
            return night_schedule.NightConfig()

    def tabs(self):
        if self.zone_tabs is None:
            import night_schedule
            self.zone_tabs = (night_schedule.read_zone_tab((night_schedule.ZONE_TAB,)),
                              night_schedule.read_zone_tab())
        return self.zone_tabs

    def zones(self):
        if self.zone_list is None:
            import night_schedule
            self.zone_list = night_schedule.zone_names(self.tabs()[0])
        return self.zone_list

    def chime(self):
        """The startup chime's number, 0 for none (or one this list lacks)."""
        tag = read_text(os.path.join(self.home, ".macintosh_chime"))
        for i, entry in enumerate(CHIMES, 1):
            if entry[0] == tag:
                return i
        return 0

    def brightness(self):
        # Just after 'Mb' the level file may not have caught up
        if self.sent_level and time.monotonic() - self.sent_level[1] < 0.5:
            return self.sent_level[0]
        try:
            return max(0, min(100, int(read_text(os.path.join(self.run_dir, "level")))))
        except (TypeError, ValueError):
            return 100

    def software(self):
        for line in (read_text(self.install_state) or "").splitlines():
            if line.startswith("VERSION="):
                return line[len("VERSION="):].strip()
        return ""

    # The status blocks

    def status(self):
        percent, charging = read_battery(self.power_supply)
        name, signal, address = self.wifi()
        if isinstance(name, bytes):     # as networks are named, in UTF-8
            name = name.decode("utf-8", "replace")
        flags = ((1 if percent is not None else 0) | (2 if charging else 0)
                 | (8 if name else 0) | (16 if self.night().on else 0))
        return (struct.pack(">6h", LINK_VERSION, flags,
                            -1 if percent is None else percent, signal,
                            self.chime(), len(CHIMES))
                + pstr_field(name, 32) + b"\0" + pstr_field(address, 15))

    def chimes(self):
        return bytes([len(CHIMES)]) + b"".join(pstr(chime_name(c)) for c in CHIMES)

    def settings(self):
        import night_schedule
        cfg = self.night()
        zones = self.zones()
        if self.now is None:
            from datetime import datetime
            time.tzset()    # 'Mz' may just have changed the zone
            now = datetime.now().astimezone()
        else:
            now = self.now
        zone = self.zone or night_schedule.system_timezone()
        coords = night_schedule.place(cfg, zone, self.tabs()[1])
        sunset = night_schedule.sun_minutes(coords, now, True)
        sunrise = night_schedule.sun_minutes(coords, now, False, 1)
        flags = (16 if cfg.on else 0) | (32 if coords is not None else 0)
        return (struct.pack(">10h", LINK_VERSION, self.brightness(), flags,
                            cfg.from_, cfg.until, cfg.level,
                            zones.index(zone) if zone in zones else -1, len(zones),
                            self.chime(), len(CHIMES))
                + pstr_field(self.software(), 15)
                + pstr_field("", 95)    # update news: none on this build yet
                + struct.pack(">hh", -1 if sunset is None else sunset,
                              -1 if sunrise is None else sunrise))

    def zones_block(self):
        if self.zone_reply is None:
            zones = self.zones()
            self.zone_reply = struct.pack(">H", len(zones)) + b"".join(pstr(z) for z in zones)
        return self.zone_reply

    # The set codes: 0 done, PARAM_ERR out of range, IO_ERR couldn't

    def set_chime(self, n):
        if not 0 <= n <= len(CHIMES):
            return PARAM_ERR
        tag_file = os.path.join(self.home, ".macintosh_chime")
        before = read_text(tag_file) or ""
        # Say so at once; the download and install follow, and put the old
        # name back if they fail
        try:
            with open(tag_file, "w") as f:
                f.write((CHIMES[n - 1][0] if n else NO_CHIME) + "\n")
        except OSError:
            return IO_ERR
        if self.spawn("--chime", str(n), before):
            return 0
        restore_chime_name(self.home, before)
        return IO_ERR

    def set_night(self, **changes):
        cfg = self.night()
        for key, value in changes.items():
            setattr(cfg, key, value)
        ok = self.apply("night", int(cfg.on), cfg.from_, cfg.until, cfg.level)
        return 0 if ok else IO_ERR

    def set_dim(self, on):
        if on not in (0, 1):
            return PARAM_ERR
        return self.set_night(on=bool(on))

    def set_times(self, start, end):
        import night_schedule
        if not (0 <= start < 24 * 60 or start == night_schedule.SUNSET):
            return PARAM_ERR
        if not (0 <= end < 24 * 60 or end == night_schedule.SUNRISE):
            return PARAM_ERR
        return self.set_night(from_=start, until=end)

    def set_dim_level(self, level):
        if not 0 <= level <= 100:
            return PARAM_ERR
        return self.set_night(level=level)

    def set_zone(self, n):
        zones = self.zones()
        if not 0 <= n < len(zones):
            return PARAM_ERR
        return 0 if self.apply("zone", zones[n]) else IO_ERR

    def set_brightness(self, level):
        if not 2 <= level <= 100:
            return PARAM_ERR
        if not self.send_level(level, self.run_dir):
            return IO_ERR
        self.sent_level = (level, time.monotonic())
        return 0

    def play_chime(self, n):
        if not 1 <= n <= len(CHIMES):
            return PARAM_ERR
        return 0 if self.spawn("--play", str(n)) else IO_ERR

    def answer(self, code, p0=0, p1=0, p2=0):
        """The whole reply to one request."""
        blocks = {0x4D53: self.status,          # 'MS'
                  0x4D43: self.chimes,          # 'MC'
                  0x4D50: self.settings,        # 'MP'
                  0x4D5A: self.zones_block}     # 'MZ'
        sets = {0x4D63: lambda: self.set_chime(p0),         # 'Mc'
                0x4D64: lambda: self.set_dim(p0),           # 'Md'
                0x4D74: lambda: self.set_times(p0, p1),     # 'Mt'
                0x4D6C: lambda: self.set_dim_level(p0),     # 'Ml'
                0x4D7A: lambda: self.set_zone(p0),          # 'Mz'
                0x4D62: lambda: self.set_brightness(p0),    # 'Mb'
                0x4D70: lambda: self.play_chime(p0)}        # 'Mp'
        try:
            if code in blocks:
                return reply(code, blocks[code]())
            if code in sets:
                return reply(code, struct.pack(">h", sets[code]()))
        except Exception as e:
            # Better "I don't know that one" than a Mac left waiting
            log(f"request {code:#06x} failed: {e!r}")
        return reply(code)


# --- Chimes: fetching, installing, playing ---------------------------------

def is_wav(path):
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError:
        return False
    return head[:4] == b"RIFF" and head[8:12] == b"WAVE"


def fetch_sound(name, cache):
    """The sound's file, downloaded from the repository the first time and
    kept. Raises OSError when it can't be had."""
    import subprocess
    path = os.path.join(cache, name + ".wav")
    if is_wav(path):
        return path
    os.makedirs(cache, exist_ok=True)
    part = f"{path}.{os.getpid()}.part"
    try:
        subprocess.run(["curl", "-fsSL", "--retry", "2", "--max-time", "60", "-o", part,
                        CHIME_URL + name + ".wav"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        if not is_wav(part):
            raise OSError(f"couldn't download {name}.wav")
        os.replace(part, path)
    except subprocess.SubprocessError as e:
        raise OSError(f"couldn't download {name}.wav: {e}")
    finally:
        try:
            os.unlink(part)
        except OSError:
            pass
    return path


def copy_file(src, dst):
    with open(src, "rb") as f:
        data = f.read()
    with open(dst + ".new", "wb") as f:
        f.write(data)
    os.replace(dst + ".new", dst)


def restore_chime_name(home, before):
    tag_file = os.path.join(home, ".macintosh_chime")
    try:
        if before:
            with open(tag_file, "w") as f:
                f.write(before + "\n")
        else:
            os.unlink(tag_file)
    except OSError:
        pass


def install_chime(n, before, home, cache, fetch=fetch_sound, apply=apply):
    """Makes chime n the startup chime, as the installer's settings editor
    does: the sound and its crash sound into the home folder, then into
    /usr/local/bin, where the launcher plays them from. 0 is no chime. If it
    fails, the chime's name goes back to what it was."""
    chime = os.path.join(home, "chime.wav")
    try:
        with open(chime, "rb") as f:
            old = f.read()
    except OSError:
        old = None
    try:
        if n:
            name = CHIMES[n - 1][2]
            copy_file(fetch(name, cache), chime)
            try:
                copy_file(fetch(CRASHES[name], cache), os.path.join(home, "crash.wav"))
            except OSError as e:
                log(f"keeping the old crash sound: {e}")
        else:
            try:
                os.unlink(chime)
            except FileNotFoundError:
                pass
        if not apply("sounds", timeout=20):
            raise OSError("couldn't install the sounds")
        return True
    except OSError as e:
        log(f"chime not changed: {e}")
        restore_chime_name(home, before)
        # The home folder's copy too: the installer installs from it on an update
        try:
            if old is None:
                os.unlink(chime)
            else:
                with open(chime + ".new", "wb") as f:
                    f.write(old)
                os.replace(chime + ".new", chime)
        except OSError:
            pass
        return False


def play_chime(n, cache, fetch=fetch_sound):
    """Plays chime n now, on the speaker. One at a time: a second request
    while one is playing is dropped."""
    import fcntl
    import subprocess
    os.makedirs(cache, exist_ok=True)
    with open(os.path.join(cache, "playing"), "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        try:
            path = fetch(CHIMES[n - 1][2], cache)
            done = subprocess.run(["aplay", "-q", path], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=30)
            if done.returncode:
                log(f"aplay couldn't play {path} (exit {done.returncode})")
            return done.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            log(f"chime not played: {e}")
            return False


# --- The port --------------------------------------------------------------

def make_raw(fd):
    """Raw mode, so no echo or line editing reaches the Mac. Takes effect at
    once and keeps what's already waiting: the Mac's first request may be."""
    import termios
    try:
        attrs = termios.tcgetattr(fd)
    except (termios.error, OSError):
        return      # not a terminal: the tests' pipes
    attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP
                  | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON
                  | termios.IXOFF | termios.IXANY)
    attrs[1] &= ~termios.OPOST
    attrs[2] = (attrs[2] & ~(termios.CSIZE | termios.PARENB)) | termios.CS8
    attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG
                  | termios.IEXTEN)
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def write_all(fd, data):
    while data:
        data = data[os.write(fd, data):]


def serve(mini, fd_in=0, fd_out=1):
    """Answers requests until the Mac closes the port."""
    requests = Requests()
    while True:
        try:
            data = os.read(fd_in, 256)
        except OSError:
            return      # the port closed
        if not data:
            return
        for request in requests.feed(data):
            try:
                write_all(fd_out, mini.answer(*request))
            except OSError:
                return


def main(argv):
    # Nothing but replies may reach the pty, a Python error least of all
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    cache = os.path.join(os.path.expanduser("~"), ".cache", "mini-link")
    if len(argv) == 4 and argv[1] == "--chime":
        return 0 if install_chime(int(argv[2]), argv[3], os.path.expanduser("~"), cache) else 1
    if len(argv) == 3 and argv[1] == "--play":
        return 0 if play_chime(int(argv[2]), cache) else 1
    make_raw(0)
    serve(Mini())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
