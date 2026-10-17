#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the press / double-press / hold logic in button_handler.py.

Run: python3 -m unittest test_button_handler
The lgpio module only exists on the Pi, so it is stubbed out here; nothing
under test touches GPIO.
"""

import sys
import types
import unittest

sys.modules.setdefault("lgpio", types.ModuleType("lgpio"))

import button_handler as bh  # noqa: E402

B1, B2 = bh.BTN1_PIN, bh.BTN2_PIN


class ButtonLogicTest(unittest.TestCase):

    def setUp(self):
        self.logic = bh.ButtonLogic()

    def test_btn1_fires_on_press(self):
        self.assertEqual(self.logic.press(B1, 0.0), [(B1, 'single')])
        self.assertEqual(self.logic.release(B1, 0.1), [])
        self.assertEqual(self.logic.tick(1.0), [])

    def test_quick_tap_still_restarts(self):
        self.assertEqual(self.logic.press(B2, 0.0), [])
        self.assertEqual(self.logic.release(B2, 0.1), [])
        self.assertEqual(self.logic.tick(0.4), [])
        self.assertEqual(self.logic.tick(0.6), [(B2, 'single')])
        self.assertEqual(self.logic.tick(2.0), [])

    def test_double_tap(self):
        self.logic.press(B2, 0.0)
        self.logic.release(B2, 0.1)
        self.assertEqual(self.logic.press(B2, 0.3), [(B2, 'double')])
        self.assertEqual(self.logic.release(B2, 0.4), [])
        self.assertEqual(self.logic.tick(0.9), [])
        self.assertEqual(self.logic.tick(12.0), [])

    def test_held_past_window_then_released_is_single(self):
        self.logic.press(B2, 0.0)
        self.assertEqual(self.logic.tick(0.6), [])
        self.assertEqual(self.logic.tick(2.0), [])
        self.assertEqual(self.logic.release(B2, 3.0), [(B2, 'single')])
        self.assertEqual(self.logic.tick(11.0), [])

    def test_hold_fires_once_and_no_tap(self):
        self.logic.press(B2, 0.0)
        self.assertEqual(self.logic.tick(9.9), [])
        self.assertEqual(self.logic.tick(10.0), [(B2, 'hold')])
        self.assertEqual(self.logic.tick(11.0), [])
        self.assertEqual(self.logic.release(B2, 12.0), [])
        self.assertEqual(self.logic.tick(13.0), [])

    def test_bounce_ignored(self):
        self.logic.press(B2, 0.0)
        self.assertEqual(self.logic.press(B2, 0.02), [])
        self.logic.release(B2, 0.1)
        self.assertEqual(self.logic.tick(0.6), [(B2, 'single')])

    def test_press_after_double_starts_fresh(self):
        self.logic.press(B2, 0.0)
        self.logic.release(B2, 0.1)
        self.logic.press(B2, 0.3)
        self.logic.release(B2, 0.4)
        self.assertEqual(self.logic.press(B2, 2.0), [])
        self.logic.release(B2, 2.1)
        self.assertEqual(self.logic.tick(2.6), [(B2, 'single')])


class CommandFor(unittest.TestCase):

    def test_tap_cancels_setup_when_requested(self):
        self.assertEqual(bh.command_for(B2, 'single', setup_requested=True),
                         ['/usr/local/bin/mac-setup', 'cancel'])

    def test_tap_restarts_otherwise(self):
        self.assertEqual(bh.command_for(B2, 'single', setup_requested=False),
                         bh.COMMANDS[B2])

    def test_hold_requests_setup(self):
        self.assertEqual(bh.command_for(B2, 'hold', setup_requested=False),
                         ['/usr/local/bin/mac-setup', 'request'])


if __name__ == '__main__':
    unittest.main()
