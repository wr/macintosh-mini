#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
"""Upload a packaged image and its .sha256 to the Internet Archive with
ia-metadata.toml: upload.py ZIP. Needs the ia tool, signed in with ia configure."""
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent


def description_html(text: str) -> str:
    """The archive shows descriptions as HTML: each blank-line-separated
    paragraph becomes a <p>, and a <ul> block stays a list."""
    parts = []
    for para in text.strip().split("\n\n"):
        lines = [line.strip() for line in para.splitlines()]
        start = lines.index("<ul>") if "<ul>" in lines else len(lines)
        if start:
            parts.append(f"<p>{' '.join(lines[:start])}</p>")
        parts.append("".join(lines[start:]))
    return "".join(parts)


def ia_args(meta: dict, files: list[str]) -> list[str]:
    """The ia upload command for these files, one --metadata per value."""
    args = ["ia", "upload", meta["identifier"], *files]
    for key, value in meta.items():
        if key == "identifier":
            continue
        if key == "description":
            value = description_html(value)
        for v in value if isinstance(value, list) else [value]:
            args.append(f"--metadata={key}:{v}")
    return args + ["--retries=10"]


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".zip"):
        print(__doc__, file=sys.stderr)
        return 2
    zip_path = Path(sys.argv[1])
    sha = Path(f"{zip_path}.sha256")
    for f in (zip_path, sha):
        if not f.exists():
            print(f"missing: {f}", file=sys.stderr)
            return 1
    meta = tomllib.loads((HERE / "ia-metadata.toml").read_text())
    return subprocess.run(ia_args(meta, [str(zip_path), str(sha)])).returncode


if __name__ == "__main__":
    sys.exit(main())
