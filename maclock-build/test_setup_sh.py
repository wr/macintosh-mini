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
    # Top level, or nested in an if block: it closes at the indent it opened at.
    m = re.search(rf'^([ \t]*){name}\(\) \{{\n.*?^\1\}}\n', SETUP, re.S | re.M)
    if not m:
        raise AssertionError(f'{name}() not found in setup.sh')
    return m.group(0)


def one_liner(name):
    m = re.search(rf'^{name}\(\) \{{ .* \}}\n', SETUP, re.M)
    if not m:
        raise AssertionError(f'{name}() not found on one line in setup.sh')
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

    def test_restarts_for_a_check(self):
        # Whoever prepared it sees the setup screen before boxing it.
        self.assertEqual(self.HANDOFF.split()[-1], 'reboot')
        self.assertNotIn('poweroff', self.HANDOFF)

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


class AudioLevel(unittest.TestCase):
    """Chimes crackle through the breakout's amp at full scale, so the Pi's
    audio goes 4 dB down. On a fresh card the Headphones card only appears
    after the reboot, so the level goes into ALSA's saved state for then."""

    HDMI = ("state.vc4hdmi {\n\tcontrol.1 {\n\t\tiface CARD\n\t\tname 'HDMI Jack'\n"
            "\t\tvalue false\n\t}\n}\n")
    OLD_HEADPHONES = ("state.Headphones {\n\tcontrol.1 {\n\t\tiface MIXER\n"
                      "\t\tname 'PCM Playback Volume'\n\t\tvalue 0\n\t\tcomment {\n"
                      "\t\t\tdbvalue.0 0\n\t\t}\n\t}\n}\n")

    def run_fn(self, card, state=None):
        tmp = Path(tempfile.mkdtemp())
        calls = tmp / 'calls'
        for name, body in (('amixer', f'exit {0 if card else 1}'),
                           ('alsactl', f'echo "$*" >> {calls}'),
                           ('sudo', 'exec "$@"')):
            (tmp / name).write_text(f'#!/bin/sh\n{body}\n')
            (tmp / name).chmod(0o755)
        f = tmp / 'alsa' / 'asound.state'
        if state is not None:
            f.parent.mkdir()
            f.write_text(state)
        script = function('set_audio_level') + f'set_audio_level {f}; echo "rc=$?"\n'
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True,
                           text=True, env=dict(os.environ, PATH=f'{tmp}:/usr/bin:/bin'))
        self.assertIn('rc=0', r.stdout, r.stderr)
        return (calls.read_text().splitlines() if calls.exists() else [],
                f.read_text() if f.exists() else None)

    def headphones(self, state):
        return re.findall(r'^state\.Headphones \{\n.*?^\}\n', state, re.S | re.M)

    def test_card_present_saves_the_live_level(self):
        calls, state = self.run_fn(card=True)
        self.assertEqual(calls, ['store'])
        self.assertIsNone(state)

    def test_fresh_card_saves_minus_4_db_for_the_first_boot(self):
        calls, state = self.run_fn(card=False)
        self.assertEqual(calls, [])
        [block] = self.headphones(state)
        # The volume counts in 0.01 dB. Both of the card's controls, or
        # alsactl restore falls back to its init script first.
        self.assertIn("name 'PCM Playback Volume'\n\t\tvalue -400\n", block)
        self.assertIn("name 'PCM Playback Switch'\n\t\tvalue true\n", block)

    def test_other_cards_kept_and_an_old_level_replaced(self):
        _, state = self.run_fn(card=False, state=self.HDMI + self.OLD_HEADPHONES)
        self.assertTrue(state.startswith(self.HDMI), state)
        [block] = self.headphones(state)
        self.assertIn('value -400', block)
        self.assertNotIn('value 0', block)

    def test_old_level_replaced_before_other_cards(self):
        _, state = self.run_fn(card=False, state=self.OLD_HEADPHONES + self.HDMI)
        self.assertIn(self.HDMI, state)
        self.assertEqual(len(self.headphones(state)), 1)
        self.assertNotIn('value 0', state.replace(self.HDMI, ''))


class SpeakerAutoMute(unittest.TestCase):
    """Speaker auto-mute (the audio gate) is a choice, off unless asked for:
    it quiets rev 2026.09 boards and makes rev 2026.11 pop. Turning it off
    takes out what 1.10.0 put on every Mac."""

    FILES = ('etc/systemd/system/audio-gate.socket', 'etc/systemd/system/audio-gate.service',
             'usr/local/bin/audio_gate.py',
             'usr/local/lib/alsa-lib/libasound_module_pcm_audiogate.so', 'run/audio-gate.sock')

    def remove(self, asound=None, installed=True):
        tmp = Path(tempfile.mkdtemp())
        root, calls = tmp / 'root', tmp / 'calls'
        if installed:
            for f in self.FILES:
                (root / f).parent.mkdir(parents=True, exist_ok=True)
                (root / f).write_text('x')
        if asound is not None:
            (root / 'etc').mkdir(parents=True, exist_ok=True)
            (root / 'etc/asound.conf').write_text(asound)
        bin_ = tmp / 'bin'
        bin_.mkdir()
        # systemctl notes whether players still go through the plugin when
        # it's called, and fails like the real one when there's no unit.
        for name, body in (('sudo', 'exec "$@"'),
                           ('systemctl', f'echo "$* asound=$([ -e {root}/etc/asound.conf ] '
                                         f'&& echo y || echo n)" >> {calls}\n'
                                         f'[ "$1" = daemon-reload ] || [ "{int(installed)}" = 1 ]')):
            (bin_ / name).write_text(f'#!/bin/sh\n{body}\n')
            (bin_ / name).chmod(0o755)
        fn = function('remove_audio_gate')
        for d in ('/etc/', '/usr/local/', '/run/'):
            fn = fn.replace(d, f'{root}{d}')
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', fn + 'remove_audio_gate; echo "rc=$?"\n'],
                           capture_output=True, text=True,
                           env=dict(os.environ, PATH=f'{bin_}:/usr/bin:/bin'))
        self.assertIn('rc=0', r.stdout, r.stderr)
        return root, calls.read_text().splitlines()

    def test_stops_the_gate_before_players_skip_the_plugin(self):
        root, calls = self.remove(asound=(Path(__file__).resolve().parent / 'asound.conf').read_text())
        self.assertEqual(calls[0], 'disable --now audio-gate.socket audio-gate.service asound=y')
        self.assertFalse((root / 'etc/asound.conf').exists())
        for f in self.FILES:
            self.assertFalse((root / f).exists(), f)
        self.assertTrue(calls[-1].startswith('daemon-reload'))

    def test_keeps_an_owners_asound_conf(self):
        root, _ = self.remove(asound='pcm.!default { type hw; card 1 }\n')
        self.assertTrue((root / 'etc/asound.conf').exists())

    def test_nothing_to_remove_on_a_fresh_card(self):
        root, calls = self.remove(installed=False)
        self.assertEqual(calls[-1], 'daemon-reload asound=n')

    def pick(self, current, choice):
        """Run pick_audio_gate with wt_menu answering `choice` (None = Cancel)."""
        fake = ('wt_menu() { echo "default=$3" >&2; '
                + ('return 1; }\n' if choice is None else f'echo {choice}; }}\n'))
        script = (fake + function('pick_audio_gate') + 'AUDIO_GATE=""\n'
                  + f'if pick_audio_gate {current}; then echo "gate=$AUDIO_GATE"; '
                  + 'else echo cancelled; fi\n')
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True, text=True)
        return r.stdout.strip(), r.stderr.strip()

    def test_off_unless_this_mac_has_it(self):
        self.assertEqual(self.pick('""', 'No'), ('gate=0', 'default=No'))
        self.assertEqual(self.pick(0, 'Yes'), ('gate=1', 'default=No'))
        self.assertEqual(self.pick(1, 'No'), ('gate=0', 'default=Yes'))

    def test_cancel_leaves_the_choice_unmade(self):
        self.assertEqual(self.pick(0, None)[0], 'cancelled')

    def test_update_keeps_the_installed_choice_and_records_it(self):
        self.assertIn('[[ -z $AUDIO_GATE ]] && AUDIO_GATE=${INSTALLED_AUDIO_GATE:-0}', SETUP)
        self.assertIn('AUDIO_GATE=%s', function('record_install'))
        # 1.10.0 put the gate on every Mac and recorded nothing
        self.assertIn('systemctl is-enabled --quiet audio-gate.service', SETUP)


class WhatsNew(unittest.TestCase):
    """The update menu lists the changelog entries since the installed version."""

    MD = ("# Changelog\n\n## [1.11.0] - 2026-11-01\n- later\n\n"
          "## [1.10.0] - 2026-10-27\n- one\n- two\n\n"
          "## [1.9.1] - 2026-10-22\n- three\n\n## [1.9.0] - 2026-10-21\n- four\n")

    def test_versions_since_the_installed_one_with_a_blank_line_between(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'CHANGELOG.md').write_text(self.MD)
        (tmp / 'curl').write_text(f'#!/bin/sh\ncat {tmp}/CHANGELOG.md\n')
        (tmp / 'curl').chmod(0o755)
        script = function('changelog_since') + 'VERSION=1.10.0 REPO_RAW=x\nchangelog_since 1.9.0\n'
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True,
                           text=True, env=dict(os.environ, PATH=f'{tmp}:/usr/bin:/bin'))
        self.assertEqual(r.stdout, 'New in 1.10.0:\n- one\n- two\n\nNew in 1.9.1:\n- three\n',
                         r.stderr)


class Hotspot(unittest.TestCase):

    def test_no_dhcp_option_114(self):
        # RFC 8910 wants a captive-portal API (JSON over HTTPS) there, not a page;
        # phones find the page through their usual checks.
        self.assertNotIn('dhcp-option=114', SETUP)


class NightDimming(unittest.TestCase):
    """One schedule for both builds: from, until (clock times, or sunset and
    sunrise) and how dim. The installer keeps what's set and moves a file
    from before 1.12.0."""

    CLOCK = re.search(r"^NIGHT_CLOCK=.*\n", SETUP, re.M).group(0)
    OLD = ('# Night dimming for the maclock backlight.\nNIGHT_DIM=%s\nLAT=%s\nLON=%s\n'
           'NIGHT_FACTOR=0.5\nNIGHT_OFF_AT=%s\n')

    def script(self, conf, body):
        tmp = Path(tempfile.mkdtemp())
        if conf is not None:
            (tmp / 'conf').write_text(conf)
        (tmp / 'sudo').write_text('#!/bin/sh\nexec "$@"\n')
        (tmp / 'sudo').chmod(0o755)
        script = (self.CLOCK + f'NIGHT_CONF={tmp}/conf\n'
                  + 'NIGHT_DIM="" NIGHT_FROM="" NIGHT_UNTIL="" NIGHT_LEVEL="" TIMEZONE=""\n'
                  + one_liner('conf_get')
                  + ''.join(function(f) for f in ('read_night_conf', 'night_summary',
                                                  'write_night_conf', 'pick_night'))
                  + body)
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True,
                           text=True, env=dict(os.environ, PATH=f'{tmp}:/usr/bin:/bin'))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout, tmp / 'conf'

    def current(self, conf):
        out, _ = self.script(conf, 'read_night_conf\n'
                             'echo "$CUR_NIGHT_DIM $CUR_NIGHT_FROM $CUR_NIGHT_UNTIL $CUR_NIGHT_LEVEL"\n')
        return out.strip()

    def written(self, conf, chosen=''):
        """What the install leaves in the file, as night_schedule reads it."""
        import night_schedule
        _, path = self.script(conf, chosen + '\nwrite_night_conf\n')
        return night_schedule.parse_config(path.read_text()), path.read_text()

    def test_no_file_is_off_with_the_defaults(self):
        self.assertEqual(self.current(None), '0 22:00 07:00 20')

    def test_on_before_1_12_becomes_sunset_to_sunrise_at_50(self):
        for off_at in ('22:00', '01:00', ''):
            self.assertEqual(self.current(self.OLD % (1, '', '', off_at)), '1 sunset sunrise 50')

    def test_off_before_1_12_stays_off(self):
        self.assertEqual(self.current(self.OLD % (0, '', '', '22:00')), '0 22:00 07:00 20')

    def test_new_settings_are_kept(self):
        self.assertEqual(self.current('NIGHT_DIM=1\nNIGHT_FROM=21:30\nNIGHT_UNTIL=sunrise\n'
                                      'NIGHT_LEVEL=0\n'), '1 21:30 sunrise 0')

    def test_a_mistyped_setting_means_off_as_it_does_for_the_dial_script(self):
        import night_schedule
        for bad in ('NIGHT_FROM=10pm', 'NIGHT_UNTIL=sunset', 'NIGHT_LEVEL=101'):
            conf = 'NIGHT_DIM=yes\n' + bad + '\n'
            self.assertEqual(self.current(conf), '0 22:00 07:00 20', bad)
            with self.assertRaises(ValueError):
                night_schedule.parse_config(conf)
        self.assertEqual(self.current('NIGHT_DIM=yes\nNIGHT_LEVEL=35\n'), '1 22:00 07:00 35')

    def test_update_moves_an_old_file_and_keeps_a_hand_set_place(self):
        import night_schedule
        cfg, text = self.written(self.OLD % (1, '51.5', '-0.13', '23:00'))
        self.assertEqual(cfg, night_schedule.NightConfig(True, night_schedule.SUNSET,
                                                         night_schedule.SUNRISE, 50, 51.5, -0.13))
        self.assertNotIn('NIGHT_FACTOR', text)
        self.assertNotIn('NIGHT_OFF_AT', text)

    def test_update_with_no_file_writes_dimming_off(self):
        import night_schedule
        self.assertEqual(self.written(None)[0], night_schedule.NightConfig())

    def test_what_is_chosen_wins_over_what_was_set(self):
        import night_schedule
        cfg, _ = self.written('NIGHT_DIM=0\nNIGHT_FROM=21:30\nNIGHT_UNTIL=06:00\nNIGHT_LEVEL=35\n',
                              'NIGHT_DIM=1 NIGHT_LEVEL=0')
        self.assertEqual(cfg, night_schedule.NightConfig(True, 21 * 60 + 30, 6 * 60, 0))

    def test_writes_the_file_as_night_schedule_does(self):
        import night_schedule
        for cfg in (night_schedule.NightConfig(),
                    night_schedule.NightConfig(True, night_schedule.SUNSET, night_schedule.SUNRISE, 50),
                    night_schedule.NightConfig(True, 60, 23 * 60 + 59, 0, 40.7, -74)):
            self.assertEqual(self.written(night_schedule.format_config(cfg))[1],
                             night_schedule.format_config(cfg))

    def test_summary(self):
        out, _ = self.script(None, 'night_summary 0 22:00 07:00 20; echo\n'
                             'night_summary 1 22:00 07:00 20; echo\n'
                             'night_summary 1 sunset sunrise 50; echo\n'
                             'night_summary 1 sunset 06:30 0; echo\n')
        self.assertEqual(out.splitlines(), ['Off', '22:00 to 07:00, dimmed to 20%',
                                            'Sunset to sunrise, dimmed to 50%',
                                            'Sunset to 06:30, screen off'])

    def pick(self, conf, answers, flags=''):
        """Run pick_night with wt_menu giving each answer in turn (None = Cancel).
        Returns what it chose and the entry each menu started on."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'answers').write_text(''.join(f'{a}\n' for a in answers if a is not None))
        fake = (f'wt_menu() {{ echo "default=$3" >&2; n=$(cat {tmp}/n 2>/dev/null || echo 0); '
                f'n=$((n+1)); echo $n > {tmp}/n; a=$(sed -n "${{n}}p" {tmp}/answers); '
                '[[ -n $a ]] || return 1; echo "$a"; }\n'
                'current_timezone() { echo America/New_York; }\n'
                'pick_timezone() { TIMEZONE=Asia/Tokyo; }\n')
        out, _ = self.script(conf, fake + 'read_night_conf\n' + flags + '\n'
                             'if pick_night; then echo "$NIGHT_DIM $NIGHT_FROM $NIGHT_UNTIL '
                             '$NIGHT_LEVEL $TIMEZONE"; else echo cancelled; fi\n')
        return out.strip()

    def test_pick_the_defaults(self):
        self.assertEqual(self.pick(None, ['10 PM to 7 AM', 'Dim']), '1 22:00 07:00 20')

    def test_pick_sunset_to_sunrise_and_off(self):
        self.assertEqual(self.pick(None, ['Sunset to sunrise', 'Off']), '1 sunset sunrise 0')

    def test_pick_no(self):
        self.assertEqual(self.pick('NIGHT_DIM=1\nNIGHT_FROM=sunset\n', ['No']), '0')

    def test_pick_keeps_hand_set_times_and_level(self):
        conf = 'NIGHT_DIM=1\nNIGHT_FROM=21:30\nNIGHT_UNTIL=06:00\nNIGHT_LEVEL=35\n'
        self.assertEqual(self.pick(conf, ['Keep 21:30 to 06:00', 'Keep 35%']), '1 21:30 06:00 35')

    def test_update_timezone_comes_back_to_the_question(self):
        self.assertEqual(self.pick(None, ['Update timezone', 'Sunset to sunrise', 'Half']),
                         '1 sunset sunrise 50 Asia/Tokyo')

    def test_cancel_changes_nothing(self):
        self.assertEqual(self.pick(None, [None]), 'cancelled')
        self.assertEqual(self.pick(None, ['10 PM to 7 AM', None]), 'cancelled')

    def flags(self, *args):
        a = SETUP.index('NIGHT_CLOCK=')
        b = SETUP.index('\n', SETUP.index("--night-level takes 0 to 100")) + 1
        script = ('die() { echo "$*"; exit 1; }\nNIGHT_FROM=$1 NIGHT_UNTIL=$2 NIGHT_LEVEL=$3\n'
                  + SETUP[a:b] + 'echo ok\n')
        return subprocess.run(['bash', '-euo', 'pipefail', '-c', script, 'x', *args],
                              capture_output=True, text=True).stdout.strip()

    def test_flags_take_clock_times_or_the_sun(self):
        for good in (('', '', ''), ('22:00', '07:00', '20'), ('sunset', 'sunrise', '0'),
                     ('00:00', '23:59', '100')):
            self.assertEqual(self.flags(*good), 'ok', good)
        for bad in (('sunrise', '', ''), ('24:00', '', ''), ('7:00', '', ''), ('never', '', ''),
                    ('', 'sunset', ''), ('', '07:60', ''), ('', '', '101'), ('', '', '-1'),
                    ('', '', '050'), ('', '', 'off')):
            self.assertIn('takes', self.flags(*bad), bad)

    def test_the_old_flag_says_what_replaced_it(self):
        self.assertRegex(SETUP, r'--night-off\)\s+die ".*--night-from, --night-until and --night-level')
        for flag in ('--night-from)', '--night-until)', '--night-level)'):
            self.assertIn(flag, SETUP)

    def test_asked_on_a_fresh_install_and_offered_in_the_settings_editor(self):
        self.assertIn('pick_night || die "Cancelled"', SETUP)
        editor = function('configure_existing')
        self.assertIn('"Night dimming:") pick_night', editor)
        # The editor is used before the main prompts, so its helpers come first
        self.assertLess(SETUP.index('pick_night() {'), SETUP.index('configure_existing() {'))

    def test_settings_are_written_on_every_install_with_the_schedule_code(self):
        helpers = function('install_gpio_helpers')
        self.assertIn('night_schedule.py', helpers)
        self.assertLess(helpers.index('write_night_conf'), helpers.index('systemctl restart'))
        self.assertNotIn('[[ -n $NIGHT_DIM ]] || return 0', function('write_night_conf'))


class MiniLink(unittest.TestCase):
    """The Mac's modem port runs mini-link, which answers the Mini's Mac OS
    software."""

    PREF = '|/usr/local/bin/mini-link'

    def set_pref(self, before):
        tmp = Path(tempfile.mkdtemp())
        prefs = tmp / 'prefs'
        if before is not None:
            prefs.write_text(before)
        pref = re.search(r'^MINI_LINK_PREF=.*\n', SETUP, re.M).group(0)
        script = (pref + one_liner('pref_get') + function('pref_set') + function('set_serial_pref')
                  + f'set_serial_pref {prefs}\n')
        r = subprocess.run(['bash', '-euo', 'pipefail', '-c', script], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return prefs.read_text() if prefs.exists() else None

    def test_the_pref_is_the_one_the_contract_names(self):
        self.assertIn(f'MINI_LINK_PREF="{self.PREF}"', SETUP)

    def test_new_installs_get_it_for_both_emulators(self):
        for fn in ('write_prefs', 'write_basilisk_prefs'):
            self.assertIn('\nseriala $MINI_LINK_PREF\n', function(fn), fn)

    def test_an_update_adds_it(self):
        self.assertEqual(self.set_pref('rom ROM\nether slirp\n'),
                         f'rom ROM\nether slirp\nseriala {self.PREF}\n')

    def test_an_update_replaces_the_emulators_stock_device_and_leaves_ours(self):
        if subprocess.run(['sed', '--version'], capture_output=True).returncode:
            self.skipTest('pref_set needs GNU sed, as on the Pi')
        want = f'rom ROM\nseriala {self.PREF}\nether slirp\n'
        self.assertEqual(self.set_pref('rom ROM\nseriala /dev/ttyS0\nether slirp\n'), want)
        self.assertEqual(self.set_pref(want), want)

    def test_no_prefs_file_is_not_made(self):
        self.assertIsNone(self.set_pref(None))

    def test_an_owners_own_serial_device_is_kept(self):
        before = 'rom ROM\nseriala /dev/ttyUSB0\n'
        self.assertEqual(self.set_pref(before), before)

    def test_update_covers_both_emulators_prefs(self):
        fn = function('install_mini_link')
        for prefs in ('.basilisk_ii_prefs', '.sheepshaver_prefs'):
            self.assertIn(f'set_serial_pref "$HOME/{prefs}"', fn)

    def test_installs_the_program_and_what_it_needs(self):
        fn = function('install_mini_link')
        for line in ('sudo install -m644 /tmp/night_schedule.py /usr/local/bin/night_schedule.py',
                     'sudo install -m755 /tmp/mini_link.py /usr/local/bin/mini-link',
                     'sudo install -D -m755 /tmp/mini_link_apply.py /usr/local/sbin/mini-link-apply'):
            self.assertIn(line, fn)
        here = Path(__file__).resolve().parent
        for f in ('night_schedule.py', 'mini_link.py', 'mini_link_apply.py'):
            self.assertTrue((here / f).is_file(), f)

    def test_root_is_only_for_the_one_program(self):
        fn = function('install_mini_link')
        self.assertIn("printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/mini-link-apply\\n' "
                      '"$USER" > "$rule" || return $?', fn)
        self.assertEqual(fn.count('NOPASSWD'), 1)
        self.assertLess(fn.index('visudo -c -f "$rule"'), fn.index('/etc/sudoers.d/020-mini-link'))
        # Never a fixed name in /tmp, which someone else could have put there
        self.assertIn('rule=$(mktemp) || return $?', fn)
        self.assertNotIn('/tmp/020', fn)
        # The path the rule names is the one mini-link runs
        import mini_link
        self.assertEqual(mini_link.APPLY, '/usr/local/sbin/mini-link-apply')

    def test_installed_with_either_emulator_and_counted(self):
        self.assertRegex(SETUP, r'if \[\[ \$INSTALL_SHEEPSHAVER -eq 1 \|\| \$INSTALL_BASILISK -eq 1 \]\]; then\n'
                                r'  install_mini_link\(\) \{')
        self.assertIn('TOTAL_STEPS=$((TOTAL_STEPS+2))   # Wi-Fi setup, mini-link', SETUP)

    def test_the_version_mini_link_reports_is_recorded(self):
        import mini_link
        self.assertIn("printf 'VERSION=%s\\n", function('record_install'))
        self.assertEqual(mini_link.INSTALL_STATE, re.search(r'^INSTALL_STATE=(\S+)', SETUP, re.M).group(1))

    def test_a_chime_named_by_flag_is_recorded_by_its_tag(self):
        self.assertIn('[[ "$filename" == "$CHIME_NAME" ]] && CHIME_TAG=$tag', SETUP)


class Changelog(unittest.TestCase):

    def test_this_version_has_an_entry(self):
        version = re.search(r'^VERSION="([0-9.]+)"', SETUP, re.M).group(1)
        md = (Path(__file__).resolve().parent.parent / 'CHANGELOG.md').read_text()
        self.assertRegex(md, rf'(?m)^## \[{re.escape(version)}\] - \d{{4}}-\d\d-\d\d\n- ')


if __name__ == '__main__':
    unittest.main()
