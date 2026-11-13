#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check a finished disk image against expected.toml: check_image.py IMAGE"""
import sys
import tomllib
from pathlib import Path

from mmdisk.check import check_image

HERE = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    expected = tomllib.loads((HERE / "expected.toml").read_text())
    problems = check_image(Path(sys.argv[1]).read_bytes(), expected)
    for p in problems:
        print(p)
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
