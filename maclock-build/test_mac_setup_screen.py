#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the setup screen renderer in mac_setup_screen.py.

Run: python3 -m unittest test_mac_setup_screen
Uses tiny made-up fonts and a temp file in place of /dev/fb0.
"""

import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import mac_setup_screen as scr


def psf1(height=16, glyphs=None):
    """PSF1: 256 glyphs, 8 px wide. glyphs: {index: [row bytes]}"""
    data = bytearray(b'\x36\x04\x00' + bytes([height]))
    for i in range(256):
        rows = (glyphs or {}).get(i, [0] * height)
        data += bytes(rows)
    return bytes(data)


def psf2(width=10, height=4, glyphs=None, unicode=None):
    """PSF2 with optional unicode table {glyph index: 'chars'}."""
    rowbytes = (width + 7) // 8
    charsize = rowbytes * height
    n = 8
    flags = 1 if unicode else 0
    data = bytearray(b'\x72\xb5\x4a\x86')
    data += struct.pack('<7I', 0, 32, flags, n, charsize, height, width)
    for i in range(n):
        data += bytes((glyphs or {}).get(i, [0] * charsize))
    if unicode:
        for i in range(n):
            data += unicode.get(i, '').encode() + b'\xff'
    return bytes(data)


def full_font(width=8, height=16):
    # Every printable ASCII glyph is a solid block, so text shows up as ink.
    return scr.Font(width, height, {chr(c): [(1 << width) - 1] * height for c in range(32, 127)})


class Qr(unittest.TestCase):

    def test_qr_matrix_parses_ascii(self):
        def fake_run(cmd, **kw):
            self.assertEqual(cmd[0], 'qrencode')
            return subprocess.CompletedProcess(cmd, 0, stdout='##  ##\n  ##  \n')
        self.assertEqual(scr.qr_matrix('x', run=fake_run),
                         [[True, False, True], [False, True, False]])


class Fonts(unittest.TestCase):

    def write(self, data, suffix='.psf'):
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.write(data)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_load_psf_v1(self):
        rows = [0x18] * 16
        font = scr.load_psf(self.write(psf1(glyphs={ord('A'): rows})))
        self.assertEqual((font.width, font.height), (8, 16))
        self.assertEqual(font.glyph('A'), rows)

    def test_load_psf_v2_with_unicode_table(self):
        g = [0xFF, 0xC0, 0x80, 0x00, 0x80, 0x40, 0x00, 0x00]   # 10 px wide: 2 bytes a row
        font = scr.load_psf(self.write(psf2(glyphs={5: g}, unicode={5: 'A'})))
        self.assertEqual((font.width, font.height), (10, 4))
        self.assertEqual(font.glyph('A'), [0x3FF, 0x200, 0x201, 0x000])

    def test_missing_glyph_is_blank(self):
        font = scr.load_psf(self.write(psf1()))
        self.assertEqual(font.glyph('☃'), [0] * 16)


class Render(unittest.TestCase):

    def qr(self, text):
        return [[(x + y) % 2 == 0 for x in range(25)] for y in range(25)]

    def test_render_size_and_qr_left(self):
        screen = {'title': 'Set up Wi-Fi', 'lines': ['Join', 'Macintosh Mini 4E2A'], 'qr': 'WIFI:...'}
        c = scr.render(screen, full_font(), qr_matrix=self.qr)
        self.assertEqual((c.width, c.height), (640, 480))
        left = any(c.get(x, y) for x in range(24, 320) for y in range(100, 380))
        self.assertTrue(left)
        margin = any(c.get(x, y) for x in range(630, 640) for y in range(480))
        self.assertFalse(margin)

    def test_render_without_qr_centres_text(self):
        screen = {'title': 'Connecting', 'lines': ['Joining Home.'], 'qr': None}
        c = scr.render(screen, full_font(), qr_matrix=self.qr)
        xs = [x for y in range(c.height) for x in range(c.width) if c.get(x, y)]
        left, right = min(xs), c.width - 1 - max(xs)
        self.assertLessEqual(abs(left - right), 16)

    def test_long_line_wraps_inside_canvas(self):
        screen = {'title': 'T', 'lines': ['word ' * 60], 'qr': 'x'}
        c = scr.render(screen, full_font(), qr_matrix=self.qr)
        margin = any(c.get(x, y) for x in range(630, 640) for y in range(480))
        self.assertFalse(margin)


class Blit(unittest.TestCase):

    def test_blit_rotation(self):
        tmp = Path(tempfile.mkdtemp())
        fbdir = tmp / 'fb0'
        fbdir.mkdir()
        (fbdir / 'virtual_size').write_text('2,4\n')
        (fbdir / 'stride').write_text('4\n')
        (fbdir / 'bits_per_pixel').write_text('16\n')
        rotate = tmp / 'rotate'
        rotate.write_text('1\n')
        dev = tmp / 'dev'
        dev.write_bytes(b'')
        c = scr.Canvas(4, 2)
        c.set(1, 0)
        scr.blit(c, fb_dir=str(fbdir), dev=str(dev), rotate_path=str(rotate))
        data = dev.read_bytes()
        self.assertEqual(len(data), 16)
        px = [int.from_bytes(data[i:i + 2], 'little') for i in range(0, 16, 2)]
        # Rotated a quarter turn clockwise: canvas (1, 0) lands at fb (1, 1).
        black = [i for i, v in enumerate(px) if v == 0]
        self.assertEqual(black, [1 * 2 + 1])
        self.assertTrue(all(v == 0xFFFF for i, v in enumerate(px) if i != 3))

    def test_blit_no_rotation_32bpp(self):
        tmp = Path(tempfile.mkdtemp())
        fbdir = tmp / 'fb0'
        fbdir.mkdir()
        (fbdir / 'virtual_size').write_text('4,2\n')
        (fbdir / 'stride').write_text('16\n')
        (fbdir / 'bits_per_pixel').write_text('32\n')
        dev = tmp / 'dev'
        dev.write_bytes(b'')
        c = scr.Canvas(4, 2)
        c.set(3, 1)
        scr.blit(c, fb_dir=str(fbdir), dev=str(dev), rotate_path=str(tmp / 'missing'))
        data = dev.read_bytes()
        px = [int.from_bytes(data[i:i + 4], 'little') for i in range(0, 32, 4)]
        self.assertEqual([i for i, v in enumerate(px) if v == 0xFF000000], [7])


class Main(unittest.TestCase):

    def test_exits_when_setup_is_over(self):
        tmp = Path(tempfile.mkdtemp())
        status = tmp / 'status.json'
        status.write_text('{"phase": "off", "screen": {"title": "", "lines": [], "qr": null}}')
        old = scr.DONE_S, scr.find_font, scr.sys.stdout
        scr.DONE_S, scr.find_font = 0.1, (lambda: None)
        scr.sys.stdout = open(os.devnull, 'w')
        try:
            self.assertEqual(scr.main(status, tmp / 'requested', poll=0.02), 0)
        finally:
            scr.sys.stdout.close()
            scr.DONE_S, scr.find_font, scr.sys.stdout = old


if __name__ == '__main__':
    unittest.main()
