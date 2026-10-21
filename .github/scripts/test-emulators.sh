#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Tests for the prebuilt-emulator plumbing: the shared build settings in
# setup.sh, the Pi's "can I download?" check, and pin-emulators.sh.
#
# Usage: test-emulators.sh [setup.sh]
# Runs anywhere bash, sed and sha256sum do (CI, or a Mac). Changes nothing.

# The snippets passed to in_settings are expanded there, not here.
# shellcheck disable=SC2016

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
setup=${1:-$here/../../setup.sh}
pin="$here/pin-emulators.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

fails=0 passes=0
ok()   { passes=$((passes + 1)); echo "ok   $*"; }
fail() { fails=$((fails + 1)); echo "FAIL $*"; }
check() {  # check <name> <command...>
  local name=$1; shift
  if "$@"; then ok "$name"; else fail "$name"; fi
}
same() {  # same <name> <got> <want>
  if [[ $2 == "$3" ]]; then ok "$1"; else fail "$1: got '$2', want '$3'"; fi
}

# Everything setup.sh shares with CI, loaded the way CI loads it, in a
# subshell so each test starts clean. $1 = a setup.sh, then commands to run.
in_settings() {
  local file=$1; shift
  ( eval "$("$pin" --setup "$file" settings)" || exit 99; eval "$*" )
}

# --- The shared build settings -----------------------------------------------

tag=$(in_settings "$setup" emulators_tag)
check "tag looks like emulators-<commit7>-<recipe8> ($tag)" \
  grep -Eq '^emulators-[0-9a-f]{7}-[0-9a-f]{8}$' <<<"$tag"
same "tag is stable" "$(in_settings "$setup" emulators_tag)" "$tag"
commit=$(in_settings "$setup" 'echo $MACEMU_COMMIT')
same "tag starts with the pinned commit" "${tag:10:7}" "${commit:0:7}"

same "Basilisk II CFLAGS" "$(in_settings "$setup" 'echo "$BASILISK_CFLAGS"')" "-g -O3"
same "Basilisk II configure" "$(in_settings "$setup" 'echo "${BASILISK_CONFIGURE[*]}"')" \
  "--enable-sdl-video --enable-sdl-audio --disable-jit-compiler --enable-vosf --with-gtk=no"
same "SheepShaver CFLAGS" "$(in_settings "$setup" 'echo "$SHEEPSHAVER_CFLAGS"')" "-DMEM_BULK -g -O3"
same "SheepShaver configure" "$(in_settings "$setup" 'echo "${SHEEPSHAVER_CONFIGURE[*]}"')" "--with-gtk=no"
same "performance CFLAGS" "$(in_settings "$setup" 'echo "$PERF_CFLAGS"')" "-mcpu=cortex-a53 -mtune=cortex-a53"

# Any change to how the binaries are built must change the tag.
for change in 'BASILISK_CFLAGS="-g -O2"' 'SHEEPSHAVER_CONFIGURE=(--with-gtk=yes)' \
              'EMULATORS_RECIPE_REV=99' 'MACEMU_COMMIT=0000000000000000000000000000000000000000'; do
  other=$(in_settings "$setup" "$change; emulators_tag")
  check "changing ${change%%=*} changes the tag" test "$other" != "$tag"
done
# ...but the runtime packages don't: they change what's installed next to it.
same "changing MACEMU_RUNTIME_PKGS keeps the tag" \
  "$(in_settings "$setup" 'MACEMU_RUNTIME_PKGS=(foo); emulators_tag')" "$tag"

# --- The pins: does a Pi download, or compile? ---------------------------------

check "the pin helpers are defined" \
  in_settings "$setup" 'declare -F prebuilt_asset prebuilt_sha prebuilt_pinned >/dev/null'
shas='EMULATORS_SHA256=("BasiliskII-perf0.gz aaaa" "BasiliskII-perf1.gz bbbb" "SheepShaver-perf0.gz cccc")'
same "the asset follows PERF" "$(in_settings "$setup" 'PERF=1; prebuilt_asset BasiliskII')" "BasiliskII-perf1.gz"
same "the asset defaults to perf0" "$(in_settings "$setup" 'unset PERF; prebuilt_asset SheepShaver')" "SheepShaver-perf0.gz"
same "prebuilt_sha picks its line" "$(in_settings "$setup" "$shas; prebuilt_sha BasiliskII-perf1.gz")" "bbbb"
check "prebuilt_sha fails for a missing asset" \
  in_settings "$setup" "$shas; ! prebuilt_sha SheepShaver-perf1.gz"
check "no pins: compile" \
  in_settings "$setup" 'EMULATORS_RELEASE=""; EMULATORS_SHA256=(); ! prebuilt_pinned BasiliskII'
check "pins for this build: download" \
  in_settings "$setup" "$shas; EMULATORS_RELEASE=\$(emulators_tag); PERF=1; prebuilt_pinned BasiliskII"
check "pins for this build, but not this variant: compile" \
  in_settings "$setup" "$shas; EMULATORS_RELEASE=\$(emulators_tag); PERF=1; ! prebuilt_pinned SheepShaver"
check "pins for an older commit: compile" \
  in_settings "$setup" "$shas; EMULATORS_RELEASE=\$(MACEMU_COMMIT=1111111111111111111111111111111111111111 emulators_tag); ! prebuilt_pinned BasiliskII"
check "pins for older flags: compile" \
  in_settings "$setup" "$shas; EMULATORS_RELEASE=\$(BASILISK_CFLAGS=-O2 emulators_tag); ! prebuilt_pinned BasiliskII"

# --- pin-emulators.sh write ----------------------------------------------------

copy="$work/setup.sh"
cp "$setup" "$copy"
sums="$work/SHA256SUMS"
for f in BasiliskII-perf0 BasiliskII-perf1 SheepShaver-perf0 SheepShaver-perf1; do
  printf '%s  %s.gz\n' "$(printf '%s' "$f" | sha256sum | cut -c1-64)" "$f"
done > "$sums"
"$pin" --setup "$copy" write "$sums"
outside() { sed '/^# >>> prebuilt emulators/,/^# <<< prebuilt emulators/d' "$1"; }
check "write changes nothing outside the pin block" \
  cmp -s <(outside "$setup") <(outside "$copy")
same "write pins the current tag" "$(in_settings "$copy" 'echo "$EMULATORS_RELEASE"')" "$tag"
want=$(awk '$2 == "SheepShaver-perf1.gz" { print $1 }' "$sums")
same "write pins each checksum" "$(in_settings "$copy" 'prebuilt_sha SheepShaver-perf1.gz')" "$want"
for emu in BasiliskII SheepShaver; do
  for perf in 0 1; do
    check "after write, $emu perf=$perf downloads" \
      in_settings "$copy" "PERF=$perf; prebuilt_pinned $emu"
  done
done
cp "$copy" "$work/once"
"$pin" --setup "$copy" write "$sums"
check "writing the same pins twice is a no-op" cmp -s "$work/once" "$copy"
check "the pinned setup.sh still parses" bash -n "$copy"
grep -v SheepShaver-perf1 "$sums" > "$work/short"
check "write refuses SHA256SUMS missing a file" \
  bash -c '! "$1" --setup "$2" write "$3" 2>/dev/null' _ "$pin" "$copy" "$work/short"
check "a refused write leaves setup.sh alone" cmp -s "$work/once" "$copy"

echo
echo "$passes passed, $fails failed"
[[ $fails -eq 0 ]]
