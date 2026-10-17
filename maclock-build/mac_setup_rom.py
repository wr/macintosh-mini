#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# mac_setup_rom.py
#
# Checks a ROM someone hands the setup page: a raw ROM, or the .zip it was
# downloaded as. Error messages are shown to the owner as-is, so they are
# plain words, not exceptions.
# ####################################

import io
import sys
import zipfile
from array import array

SIZES = {
    'basilisk': (512 * 1024, 1024 * 1024),
    'sheepshaver': (4 * 1024 * 1024,),
}
PPC_SIZE = 4 * 1024 * 1024


class RomError(Exception):
    """A ROM was refused; str(e) is the message for the owner."""


def rom_checksum_ok(data):
    # A 68k Mac ROM starts with a checksum: the sum of every big-endian 16-bit
    # word after it, kept to 32 bits. A blank file sums to zero, so a zero
    # checksum counts as a failure too.
    stored = int.from_bytes(data[:4], 'big')
    words = array('H', data[4:len(data) & ~1])
    if sys.byteorder == 'little':
        words.byteswap()
    return stored != 0 and stored == sum(words) & 0xFFFFFFFF


def check_rom(data, emulator):
    size = len(data)
    if emulator == 'sheepshaver':
        if size == PPC_SIZE:
            return
        if size in SIZES['basilisk']:
            raise RomError("That's a 68k ROM; this Mac runs SheepShaver and needs the 4 MB PowerPC ROM.")
        raise RomError("That file isn't a Mac ROM.")
    if size == PPC_SIZE:
        raise RomError("That's a PowerPC ROM; this Mac needs a 68k one like the Performa ROM.")
    if size not in SIZES['basilisk']:
        raise RomError("That file isn't a Mac ROM.")
    if not rom_checksum_ok(data):
        raise RomError("That ROM looks damaged: its checksum doesn't match. Try downloading it again.")


def extract_rom(data, emulator):
    if not data.startswith(b'PK'):
        check_rom(data, emulator)
        return data
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        sizes = SIZES['basilisk'] + SIZES['sheepshaver']
        # Largest first, so a 1 MB ROM wins over a 512 KB one in the same zip.
        members = sorted((m for m in z.infolist() if m.file_size in sizes),
                         key=lambda m: m.file_size, reverse=True)
        last = None
        for m in members:
            candidate = z.read(m)
            try:
                check_rom(candidate, emulator)
            except RomError as e:
                last = e
                continue
            return candidate
    except (zipfile.BadZipFile, EOFError, ValueError, NotImplementedError):
        raise RomError("That zip file is damaged. Try downloading it again.")
    # A ROM of the wrong kind says why; anything else is just not a ROM.
    if last is not None and 'damaged' not in str(last):
        raise last
    raise RomError("That zip doesn't have a Mac ROM in it.")
