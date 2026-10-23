#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for pieces of ../setup.sh that can run off the Pi.

Run: python3 -m unittest test_setup_sh
Functions and heredocs are cut out of setup.sh and run with bash, with fake
commands on PATH where they'd touch the system.
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SETUP = (Path(__file__).resolve().parent.parent / 'setup.sh').read_text()


def function(name):
    m = re.search(rf'^{name}\(\) \{{\n.*?^\}}\n', SETUP, re.S | re.M)
    if not m:
        raise AssertionError(f'{name}() not found in setup.sh')
    return m.group(0)


def heredoc(tag, first_line):
    for m in re.finditer(rf"<<'{tag}'\n(.*?)\n{tag}\n", SETUP, re.S):
        if m.group(1).startswith(first_line):
            return m.group(1) + '\n'
    raise AssertionError(f'heredoc {tag} starting {first_line!r} not found')


class InstalledRomPath(unittest.TestCase):

    def run_fn(self, home, sheepshaver=0):
        script = (function('installed_rom_path')
                  + f'INSTALL_SHEEPSHAVER={sheepshaver}\nHOME={home}\n'
                  + 'installed_rom_path; echo; echo after\n')
        return subprocess.run(['bash', '-euo', 'pipefail', '-c', script],
                              capture_output=True, text=True)

    def test_survives_pipefail_with_one_prefs_file(self):
        home = tempfile.mkdtemp()
        Path(home, '.basilisk_ii_prefs').write_text(f'disk {home}/d.hda\nrom {home}/ROM\n')
        r = self.run_fn(home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, f'{home}/ROM\nafter\n')

    def test_relative_rom_is_resolved(self):
        home = tempfile.mkdtemp()
        Path(home, '.sheepshaver_prefs').write_text('rom ROM\n')
        r = self.run_fn(home, sheepshaver=1)
        self.assertEqual(r.stdout, f'{home}/ROM\nafter\n')

    def test_no_prefs_prints_nothing(self):
        r = self.run_fn(tempfile.mkdtemp())
        self.assertEqual((r.returncode, r.stdout), (0, '\nafter\n'))


class NeededWrapper(unittest.TestCase):
    """The `mac-setup needed` fast path the launcher runs on every start."""

    def run_needed(self, saved='', active='', fail=False):
        tmp = Path(tempfile.mkdtemp())
        nmcli = tmp / 'nmcli'
        nmcli.write_text('#!/bin/sh\n'
                         f'[ "{int(fail)}" = 1 ] && exit 8\n'
                         'case "$*" in *--active*) printf "%s" "$ACTIVE" ;; *) printf "%s" "$SAVED" ;; esac\n')
        nmcli.chmod(0o755)
        wrapper = tmp / 'mac-setup'
        wrapper.write_text(heredoc('WRAPPER', '#!/bin/sh\n# Wi-Fi setup from a phone'))
        wrapper.chmod(0o755)
        env = dict(os.environ, PATH=f'{tmp}:/usr/bin:/bin', SAVED=saved, ACTIVE=active)
        return subprocess.run([str(wrapper), 'needed'], env=env, capture_output=True).returncode

    def test_saved_wifi_not_needed(self):
        self.assertEqual(self.run_needed(saved='Home:802-11-wireless\n'), 1)

    def test_no_wifi_needed(self):
        self.assertEqual(self.run_needed(saved='Wired connection 1:802-3-ethernet\n'), 0)

    def test_hotspot_profile_does_not_count(self):
        self.assertEqual(self.run_needed(saved='mac-setup-hotspot:802-11-wireless\n'), 0)

    def test_wired_connection_not_needed(self):
        self.assertEqual(self.run_needed(saved='Wired connection 1:802-3-ethernet\n',
                                         active='802-3-ethernet\n'), 1)

    def test_nmcli_failing_not_needed(self):
        self.assertEqual(self.run_needed(fail=True), 1)


class Handoff(unittest.TestCase):
    """--hotspot-setup must leave nothing of the person who prepared the card."""

    HANDOFF = heredoc('HANDOFF', '#!/bin/bash')

    def test_erases_traces(self):
        for needle in ('rm -rf "$home/.ssh"',
                       '/root/.ssh/authorized_keys',
                       '/var/lib/NetworkManager/seen-bssids',
                       '/var/lib/NetworkManager/timestamps',
                       '/var/lib/NetworkManager/*.lease',
                       '/var/log/cloud-init',
                       'journalctl --rotate',
                       'pkill -KILL -u "$user"',
                       "s/^LAT=.*/LAT=/",
                       '-size 1048576c',
                       # Imager / cloud-init seed files, and any backup copies
                       # of them (user-data.bak holds the login).
                       '/boot/firmware/user-data*',
                       '/boot/firmware/network-config*'):
            self.assertIn(needle, self.HANDOFF)

    def test_history_removed_after_sessions_killed(self):
        self.assertLess(self.HANDOFF.index('pkill -KILL -u "$user"'),
                        self.HANDOFF.rindex('.bash_history'))

    def test_rom_path_read_safely(self):
        self.assertIn('ho_rom=$(installed_rom_path)', SETUP)

    def test_handoff_is_valid_bash(self):
        r = subprocess.run(['bash', '-n'], input=self.HANDOFF, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class FirstBoot(unittest.TestCase):
    """A card's first start runs apt in the background (cloud-init installs
    Imager's avahi-daemon), so the installer waits before its own apt steps."""

    def run_fn(self, call, status=None, wait_rc=0):
        tmp = Path(tempfile.mkdtemp())
        calls = tmp / 'calls'
        if status is not None:
            fake = tmp / 'cloud-init'
            fake.write_text('#!/bin/sh\n'
                            f'echo "$*" >> {calls}\n'
                            f'case "$*" in *--wait*) exit {wait_rc} ;; esac\n'
                            f'echo "status: {status}"\n')
            fake.chmod(0o755)
        script = (function('first_boot_running') + function('wait_for_first_boot')
                  + f'{call}; echo "rc=$?"\n')
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True,
                           text=True, env=dict(os.environ, PATH=f'{tmp}:/usr/bin:/bin'))
        return r, calls.read_text().splitlines() if calls.exists() else []

    def test_running(self):
        r, _ = self.run_fn('first_boot_running || echo "rc=1"; true', status='running')
        self.assertNotIn('rc=1', r.stdout)

    def test_done_disabled_or_absent_is_not_running(self):
        for status in ('done', 'disabled', None):
            r, _ = self.run_fn('first_boot_running && echo yes; true', status=status)
            self.assertNotIn('yes', r.stdout, status)

    def test_waits_while_running(self):
        r, calls = self.run_fn('wait_for_first_boot', status='running')
        self.assertIn('rc=0', r.stdout, r.stderr)
        self.assertIn('status --wait', calls)

    def test_no_wait_once_done(self):
        _, calls = self.run_fn('wait_for_first_boot', status='done')
        self.assertNotIn('status --wait', calls)

    def test_cloud_init_error_does_not_stop_the_install(self):
        r, _ = self.run_fn('wait_for_first_boot', status='running', wait_rc=1)
        self.assertIn('rc=0', r.stdout, r.stderr)

    def test_waits_before_apt(self):
        self.assertLess(SETUP.rindex(' wait_for_first_boot\n'),
                        SETUP.index('run "Updating apt index"'))

    def test_installs_wait_for_dpkg_lock(self):
        # Anything else holding dpkg (apt-daily, another session) gets waited
        # out too. apt's lock timeout covers installs, not `apt-get update`.
        installs = re.findall(r'apt-get\b[^\n]*\binstall\b[^\n]*', SETUP)
        self.assertTrue(installs)
        for line in installs:
            self.assertIn('DPkg::Lock::Timeout', line, line)


class Theme(unittest.TestCase):
    """whiptail's buttons are newt's compact ones (<Ok>): newt draws them in
    `compactbutton`, and the focused one in `button`, not `actbutton`."""

    def colors(self):
        m = re.search(r'^NEWT_THEME=\((.*?)^\)', SETUP, re.S | re.M)
        return dict(line.split('=') for line in m.group(1).split())

    def test_focused_button_inverts(self):
        c = self.colors()
        fg, bg = c['compactbutton'].split(',')
        self.assertEqual(c['button'], f'{bg},{fg}')


class PiCheck(unittest.TestCase):
    """Run anywhere but a Pi (a Mac in the wrong terminal tab), the installer
    would change that machine: it stops first unless told otherwise."""

    def run_fn(self, kernel, model=None):
        tmp = Path(tempfile.mkdtemp())
        uname = tmp / 'uname'
        uname.write_text(f'#!/bin/sh\necho {kernel}\n')
        uname.chmod(0o755)
        model_file = tmp / 'model'
        if model is not None:
            model_file.write_bytes(model.encode() + b'\0')
        script = function('pi_model') + f'pi_model {model_file} && echo " yes" || echo no\n'
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True,
                           text=True, env=dict(os.environ, PATH=f'{tmp}:/usr/bin:/bin'))
        return r.stdout.strip()

    def test_pi(self):
        self.assertEqual(self.run_fn('Linux', 'Raspberry Pi Zero 2 W Rev 1.0'),
                         'Raspberry Pi Zero 2 W Rev 1.0 yes')

    def test_mac(self):
        self.assertEqual(self.run_fn('Darwin', 'Raspberry Pi Zero 2 W Rev 1.0'), 'no')

    def test_linux_without_a_model(self):
        self.assertEqual(self.run_fn('Linux'), 'no')

    def test_other_board(self):
        self.assertEqual(self.run_fn('Linux', 'Radxa ZERO 3W'), 'no')

    def test_checked_before_anything_changes(self):
        check = SETUP.index('[[ $SKIP_PI_CHECK -eq 1 ]] || pi_model')
        self.assertLess(check, SETUP.index('\nensure_sudo\n'))
        self.assertLess(check, SETUP.index('check_basilisk_assets\n'))
        self.assertIn('--skip-pi-check) SKIP_PI_CHECK=1', SETUP)


class Hotspot(unittest.TestCase):

    def test_no_dhcp_option_114(self):
        # RFC 8910 wants a captive-portal API (JSON over HTTPS) there, not a page;
        # phones find the page through their usual checks.
        self.assertNotIn('dhcp-option=114', SETUP)


if __name__ == '__main__':
    unittest.main()
