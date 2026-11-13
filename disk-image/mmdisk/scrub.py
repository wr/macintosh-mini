# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Blank names that the Mac OS installer copied into aliases, in place on a
finished image. Aliases hold the Sharing Setup names of the Mac that made them
(for finding a file over AppleShare), here the Mac that ran the installer."""
import struct

import machfs


def _alias_records(fork: bytes) -> list[bytes]:
    """Every 'alis' resource in a resource fork."""
    if len(fork) < 16:
        return []
    data_off, map_off = struct.unpack(">II", fork[:8])
    rmap = fork[map_off:]
    types = rmap[struct.unpack(">H", rmap[24:26])[0]:]
    found = []
    for i in range(struct.unpack(">h", types[:2])[0] + 1):
        t, n, refs_off = struct.unpack(">4shH", types[2 + 8 * i:10 + 8 * i])
        if t != b"alis":
            continue
        for j in range(n + 1):
            ref = types[refs_off + 12 * j:refs_off + 12 * j + 12]
            at = data_off + (struct.unpack(">I", ref[4:8])[0] & 0xFFFFFF)
            found.append(fork[at + 4:at + 4 + struct.unpack(">I", fork[at:at + 4])[0]])
    return found


def scrub_alias_names(image: bytearray, names: list[bytes]) -> int:
    """Zero each name's Pascal-string field inside every alias record on the
    image, keeping every size, and return how many fields were blanked."""
    v = machfs.Volume()
    v.read(bytes(image))
    blanked = 0
    for path, f in v.iter_paths():
        if not isinstance(f, machfs.File):
            continue
        for record in _alias_records(bytes(f.rsrc)):
            patched = record
            for name in names:
                field = bytes([len(name)]) + name
                blanked += patched.count(field)
                patched = patched.replace(field, bytes(len(field)))
            if patched == record:
                continue
            at = image.find(record)
            if at < 0:
                raise ValueError(f"the alias in {':'.join(path)} isn't stored in one piece")
            image[at:at + len(record)] = patched
    return blanked
