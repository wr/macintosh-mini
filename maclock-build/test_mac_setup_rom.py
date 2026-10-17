#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for mac_setup_rom.py.

Run: python3 -m unittest test_mac_setup_rom
"""

import io
import unittest
import zipfile

import mac_setup_rom as rom

K512 = 512 * 1024
M1 = 1024 * 1024
M4 = 4 * 1024 * 1024


def make_rom(size, seed=7):
    """A synthetic Mac ROM: patterned bytes with a correct checksum in front."""
    body = bytearray((i * seed + (i >> 9)) & 0xFF for i in range(size))
    total = sum(int.from_bytes(body[i:i + 2], 'big') for i in range(4, size, 2))
    body[0:4] = (total & 0xFFFFFFFF).to_bytes(4, 'big')
    return bytes(body)


def make_zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


class CheckRom(unittest.TestCase):

    def test_good_68k_rom_passes(self):
        for size in (K512, M1):
            data = make_rom(size)
            self.assertTrue(rom.rom_checksum_ok(data))
            rom.check_rom(data, 'basilisk')

    def test_bad_checksum_rejected(self):
        data = bytearray(make_rom(M1))
        data[100] ^= 0xFF
        with self.assertRaises(rom.RomError) as cm:
            rom.check_rom(bytes(data), 'basilisk')
        self.assertIn('damaged', str(cm.exception))

    def test_ppc_rom_rejected_for_basilisk(self):
        with self.assertRaises(rom.RomError) as cm:
            rom.check_rom(bytes(M4), 'basilisk')
        self.assertEqual(str(cm.exception),
                         "That's a PowerPC ROM; this Mac needs a 68k one like the Performa ROM.")

    def test_68k_rom_rejected_for_sheepshaver(self):
        with self.assertRaises(rom.RomError) as cm:
            rom.check_rom(make_rom(M1), 'sheepshaver')
        self.assertIn('4 MB PowerPC ROM', str(cm.exception))

    def test_ppc_rom_passes_for_sheepshaver(self):
        rom.check_rom(bytes(M4), 'sheepshaver')

    def test_wrong_size_rejected(self):
        with self.assertRaises(rom.RomError) as cm:
            rom.check_rom(bytes(1000), 'basilisk')
        self.assertEqual(str(cm.exception), "That file isn't a Mac ROM.")

    def test_html_is_not_a_rom(self):
        page = b'<!DOCTYPE html><html><body>Not found</body></html>'
        with self.assertRaises(rom.RomError) as cm:
            rom.extract_rom(page, 'basilisk')
        self.assertEqual(str(cm.exception), "That file isn't a Mac ROM.")


class ExtractRom(unittest.TestCase):

    def test_raw_rom_returned(self):
        data = make_rom(M1)
        self.assertEqual(rom.extract_rom(data, 'basilisk'), data)

    def test_zip_with_rom_inside(self):
        data = make_rom(M1)
        z = make_zip({'readme.txt': b'hello', '1mbMacrom.rom': data})
        self.assertEqual(rom.extract_rom(z, 'basilisk'), data)

    def test_zip_without_rom(self):
        z = make_zip({'readme.txt': b'hello', 'junk.bin': bytes(M1)})
        with self.assertRaises(rom.RomError) as cm:
            rom.extract_rom(z, 'basilisk')
        self.assertEqual(str(cm.exception), "That zip doesn't have a Mac ROM in it.")

    def test_zip_with_ppc_rom_explains(self):
        z = make_zip({'newworld86.rom': bytes(M4)})
        with self.assertRaises(rom.RomError) as cm:
            rom.extract_rom(z, 'basilisk')
        self.assertIn('PowerPC', str(cm.exception))

    def test_corrupt_zip(self):
        with self.assertRaises(rom.RomError):
            rom.extract_rom(b'PK\x03\x04garbage', 'basilisk')


if __name__ == '__main__':
    unittest.main()
