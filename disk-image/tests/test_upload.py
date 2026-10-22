# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import tomllib
import unittest
from pathlib import Path

from upload import already_there, description_html, ia_args, metadata_args

HERE = Path(__file__).resolve().parent.parent


class UploadTest(unittest.TestCase):
    def test_description_paragraphs_become_html_paragraphs(self):
        text = "First line\nsame paragraph.\n\n<b>List</b>:\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>\n\nLast.\n"
        self.assertEqual(description_html(text),
                         "<p>First line same paragraph.</p>"
                         "<p><b>List</b>:</p>"
                         "<ul><li>one</li><li>two</li></ul>"
                         "<p>Last.</p>")

    def test_ia_args_upload_every_file_with_every_field(self):
        meta = {"identifier": "item", "title": "T", "mediatype": "software",
                "subject": ["a", "b"], "description": "Hello\nthere."}
        args = ia_args(meta, ["x.zip", "x.zip.sha256"])
        self.assertEqual(args[:5], ["ia", "upload", "item", "x.zip", "x.zip.sha256"])
        self.assertIn("--metadata=title:T", args)
        self.assertIn("--metadata=mediatype:software", args)
        self.assertIn("--metadata=subject:a", args)
        self.assertIn("--metadata=subject:b", args)
        self.assertIn("--metadata=description:<p>Hello there.</p>", args)
        self.assertNotIn("--metadata=identifier:item", args)

    def test_metadata_args_refresh_an_existing_items_text(self):
        meta = {"identifier": "item", "title": "T", "subject": ["a", "b"], "description": "Hi\nthere."}
        args = metadata_args(meta)
        self.assertEqual(args[:3], ["ia", "metadata", "item"])
        self.assertIn("--modify=title:T", args)
        self.assertIn("--modify=subject:a;b", args)
        self.assertIn("--modify=description:<p>Hi there.</p>", args)
        self.assertNotIn("--modify=identifier:item", args)

    def test_files_already_on_the_archive_are_named(self):
        listed = "macos-8.1-basilisk-ii-2026.10.zip\nmacos-8.1-basilisk-ii-2026.10.zip.sha256\nx_meta.xml\n"
        self.assertEqual(already_there(["out/macos-8.1-basilisk-ii-2026.10.zip"], listed),
                         ["macos-8.1-basilisk-ii-2026.10.zip"])
        self.assertEqual(already_there(["macos-8.1-basilisk-ii-2026.11.zip"], listed), [])

    def test_real_metadata_has_what_the_archive_needs(self):
        meta = tomllib.loads((HERE / "ia-metadata.toml").read_text())
        for key in ("identifier", "title", "mediatype", "collection", "creator", "subject", "description"):
            self.assertIn(key, meta)
        self.assertEqual(meta["identifier"], "macos-8.1-basilisk-ii")


if __name__ == "__main__":
    unittest.main()
