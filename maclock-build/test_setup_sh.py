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


class Hotspot(unittest.TestCase):

    def test_no_dhcp_option_114(self):
        # RFC 8910 wants a captive-portal API (JSON over HTTPS) there, not a page;
        # phones find the page through their usual checks.
        self.assertNotIn('dhcp-option=114', SETUP)


if __name__ == '__main__':
    unittest.main()
