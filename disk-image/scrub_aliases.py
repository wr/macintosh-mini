#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Blank names the Mac OS installer left in the image's aliases, in place:
scrub_aliases.py IMAGE NAME [NAME...]   e.g. scrub_aliases.py out/macos-8.1.hda "SE/30" Wells"""
import sys
from pathlib import Path

from mmdisk.scrub import scrub_alias_names


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    image = bytearray(path.read_bytes())
    n = scrub_alias_names(image, [name.encode("mac_roman") for name in sys.argv[2:]])
    path.write_bytes(image)
    print(f"blanked {n} name(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
