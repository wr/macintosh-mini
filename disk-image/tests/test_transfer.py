# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import machfs

from mmdisk.macfile import (MacFile, extract_archive, files_from_floppy,
                            files_from_tree, read_host_file)
from mmdisk.transfer import build_transfer, collect, local_file, pick_from_floppy

ON_MAC = sys.platform == "darwin"


def finder_info(type_: bytes, creator: bytes, flags: int) -> str:
    return (type_ + creator + flags.to_bytes(2, "big") + bytes(22)).hex()


def hfs_volume_name(image: bytes) -> str:
    """The name in the HFS master directory block (machfs doesn't read it back)."""
    n = image[1024 + 36]
    return image[1024 + 37:1024 + 37 + n].decode("mac_roman")


def write_host_file(path: Path, data: bytes, rsrc: bytes, type_: bytes, creator: bytes, flags: int = 0):
    path.write_bytes(data)
    with open(f"{path}/..namedfork/rsrc", "wb") as f:
        f.write(rsrc)
    subprocess.run(["xattr", "-wx", "com.apple.FinderInfo", finder_info(type_, creator, flags), str(path)],
                   check=True)


class TransferTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_transfer_roundtrip(self):
        files = {
            "Apps:iCab:iCab": MacFile("iCab", b"", b"CODE resources", b"APPL", b"iCAB"),
            "Web:Start Page": MacFile("Start Page", b"<html></html>", b"", b"TEXT", b"iCAB"),
        }
        image = build_transfer(files, size=4 * 2**20)
        self.assertEqual(len(image), 4 * 2**20)
        self.assertEqual(hfs_volume_name(image), "Transfer")
        v = machfs.Volume()
        v.read(image)
        app = v["Apps"]["iCab"]["iCab"]
        self.assertEqual((bytes(app.rsrc), app.type, app.creator), (b"CODE resources", b"APPL", b"iCAB"))
        page = v["Web"]["Start Page"]
        self.assertEqual((bytes(page.data), page.type, page.creator), (b"<html></html>", b"TEXT", b"iCAB"))

    def test_files_from_floppy(self):
        v = machfs.Volume()
        v.name = "Untitled"
        f = machfs.File()
        f.type, f.creator, f.rsrc = b"PRER", b"IWRX", bytearray(b"driver")
        v["AppleTalk ImageWriter"] = f
        v["Folder"] = machfs.Folder()
        v["Folder"]["Note"] = machfs.File()
        image = v.write(size=800 * 1024, desktopdb=False, bootable=False)
        files = files_from_floppy(image)
        self.assertEqual(set(files), {"AppleTalk ImageWriter", "Folder:Note"})
        drv = files["AppleTalk ImageWriter"]
        self.assertEqual((drv.name, drv.rsrc, drv.type, drv.creator),
                         ("AppleTalk ImageWriter", b"driver", b"PRER", b"IWRX"))

    def test_files_from_floppy_reads_disk_copy_42_image(self):
        v = machfs.Volume()
        v.name = "After Dark Disk"
        v["After Dark"] = machfs.File()
        raw = v.write(size=800 * 1024, desktopdb=False, bootable=False)
        # Disk Copy 4.2: 64-byte name, data and tag sizes, checksums, disk format, 0x0100
        header = (bytes([15]) + b"After Dark Disk").ljust(64, b"\0") + \
            len(raw).to_bytes(4, "big") + bytes(4) + bytes(8) + b"\x01\x22" + b"\x01\x00"
        self.assertEqual(len(header), 84)
        self.assertEqual(set(files_from_floppy(header + raw)), {"After Dark"})

    @unittest.skipUnless(ON_MAC, "resource forks and FinderInfo are read the macOS way")
    def test_read_host_file(self):
        path = self.dir / "SimpleText"
        write_host_file(path, b"data fork", b"rsrc fork", b"APPL", b"ttxt", 0x2000)
        self.assertEqual(read_host_file(path),
                         MacFile("SimpleText", b"data fork", b"rsrc fork", b"APPL", b"ttxt", 0x2000))

    @unittest.skipUnless(ON_MAC, "resource forks and FinderInfo are read the macOS way")
    def test_files_from_tree(self):
        (self.dir / "After Dark Files").mkdir()
        write_host_file(self.dir / "After Dark Files" / "Flying Toasters", b"", b"module", b"ADgm", b"ADrk")
        write_host_file(self.dir / "After Dark", b"", b"cdev", b"cdev", b"ADrk")
        files = files_from_tree(self.dir)
        self.assertEqual(set(files), {"After Dark", "After Dark Files:Flying Toasters"})
        self.assertEqual(files["After Dark Files:Flying Toasters"].type, b"ADgm")

    def test_extract_archive_zip(self):
        archive = self.dir / "pages.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("Pages/Start Page.html", "<html></html>")
        out = extract_archive(archive, self.dir / "out")
        self.assertEqual((out / "Pages" / "Start Page.html").read_text(), "<html></html>")

    @unittest.skipUnless(ON_MAC, "resource forks and FinderInfo are read the macOS way")
    def test_collect_keeps_folder_structure_under_its_name(self):
        (self.dir / "iCab 2.9.9" / "Plug-ins").mkdir(parents=True)
        write_host_file(self.dir / "iCab 2.9.9" / "iCab", b"", b"code", b"APPL", b"iCAB")
        write_host_file(self.dir / "iCab 2.9.9" / "Plug-ins" / "Java", b"", b"j", b"plug", b"iCAB")
        files = collect(self.dir, "iCab*")
        self.assertEqual(set(files), {"iCab 2.9.9:iCab", "iCab 2.9.9:Plug-ins:Java"})

    @unittest.skipUnless(ON_MAC, "resource forks and FinderInfo are read the macOS way")
    def test_collect_single_file(self):
        write_host_file(self.dir / "StuffIt Expander", b"d", b"r", b"APPL", b"SITx")
        self.assertEqual(list(collect(self.dir, "StuffIt*")), ["StuffIt Expander"])

    def test_collect_missing_pattern_raises(self):
        with self.assertRaises(FileNotFoundError):
            collect(self.dir, "Nothing*")

    def test_pick_from_floppy_keeps_folder_structure_under_its_name(self):
        mf = MacFile("x", b"", b"r", b"ADgm", b"ADrk")
        on_floppy = {"After Dark Files:Fish!": mf, "After Dark Files:Slide Show Folder:Logo": mf, "After Dark": mf}
        picked = pick_from_floppy(on_floppy, "After Dark Files")
        self.assertEqual(set(picked), {"After Dark Files:Fish!", "After Dark Files:Slide Show Folder:Logo"})

    def test_pick_from_floppy_single_file_by_its_name(self):
        mf = MacFile("x", b"", b"r", b"cdev", b"ADrk")
        on_floppy = {"After Dark": mf, "Extras:Read Me": mf}
        self.assertEqual(list(pick_from_floppy(on_floppy, "After Dark")), ["After Dark"])
        self.assertEqual(list(pick_from_floppy(on_floppy, "Extras:Read*")), ["Read Me"])

    def test_pick_from_floppy_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            pick_from_floppy({"After Dark": MacFile("x", b"", b"", b"cdev", b"ADrk")}, "Nothing*")

    def test_local_file_uses_mac_line_endings(self):
        path = self.dir / "page.html"
        path.write_text("<html>\n<body></body>\n</html>\n")
        mf = local_file(path, "Start Page", b"TEXT", b"iCAB")
        self.assertEqual(mf, MacFile("Start Page", b"<html>\r<body></body>\r</html>\r", b"", b"TEXT", b"iCAB"))


if __name__ == "__main__":
    unittest.main()
