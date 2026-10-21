# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check a finished disk image against expected.toml."""
import struct

import machfs

ALIAS = 0x8000   # Finder flag isAlias


def volume_name(image: bytes) -> str:
    """The name in the HFS master directory block (machfs doesn't read it back)."""
    n = image[1024 + 36]
    return image[1024 + 37:1024 + 37 + n].decode("mac_roman")


def resource(fork: bytes, rtype: bytes, rid: int) -> bytes | None:
    """One resource's data from a resource fork, or None."""
    if len(fork) < 16:
        return None
    data_off, map_off = struct.unpack(">II", fork[:8])
    rmap = fork[map_off:]
    types_off = struct.unpack(">H", rmap[24:26])[0]
    types = rmap[types_off:]
    for i in range(struct.unpack(">h", types[:2])[0] + 1):
        t, n, refs_off = struct.unpack(">4shH", types[2 + 8 * i:10 + 8 * i])
        if t != rtype:
            continue
        for j in range(n + 1):
            ref = types[refs_off + 12 * j:refs_off + 12 * j + 12]
            if struct.unpack(">h", ref[:2])[0] == rid:
                at = data_off + (struct.unpack(">I", ref[4:8])[0] & 0xFFFFFF)
                return fork[at + 4:at + 4 + struct.unpack(">I", fork[at:at + 4])[0]]
    return None


def chosen_printer(driver_rsrc: bytes) -> str:
    """The printer chosen in an AppleTalk driver (its 'PAPA' -8192), or "" for none."""
    papa = resource(driver_rsrc, b"PAPA", -8192) or b"\0"
    return papa[1:1 + papa[0]].decode("mac_roman")


def _lookup(v, path: str):
    node = v
    for part in path.split(":"):
        if not hasattr(node, "keys") or part not in node:
            return None
        node = node[part]
    return node


def check_image(image: bytes, expected: dict) -> list[str]:
    """Everything about image that doesn't match expected; empty when it passes."""
    problems = []
    if len(image) != expected["size"]:
        problems.append(f"size is {len(image)} bytes, expected {expected['size']}")
    if volume_name(image) != expected["volume_name"]:
        problems.append(f"volume is named {volume_name(image)!r}, expected {expected['volume_name']!r}")
    v = machfs.Volume()
    v.read(image)
    for path in expected.get("required", []):
        if not isinstance(_lookup(v, path), machfs.File):
            problems.append(f"missing: {path}")
    for item in expected.get("desktop", []):
        f = _lookup(v, "Desktop Folder:" + item["name"])
        if f is None:
            problems.append(f"missing on the desktop: {item['name']}")
        elif bool(getattr(f, "flags", 0) & ALIAS) != item["alias"]:
            problems.append(f"{item['name']} on the desktop should {'' if item['alias'] else 'not '}be an alias")
    driver = _lookup(v, expected.get("printer_driver", ""))
    if isinstance(driver, machfs.File) and chosen_printer(driver.rsrc):
        problems.append(f"a printer is chosen ({chosen_printer(driver.rsrc)!r}); the image ships with none")
    for path in expected.get("empty", []):
        folder = _lookup(v, path)
        if folder is not None and len(folder):
            problems.append(f"{path} isn't empty: {', '.join(sorted(folder))}")
    return problems
