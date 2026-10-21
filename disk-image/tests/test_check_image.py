# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import struct
import unittest

import machfs

from mmdisk.check import check_image

SIZE = 4 * 2**20
EXPECTED = {
    "volume_name": "Macintosh HD",
    "size": SIZE,
    "required": ["System Folder:System", "System Folder:Finder",
                 "System Folder:Extensions:AppleTalk ImageWriter"],
    "desktop": [{"name": "iCab", "alias": True}, {"name": "Read Me", "alias": False}],
    "printer_driver": "System Folder:Extensions:AppleTalk ImageWriter",
    "empty": ["Trash"],
    "absent": ["System Folder:Preferences:Display Preferences"],
}


def fork_with(rtype: bytes, rid: int, data: bytes) -> bytes:
    """A resource fork holding one resource."""
    block = struct.pack(">I", len(data)) + data
    refs = struct.pack(">hHII", rid, 0xFFFF, 0, 0)
    types = struct.pack(">h4shH", 0, rtype, 0, 10)
    rmap = bytes(24) + struct.pack(">HH", 28, 28 + len(types) + len(refs)) + types + refs
    header = struct.pack(">IIII", 256, 256 + len(block), len(block), len(rmap))
    return header + bytes(240) + block + rmap


def papa(printer: str) -> bytes:
    """The driver's chosen-printer resource: Pascal strings for name and type, padded to 103."""
    name = printer.encode("mac_roman")
    data = bytes([len(name)]) + name + (b"\x0bImageWriter" if name else b"")
    return data.ljust(103, b"\0")


def volume(name="Macintosh HD", size=SIZE, drop=(), alias_flag=0x8000, printer="", trash=(), extra=()) -> bytes:
    v = machfs.Volume()
    v.name = name
    v["System Folder"] = machfs.Folder()
    v["System Folder"]["Extensions"] = machfs.Folder()
    v["Desktop Folder"] = machfs.Folder()
    v["Trash"] = machfs.Folder()
    for name in trash:
        v["Trash"][name] = machfs.File()
    files = {
        ("System Folder", "System"): (b"zsys", b"MACS", 0),
        ("System Folder", "Finder"): (b"FNDR", b"MACS", 0),
        ("System Folder", "Extensions", "AppleTalk ImageWriter"): (b"PRER", b"IWRX", 0),
        ("Desktop Folder", "iCab"): (b"APPL", b"iCAB", alias_flag),
        ("Desktop Folder", "Read Me"): (b"TEXT", b"ttxt", 0),
    }
    for path, (type_, creator, flags) in files.items():
        if path[-1] in drop:
            continue
        parent = v
        for part in path[:-1]:
            parent = parent[part]
        f = machfs.File()
        f.type, f.creator, f.flags = type_, creator, flags
        if path[-1] == "AppleTalk ImageWriter":
            f.rsrc = fork_with(b"PAPA", -8192, papa(printer))
        parent[path[-1]] = f
    for path in extra:
        parent = v
        for part in path[:-1]:
            if part not in parent:
                parent[part] = machfs.Folder()
            parent = parent[part]
        parent[path[-1]] = machfs.File()
    return v.write(size=size, desktopdb=False, bootable=False)


class CheckImageTest(unittest.TestCase):
    def test_passes_complete_volume(self):
        self.assertEqual(check_image(volume(), EXPECTED), [])

    def test_reports_missing_path(self):
        problems = check_image(volume(drop={"AppleTalk ImageWriter"}), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("System Folder:Extensions:AppleTalk ImageWriter", problems[0])

    def test_reports_wrong_size(self):
        problems = check_image(volume(size=2 * 2**20), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("size", problems[0])

    def test_reports_wrong_volume_name(self):
        problems = check_image(volume(name="Untitled"), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("Untitled", problems[0])

    def test_reports_non_alias_desktop_item(self):
        problems = check_image(volume(alias_flag=0), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("iCab", problems[0])

    def test_reports_missing_desktop_item(self):
        problems = check_image(volume(drop={"Read Me"}), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("Read Me", problems[0])

    def test_reports_chosen_printer(self):
        problems = check_image(volume(printer="ImageWriter II"), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("ImageWriter II", problems[0])

    def test_reports_full_trash(self):
        problems = check_image(volume(trash={"ImageWriter II"}), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("Trash", problems[0])

    def test_reports_file_that_must_be_absent(self):
        problems = check_image(volume(extra=[("System Folder", "Preferences", "Display Preferences")]), EXPECTED)
        self.assertEqual(len(problems), 1)
        self.assertIn("Display Preferences", problems[0])


if __name__ == "__main__":
    unittest.main()
