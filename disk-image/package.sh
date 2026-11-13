#!/bin/bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# package.sh IMAGE VERSION: zip the finished image for the Internet Archive.
# Writes macos-8.1-basilisk-ii-VERSION.zip beside IMAGE, holding the image as
# macos-8.1-basilisk-ii-VERSION.hda, and the zip's SHA-256 in a .sha256 file.
set -euo pipefail

die() { echo "package.sh: $*" >&2; exit 1; }

[[ $# -eq 2 ]] || die "usage: package.sh IMAGE VERSION   (e.g. out/macos-8.1.hda 2026.10)"
image=$1; version=$2
[[ -f $image ]] || die "no image at $image"
# A year and month, with .1, .2… for another version in the same month: a
# version is never uploaded twice, since installers pin its checksum.
[[ $version =~ ^[0-9]{4}\.[0-9]{2}(\.[0-9]+)?$ ]] || die "VERSION is a year and month, like 2026.10 or 2026.10.1, not $version"

out=$(cd "$(dirname "$image")" && pwd)
name=macos-8.1-basilisk-ii-$version
stage=$(mktemp -d "$out/.package.XXXXXX")
trap 'rm -rf "$stage"' EXIT

# A hard link names the image inside the zip without copying a gigabyte.
ln "$image" "$stage/$name.hda" 2>/dev/null || cp "$image" "$stage/$name.hda"
rm -f "$out/$name.zip" "$out/$name.zip.sha256"
(cd "$stage" && zip -q -9 -X "$name.zip" "$name.hda")
mv "$stage/$name.zip" "$out/$name.zip"
(cd "$out" && shasum -a 256 "$name.zip" > "$name.zip.sha256")
echo "$out/$name.zip"
