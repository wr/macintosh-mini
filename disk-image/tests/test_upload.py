# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
import tomllib
import unittest
from pathlib import Path

from upload import description_html, ia_args

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

    def test_real_metadata_has_what_the_archive_needs(self):
        meta = tomllib.loads((HERE / "ia-metadata.toml").read_text())
        for key in ("identifier", "title", "mediatype", "collection", "creator", "subject", "description"):
            self.assertIn(key, meta)
        self.assertEqual(meta["identifier"], "macos-8.1-basilisk-ii")


if __name__ == "__main__":
    unittest.main()
