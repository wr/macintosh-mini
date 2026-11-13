# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""The pinned downloads the disk image is built from (sources.toml)."""
import hashlib
import shutil
import tomllib
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class ChecksumError(Exception):
    pass


class MissingSourceError(Exception):
    pass


@dataclass
class Source:
    id: str
    file: str
    sha256: str
    url: str | None
    note: str


def load_sources(path: Path) -> list[Source]:
    with open(path, "rb") as f:
        entries = tomllib.load(f).get("source", [])
    return [Source(e["id"], e["file"], e["sha256"].lower(), e.get("url") or None, e.get("note", ""))
            for e in entries]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(src: Source, cache: Path) -> Path:
    """The source's file in cache, downloaded if missing, always checked."""
    path = cache / src.file
    if not path.exists():
        if not src.url:
            raise MissingSourceError(f"{src.id}: put {src.file} at {path} ({src.note})")
        cache.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        try:
            # Some mirrors (old.mac.gdn) refuse Python's default User-Agent
            req = urllib.request.Request(src.url, headers={"User-Agent": "macintosh-mini-disk-image"})
            with urllib.request.urlopen(req) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f)
            got = _sha256(part)
            if got != src.sha256:
                raise ChecksumError(f"{src.id}: {src.url} has SHA-256 {got}, expected {src.sha256}")
            part.rename(path)
        finally:
            part.unlink(missing_ok=True)
        return path
    got = _sha256(path)
    if got != src.sha256:
        raise ChecksumError(f"{src.id}: {path} has SHA-256 {got}, expected {src.sha256}")
    return path
