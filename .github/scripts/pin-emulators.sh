#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# The CI side of setup.sh's prebuilt emulators.
#
# setup.sh keeps two marked blocks for this:
#   "emulator build settings"  flags, packages, the run check and the release
#                              tag, shared by the on-Pi compile and CI
#   "prebuilt emulators"       which release to download and its checksums,
#                              written by this script, never by hand
#
# Usage: pin-emulators.sh <command> [setup.sh]
#   settings   print the shell that defines MACEMU_REPO, MACEMU_COMMIT and both
#              blocks, for eval
#
# setup.sh defaults to the one at the top of this repository.

set -euo pipefail

die() { echo "pin-emulators: $*" >&2; exit 1; }

cmd=${1:-}
setup=${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/setup.sh}
[[ -f $setup ]] || die "can't read $setup"

settings() {
  sed -n \
    -e '/^MACEMU_REPO=/p' \
    -e '/^MACEMU_COMMIT=/p' \
    -e '/^# >>> emulator build settings/,/^# <<< emulator build settings/p' \
    -e '/^# >>> prebuilt emulators/,/^# <<< prebuilt emulators/p' \
    "$setup"
}

case $cmd in
  settings) settings ;;
  *) sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
