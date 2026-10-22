# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Classic Mac files (both forks, type, creator, Finder flags), read from
macOS files, unpacked archives and HFS floppy images."""
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import machfs


@dataclass
class MacFile:
    name: str
    data: bytes
    rsrc: bytes
    type: bytes
    creator: bytes
    flags: int = 0


def read_host_file(path: Path) -> MacFile:
    """A macOS file as a Mac file: its resource fork and FinderInfo come
    from the named fork and the com.apple.FinderInfo attribute."""
    rsrc_path = Path(f"{path}/..namedfork/rsrc")
    rsrc = rsrc_path.read_bytes() if rsrc_path.exists() else b""
    info = subprocess.run(["xattr", "-px", "com.apple.FinderInfo", str(path)],
                          capture_output=True, text=True)
    fi = bytes.fromhex("".join(info.stdout.split())) if info.returncode == 0 else b""
    type_, creator = (fi[0:4], fi[4:8]) if len(fi) >= 8 else (b"????", b"????")
    flags = int.from_bytes(fi[8:10], "big") if len(fi) >= 10 else 0
    # macOS shows a ':' in a Mac file name as '/', and the other way round
    return MacFile(path.name.replace(":", "/"), path.read_bytes(), rsrc, type_, creator, flags)


def files_from_tree(root: Path) -> dict[str, MacFile]:
    """Every file under root, keyed by its colon-separated path below root."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        rel = Path(dirpath).relative_to(root).parts
        for name in sorted(filenames):
            if name == ".DS_Store" or name.startswith("._"):
                continue
            key = ":".join(p.replace(":", "/") for p in rel + (name,))
            files[key] = read_host_file(Path(dirpath) / name)
    return files


def extract_archive(archive: Path, dest: Path) -> Path:
    """Unpack a .sit/.sea/.hqx/.bin/.zip into dest, keeping resource forks."""
    dest.mkdir(parents=True, exist_ok=True)
    # Some archives hold a file and a folder with the same name, which unar
    # can't both write; the files we need are checked for by name afterwards.
    r = subprocess.run(["unar", "-q", "-forks", "fork", "-no-directory", "-o", str(dest), str(archive)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"warning: unar couldn't extract everything from {archive.name}:\n{r.stdout}{r.stderr}")
    return dest


def files_from_floppy(image: bytes) -> dict[str, MacFile]:
    """Every file on an HFS disk image (raw or Disk Copy 4.2), keyed by its
    colon-separated path."""
    if image[1024:1026] != b"BD" and image[84 + 1024:84 + 1026] == b"BD":
        # Disk Copy 4.2: an 84-byte header, then the disk, its size at byte 64
        image = image[84:84 + int.from_bytes(image[64:68], "big")]
    v = machfs.Volume()
    v.read(image)
    return {":".join(path): MacFile(path[-1], bytes(f.data), bytes(f.rsrc), f.type, f.creator, f.flags)
            for path, f in v.iter_paths() if isinstance(f, machfs.File)}
