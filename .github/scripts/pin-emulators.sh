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
# Usage: pin-emulators.sh [--setup FILE] <command> [args]
#   settings          print the shell that defines MACEMU_REPO, MACEMU_COMMIT
#                     and both blocks, for eval
#   tag               print the release tag for the current pin and settings
#   status            print what CI has to do: "current" (the release exists
#                     and setup.sh pins it), "repin" (the release exists, the
#                     pins don't match it) or "build" (no release yet)
#   write SUMS        point the pins at the current tag, with the checksums in
#                     SUMS (a SHA256SUMS file)
#   notes SHA         print the release notes for a build made at this
#                     repository's commit SHA
#
# --setup defaults to setup.sh at the top of this repository. status needs gh
# and a GH_TOKEN that can read this repository's releases.

set -euo pipefail

die() { echo "pin-emulators: $*" >&2; exit 1; }

setup="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/setup.sh"
if [[ ${1:-} == --setup ]]; then
  [[ $# -ge 2 ]] || die "--setup needs a file"
  setup=$2; shift 2
fi
cmd=${1:-}; shift || true
[[ -f $setup ]] || die "can't read $setup"
repo="${GITHUB_REPOSITORY:-wr/macintosh-mini}"

settings() {
  sed -n \
    -e '/^MACEMU_REPO=/p' \
    -e '/^MACEMU_COMMIT=/p' \
    -e '/^# >>> emulator build settings/,/^# <<< emulator build settings/p' \
    -e '/^# >>> prebuilt emulators/,/^# <<< prebuilt emulators/p' \
    "$setup"
}
eval "$(settings)"
declare -F emulators_tag >/dev/null || die "no emulator build settings block in $setup"
tag=$(emulators_tag)

# The four downloads, as setup.sh names them.
assets() {
  local emu perf
  for emu in BasiliskII SheepShaver; do
    for perf in 0 1; do echo "$emu-perf$perf.gz"; done
  done
}

# The pins setup.sh would get from SUMS ("<sha>  <file>" lines), one
# "<asset> <sha>" per line, in assets order. Fails unless SUMS covers all four.
pins_from_sums() {
  local asset sha
  for asset in $(assets); do
    sha=$(awk -v f="$asset" '$2 == f || $2 == "*" f { print $1 }' "$1")
    [[ $sha =~ ^[0-9a-f]{64}$ ]] || die "$1 has no checksum for $asset"
    echo "$asset $sha"
  done
}

# The pins setup.sh has now, in the same form.
pins_in_setup() {
  local entry
  for entry in ${EMULATORS_SHA256[@]+"${EMULATORS_SHA256[@]}"}; do echo "$entry"; done
}

status() {
  local state sums
  state=$(gh release view "$tag" --repo "$repo" --json isDraft --jq .isDraft 2>/dev/null) || state=none
  # A draft is what a run that failed halfway leaves; publishing starts over.
  if [[ $state != false ]]; then echo build; return; fi
  sums=$(mktemp)
  gh release download "$tag" --repo "$repo" --pattern SHA256SUMS --output "$sums" --clobber ||
    die "release $tag has no SHA256SUMS"
  if [[ $EMULATORS_RELEASE == "$tag" && $(pins_in_setup) == "$(pins_from_sums "$sums")" ]]; then
    echo current
  else
    echo repin
  fi
  rm -f "$sums"
}

write() {
  [[ -f ${1:-} ]] || die "write needs a SHA256SUMS file"
  local pins block tmp
  pins=$(pins_from_sums "$1")
  block=$(
    echo "EMULATORS_RELEASE=\"$tag\""
    echo "EMULATORS_SHA256=("
    while read -r line; do echo "  \"$line\""; done <<<"$pins"
    echo ")"
  )
  tmp=$(mktemp)
  BLOCK=$block awk '
    /^# >>> prebuilt emulators/ { print; print ENVIRON["BLOCK"]; skip = 1; next }
    /^# <<< prebuilt emulators/ { skip = 0 }
    !skip { print }
  ' "$setup" > "$tmp"
  # Keep setup.sh's mode: copy over it rather than moving the temp file in.
  cat "$tmp" > "$setup"
  rm -f "$tmp"
}

notes() {
  local sha=${1:-} server=${GITHUB_SERVER_URL:-https://github.com} upstream emu perf name cflags configure
  [[ $sha =~ ^[0-9a-f]{40}$ ]] || die "notes needs this repository's 40-digit commit"
  upstream=${MACEMU_REPO%.git}
  cat <<EOF
Basilisk II and SheepShaver for the [macintosh-mini installer](https://github.com/$repo), built for Raspberry Pi OS 13 (Debian 13 "trixie"), 64-bit. The installer downloads the one it needs, checks it against the checksum pinned in \`setup.sh\`, and compiles on the Pi instead if anything doesn't match. There's nothing to do with these files by hand.

- **Source:** [${upstream#https://github.com/} at \`${MACEMU_COMMIT:0:8}\`]($upstream/tree/$MACEMU_COMMIT), the complete source code for these binaries.
- **Built by:** [\`.github/scripts/build-emulator.sh\`]($server/$repo/blob/$sha/.github/scripts/build-emulator.sh) with the settings in [\`setup.sh\`]($server/$repo/blob/$sha/setup.sh) at \`${sha:0:7}\`, in \`$EMULATORS_IMAGE\` on GitHub's arm64 runners${GITHUB_RUN_ID:+ ([this run]($server/$repo/actions/runs/$GITHUB_RUN_ID))}.
- **Checksums:** \`SHA256SUMS\`, the same ones \`setup.sh\` pins.

| File | Built with |
|---|---|
EOF
  for emu in BasiliskII SheepShaver; do
    for perf in 0 1; do
      if [[ $emu == BasiliskII ]]; then
        name="Basilisk II"; cflags=$BASILISK_CFLAGS; configure="${BASILISK_CONFIGURE[*]}"
      else
        name="SheepShaver"; cflags=$SHEEPSHAVER_CFLAGS; configure="${SHEEPSHAVER_CONFIGURE[*]}"
      fi
      if [[ $perf -eq 1 ]]; then cflags+=" $PERF_CFLAGS"; name+=", tuned for the Pi Zero 2 W (performance option on)"; fi
      echo "| \`$emu-perf$perf.gz\` | $name: \`CFLAGS=\"$cflags\"\`, \`$configure\` |"
    done
  done
  cat <<EOF

Basilisk II and SheepShaver are free software, released by their authors under the GNU General Public License, version 2 or (at your option) any later version. See \`COPYING\` in the source linked above.
EOF
}

case $cmd in
  settings) settings ;;
  tag) echo "$tag" ;;
  status) status ;;
  write) write "$@" ;;
  notes) notes "$@" ;;
  *) sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac
