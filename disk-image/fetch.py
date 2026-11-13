#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch and check every pinned source: fetch.py [--cache DIR]"""
import argparse
import sys
from pathlib import Path

from mmdisk.sources import ChecksumError, MissingSourceError, fetch, load_sources

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=HERE / ".cache")
    args = ap.parse_args()
    failed = []
    for src in load_sources(HERE / "sources.toml"):
        try:
            print(f"ok    {src.id}: {fetch(src, args.cache)}")
        except (ChecksumError, MissingSourceError, OSError) as e:
            failed.append(src.id)
            print(f"FAIL  {e}", file=sys.stderr)
    if failed:
        print(f"{len(failed)} source(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
