# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Transfer disk: an HFS volume that carries the software into the
emulated Mac, which installs it from there."""
from pathlib import Path

import machfs

from .macfile import MacFile, files_from_tree, read_host_file


def collect(root: Path, pattern: str) -> dict[str, MacFile]:
    """The files matching a glob under root: a file by its name, a folder as
    everything below it, under the folder's name."""
    matches = sorted(root.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"nothing matches {pattern!r} under {root}")
    files = {}
    for m in matches:
        name = m.name.replace(":", "/")
        if m.is_dir():
            files.update({f"{name}:{key}": mf for key, mf in files_from_tree(m).items()})
        else:
            files[name] = read_host_file(m)
    return files


def local_file(path: Path, name: str, type_: bytes, creator: bytes) -> MacFile:
    """A text file from this repo, with classic Mac line endings."""
    text = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r")
    return MacFile(name, text, b"", type_, creator)


def build_transfer(files: dict[str, MacFile], size: int = 256 * 2**20, name: str = "Transfer") -> bytes:
    """An HFS volume holding files, each at its colon-separated path."""
    v = machfs.Volume()
    v.name = name
    for key, mf in files.items():
        *folders, leaf = key.split(":")
        for part in key.split(":"):
            if not 0 < len(part) <= 31:
                raise ValueError(f"HFS names are 1-31 characters: {part!r} in {key!r}")
        parent = v
        for part in folders:
            if part not in parent:
                parent[part] = machfs.Folder()
            parent = parent[part]
        f = machfs.File()
        f.data, f.rsrc = bytearray(mf.data), bytearray(mf.rsrc)
        f.type, f.creator, f.flags = mf.type, mf.creator, mf.flags
        parent[leaf] = f
    return v.write(size=size, align=512, desktopdb=False, bootable=False)
