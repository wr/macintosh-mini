#!/usr/bin/python3 -I
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# mini_link_apply.py, installed as /usr/local/sbin/mini-link-apply
#
# The three things mini-link changes that need root. mini-link runs as the
# person logged in, and setup.sh lets that person run this one program as
# root (/etc/sudoers.d/020-mini-link), so everything here is checked as if
# anyone had typed it:
#
#   mini-link-apply zone <Area/City>
#       sets the time zone. Only a name listed in tzdata's zone.tab.
#   mini-link-apply night <on> <from> <until> <level>
#       saves night dimming. on is 0 or 1; from is minutes after midnight
#       (0-1439) or 1440 for sunset; until is 0-1439 or 1441 for sunrise;
#       level is 0-100. Only these four numbers reach the settings file.
#   mini-link-apply sounds
#       installs chime.wav and crash.wav from the caller's home folder into
#       /usr/local/bin, where the launcher plays them from. Each has to be a
#       plain file the caller owns, a WAV, and no bigger than 4 MB. With no
#       chime.wav there, the installed chime is removed (no startup chime).
#
# Exit 0 when done, 2 for anything it won't do.
# ####################################

import os
import stat
import sys

sys.path.append("/usr/local/bin")   # night_schedule.py, after Python's own

import night_schedule  # noqa: E402

ZONEINFO = "/usr/share/zoneinfo"
LOCALTIME = "/etc/localtime"
TIMEZONE_FILE = "/etc/timezone"
SOUND_DIR = "/usr/local/bin"
SOUNDS = ("chime.wav", "crash.wav")
MOST_SOUND_BYTES = 4 * 1024 * 1024


class Refused(Exception):
    pass


def number(text, low, high, also=()):
    """A plain decimal number in range, or Refused."""
    if not (text.isascii() and text.isdigit() and len(text) <= 4):
        raise Refused(f"{text!r} is not a number")
    value = int(text)
    if not (low <= value <= high or value in also):
        raise Refused(f"{value} is out of range")
    return value


def replace_file(path, data, mode=0o644):
    """Writes the file whole, or not at all."""
    new = f"{path}.{os.getpid()}.new"
    fd = os.open(new, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            os.fchmod(f.fileno(), mode)
        os.replace(new, path)
    except BaseException:
        try:
            os.unlink(new)
        except OSError:
            pass
        raise


def set_zone(name, zone_tab=night_schedule.ZONE_TAB, zoneinfo=ZONEINFO,
             localtime=LOCALTIME, timezone_file=TIMEZONE_FILE):
    """What `timedatectl set-timezone` does, without the second or so it can
    take to start its service: /etc/localtime points at the zone, and
    /etc/timezone, on a system that still has one, names it."""
    names = night_schedule.zone_names(night_schedule.read_zone_tab((zone_tab,)))
    if name not in names:
        raise Refused(f"{name!r} is not a time zone in zone.tab")
    target = os.path.join(zoneinfo, name)
    if not os.path.isfile(target):
        raise Refused(f"no {target}")
    new = f"{localtime}.{os.getpid()}.new"
    try:
        os.unlink(new)      # left by a run that was cut short
    except FileNotFoundError:
        pass
    os.symlink(target, new)
    os.replace(new, localtime)
    if os.path.exists(timezone_file):
        replace_file(timezone_file, (name + "\n").encode())


def set_night(on, start, end, level, path=night_schedule.CONFIG):
    try:
        cfg = night_schedule.load_config(path)
    except (OSError, ValueError):
        cfg = night_schedule.NightConfig()     # a broken file is replaced
    cfg.on = bool(number(on, 0, 1))
    cfg.from_ = number(start, 0, 24 * 60 - 1, also=(night_schedule.SUNSET,))
    cfg.until = number(end, 0, 24 * 60 - 1, also=(night_schedule.SUNRISE,))
    cfg.level = number(level, 0, 100)
    replace_file(path, night_schedule.format_config(cfg).encode())


def read_sound(path, owner):
    """A sound's bytes, or None when there's no such file. Refused unless
    it's a plain file `owner` owns (never a link to someone else's), a WAV
    and small."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise Refused(f"can't open {path}: {e}")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != owner:
            raise Refused(f"{path} is not the caller's own file")
        if st.st_size > MOST_SOUND_BYTES:
            raise Refused(f"{path} is too big")
        data = b""
        while len(data) <= MOST_SOUND_BYTES:
            more = os.read(fd, MOST_SOUND_BYTES + 1 - len(data))
            if not more:
                break
            data += more
    finally:
        os.close(fd)
    if len(data) > MOST_SOUND_BYTES or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise Refused(f"{path} is not a WAV file")
    return data


def install_sounds(home, owner, sound_dir=SOUND_DIR):
    for name in SOUNDS:
        data = read_sound(os.path.join(home, name), owner)
        dest = os.path.join(sound_dir, name)
        if data is not None:
            replace_file(dest, data)
        elif name == "chime.wav":
            try:
                os.unlink(dest)
            except FileNotFoundError:
                pass


def caller():
    """The uid and home folder of whoever ran sudo."""
    import pwd
    try:
        uid = int(os.environ["SUDO_UID"])
        return uid, pwd.getpwuid(uid).pw_dir
    except (KeyError, ValueError):
        raise Refused("run this through sudo")


def main(argv):
    try:
        if len(argv) == 3 and argv[1] == "zone":
            set_zone(argv[2])
        elif len(argv) == 6 and argv[1] == "night":
            set_night(*argv[2:6])
        elif len(argv) == 2 and argv[1] == "sounds":
            uid, home = caller()
            install_sounds(home, uid)
        else:
            raise Refused("usage: mini-link-apply zone <Area/City> | "
                          "night <on> <from> <until> <level> | sounds")
    except (Refused, OSError) as e:
        print(f"mini-link-apply: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
