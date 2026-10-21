#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Tests for the prebuilt-emulator plumbing: the shared build settings in
# setup.sh, the Pi's "can I download?" check, and pin-emulators.sh.
#
# Usage: test-emulators.sh [setup.sh]
# Runs anywhere bash, sed and sha256sum do (CI, or a Mac). Changes nothing.

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
  ( eval "$("$pin" settings "$file")" || exit 99; eval "$*" )
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

echo
echo "$passes passed, $fails failed"
[[ $fails -eq 0 ]]
