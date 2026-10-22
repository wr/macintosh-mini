# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import unittest

import machfs

from mmdisk.check import resource
from mmdisk.scrub import scrub_alias_names


def fork_with(rtype: bytes, data: bytes) -> bytes:
    """A resource fork holding one resource, ID 0."""
    block = struct.pack(">I", len(data)) + data
    refs = struct.pack(">hHII", 0, 0xFFFF, 0, 0)
    types = struct.pack(">h4shH", 0, rtype, 0, 10)
    rmap = bytes(24) + struct.pack(">HH", 28, 28 + len(types) + len(refs)) + types + refs
    header = struct.pack(">IIII", 256, 256 + len(block), len(block), len(rmap))
    return header + bytes(240) + block + rmap


def pstr(s: bytes, size: int) -> bytes:
    return (bytes([len(s)]) + s).ljust(size, b"\0")


# Shaped like an installer-made alias: an empty zone, then the server and user names.
ALIAS = b"\x12" * 40 + bytes(33) + pstr(b"SE/30", 32) + pstr(b"Macintosh HD", 28) + pstr(b"Wells", 32) + b"\x34" * 20


def volume() -> bytes:
    v = machfs.Volume()
    v.name = "Macintosh HD"
    for name, rtype, data in (("Chooser alias", b"alis", ALIAS), ("Profiler", b"STR#", b"\x00\x01\x0fMacintosh SE/30")):
        f = machfs.File()
        f.type, f.creator, f.rsrc = b"adrp", b"MACS", bytearray(fork_with(rtype, data))
        v[name] = f
    return v.write(size=4 * 2**20, desktopdb=False, bootable=False)


def alias_of(image: bytes, name: str) -> bytes:
    v = machfs.Volume()
    v.read(bytes(image))
    return resource(bytes(v[name].rsrc), b"alis" if "alias" in name else b"STR#", 0)


class ScrubTest(unittest.TestCase):
    def test_blanks_the_names_inside_aliases(self):
        image = bytearray(volume())
        self.assertEqual(scrub_alias_names(image, [b"SE/30", b"Wells"]), 2)
        alias = alias_of(image, "Chooser alias")
        self.assertNotIn(b"SE/30", alias)
        self.assertNotIn(b"Wells", alias)
        self.assertEqual(len(alias), len(ALIAS))
        self.assertIn(pstr(b"Macintosh HD", 28), alias)

    def test_leaves_other_resources_alone(self):
        image = bytearray(volume())
        scrub_alias_names(image, [b"SE/30", b"Wells"])
        self.assertIn(b"Macintosh SE/30", alias_of(image, "Profiler"))

    def test_nothing_to_do_changes_nothing(self):
        image = bytearray(volume())
        scrub_alias_names(image, [b"SE/30", b"Wells"])
        once = bytes(image)
        self.assertEqual(scrub_alias_names(image, [b"SE/30", b"Wells"]), 0)
        self.assertEqual(bytes(image), once)


if __name__ == "__main__":
    unittest.main()
