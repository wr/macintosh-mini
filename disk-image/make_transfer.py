#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build out/transfer.dsk from transfer.toml: make_transfer.py [--cache DIR]"""
import argparse
import sys
import tomllib
from pathlib import Path

from mmdisk.macfile import files_from_floppy
from mmdisk.sources import load_sources
from mmdisk.transfer import build_transfer, collect, local_file, pick_from_floppy, unpacked

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=HERE / ".cache")
    args = ap.parse_args()
    out = HERE / "out"
    sources = {s.id: s for s in load_sources(HERE / "sources.toml")}
    plan = tomllib.loads((HERE / "transfer.toml").read_text())
    files = {}
    for item in plan["item"]:
        root = unpacked(sources[item["source"]], args.cache, out / "unpacked")
        if "floppy" in item:
            floppy = collect(root, item["floppy"])
            [image] = floppy.values()
            on_floppy = files_from_floppy(image.data)
            picked = {}
            for pattern in item["pick"]:
                picked.update(pick_from_floppy(on_floppy, pattern))
        else:
            picked = {}
            for pattern in item["pick"]:
                picked.update(collect(root, pattern))
        files.update({f"{item['dest']}:{key}": mf for key, mf in picked.items()})
    for f in plan.get("file", []):
        files[f"{f['dest']}:{f['name']}"] = local_file(HERE / f["path"], f["name"],
                                                       f["type"].encode(), f["creator"].encode())
    out.mkdir(exist_ok=True)
    (out / "transfer.dsk").write_bytes(build_transfer(files))
    print(f"out/transfer.dsk: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
