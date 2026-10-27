#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for audio_gate.py, and for the names it shares with the plugin, the
systemd units and asound.conf.

Run: python3 -m unittest test_audio_gate
Nothing here touches GPIO or ALSA.
"""

import re
import socket
import tempfile
import unittest
from pathlib import Path

import audio_gate as ag

HERE = Path(__file__).resolve().parent


class GateTest(unittest.TestCase):

    def test_starts_connected_and_lets_go_after_the_hold(self):
        gate = ag.Gate(0.0, hold_s=3.0)
        self.assertTrue(gate.connected)
        self.assertIsNone(gate.tick(2.9))
        self.assertEqual(gate.tick(3.0), 'let go')
        self.assertIsNone(gate.tick(10.0))   # once

    def test_sound_connects_once(self):
        gate = ag.Gate(0.0, hold_s=3.0)
        gate.tick(5.0)
        self.assertEqual(gate.heard(6.0), 'connect')
        self.assertIsNone(gate.heard(6.1))

    def test_each_sound_restarts_the_hold(self):
        gate = ag.Gate(0.0, hold_s=3.0)
        self.assertIsNone(gate.heard(2.0))
        self.assertIsNone(gate.tick(4.5))
        self.assertEqual(gate.tick(5.0), 'let go')


class DrainTest(unittest.TestCase):

    def test_reads_everything_queued(self):
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        self.assertFalse(ag.drain(a))
        for _ in range(5):
            b.send(b'!')
        self.assertTrue(ag.drain(a))
        self.assertFalse(ag.drain(a))


class RoutedTest(unittest.TestCase):

    def test_only_with_the_plugin_in_asound_conf(self):
        d = Path(tempfile.mkdtemp())
        self.assertFalse(ag.routed(d / 'missing'))
        (d / 'own').write_text('pcm.!default { type hw; card 1 }\n')
        self.assertFalse(ag.routed(d / 'own'))
        self.assertTrue(ag.routed(HERE / 'asound.conf'))


class SharedNamesTest(unittest.TestCase):
    """The plugin, the gate, the units and asound.conf name the same things."""

    def test_socket_path(self):
        plugin = (HERE / 'audio_gate_plugin.c').read_text()
        unit = (HERE / 'audio-gate.socket').read_text()
        self.assertIn(f'"{ag.SOCKET}"', plugin)
        self.assertIn(f'ListenDatagram={ag.SOCKET}\n', unit)

    def test_plugin_name_and_library(self):
        conf = (HERE / 'asound.conf').read_text()
        plugin = (HERE / 'audio_gate_plugin.c').read_text()
        setup = (HERE.parent / 'setup.sh').read_text()
        lib = re.search(r'lib "(/[^"]+/(libasound_module_pcm_(\w+)\.so))"', conf)
        self.assertIsNotNone(lib)
        self.assertIn('type audiogate', conf)
        self.assertEqual(lib.group(3), 'audiogate')
        self.assertIn('SND_PCM_PLUGIN_SYMBOL(audiogate)', plugin)
        self.assertIn(lib.group(1), setup)

    def test_pin(self):
        service = (HERE / 'audio-gate.service').read_text()
        self.assertIn(f'pinctrl set {ag.PIN} {" ".join(ag.CONNECT)}\n', service)


if __name__ == '__main__':
    unittest.main()
