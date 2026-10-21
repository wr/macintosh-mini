# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "package.sh"


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_package(self, *args):
        return subprocess.run(["bash", str(PACKAGE), *args], capture_output=True, text=True)

    def test_writes_zip_holding_the_versioned_image_and_its_checksum(self):
        image = self.dir / "macos-8.1.hda"
        image.write_bytes(b"BD" * 2048)
        r = self.run_package(str(image), "2026.10")
        self.assertEqual(r.returncode, 0, r.stderr)
        zip_path = self.dir / "macos-8.1-basilisk-ii-2026.10.zip"
        with zipfile.ZipFile(zip_path) as z:
            self.assertEqual(z.namelist(), ["macos-8.1-basilisk-ii-2026.10.hda"])
            self.assertEqual(z.read("macos-8.1-basilisk-ii-2026.10.hda"), image.read_bytes())
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        self.assertEqual((self.dir / "macos-8.1-basilisk-ii-2026.10.zip.sha256").read_text(),
                         f"{digest}  macos-8.1-basilisk-ii-2026.10.zip\n")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         ["macos-8.1-basilisk-ii-2026.10.zip", "macos-8.1-basilisk-ii-2026.10.zip.sha256",
                          "macos-8.1.hda"])

    def test_missing_image_fails_and_writes_nothing(self):
        r = self.run_package(str(self.dir / "nope.hda"), "2026.10")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nope.hda", r.stderr)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_version_must_look_like_a_year_and_month(self):
        image = self.dir / "macos-8.1.hda"
        image.write_bytes(b"BD")
        r = self.run_package(str(image), "latest")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["macos-8.1.hda"])


if __name__ == "__main__":
    unittest.main()
