# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from mmdisk.sources import (ChecksumError, MissingSourceError, Source, fetch,
                            load_sources)

HERE = Path(__file__).resolve().parent


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cache = self.dir / "cache"

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_sources_reads_entries(self):
        toml = self.dir / "sources.toml"
        toml.write_text(
            '[[source]]\nid = "a"\nfile = "a.sit"\nsha256 = "' + "0" * 64 + '"\n'
            'url = "https://example.com/a.sit"\nnote = "first"\n\n'
            '[[source]]\nid = "b"\nfile = "b.img"\nsha256 = "' + "1" * 64 + '"\n'
            'note = "from Wells"\n')
        sources = load_sources(toml)
        self.assertEqual([s.id for s in sources], ["a", "b"])
        self.assertEqual(sources[0], Source("a", "a.sit", "0" * 64, "https://example.com/a.sit", "first"))
        self.assertIsNone(sources[1].url)

    def test_fetch_downloads_and_verifies(self):
        payload = b"StuffIt archive bytes"
        origin = self.dir / "origin.sit"
        origin.write_bytes(payload)
        src = Source("x", "x.sit", sha256(payload), origin.as_uri(), "")
        path = fetch(src, self.cache)
        self.assertEqual(path, self.cache / "x.sit")
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse((self.cache / "x.sit.part").exists())

    def test_fetch_rejects_bad_checksum(self):
        origin = self.dir / "origin.sit"
        origin.write_bytes(b"not what was pinned")
        src = Source("x", "x.sit", "f" * 64, origin.as_uri(), "")
        with self.assertRaises(ChecksumError):
            fetch(src, self.cache)
        self.assertFalse((self.cache / "x.sit").exists())
        self.assertFalse((self.cache / "x.sit.part").exists())

    def test_fetch_verifies_existing_file_without_url(self):
        self.cache.mkdir()
        (self.cache / "y.img").write_bytes(b"hand-fetched")
        src = Source("y", "y.img", sha256(b"hand-fetched"), None, "")
        self.assertEqual(fetch(src, self.cache), self.cache / "y.img")

    def test_fetch_missing_manual_source(self):
        src = Source("y", "y.img", "0" * 64, None, "Wells has it")
        with self.assertRaises(MissingSourceError) as cm:
            fetch(src, self.cache)
        self.assertIn(str(self.cache / "y.img"), str(cm.exception))
        self.assertIn("Wells has it", str(cm.exception))

    def test_real_sources_toml_is_valid(self):
        sources = load_sources(HERE.parent / "sources.toml")
        ids = [s.id for s in sources]
        self.assertEqual(len(ids), len(set(ids)))
        for s in sources:
            self.assertRegex(s.sha256, re.compile(r"^[0-9a-f]{64}$"), s.id)
        self.assertIn("macos81-cd", ids)
        self.assertIn("imagewriter-option", ids)


if __name__ == "__main__":
    unittest.main()
