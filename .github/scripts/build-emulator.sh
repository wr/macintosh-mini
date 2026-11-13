#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Builds one emulator the way setup.sh compiles it on the Pi, for CI to
# publish (see .github/workflows/emulators.yml), and checks the result.
#
# Usage: build-emulator.sh build <BasiliskII|SheepShaver> <perf 0|1> <outdir>
#        build-emulator.sh check <BasiliskII|SheepShaver> <perf 0|1> <outdir>
#   build  writes <outdir>/<Emulator>-perf<N>.gz and, for comparing configure's
#          findings with a Pi's, <outdir>/<Emulator>-perf<N>.config.h
#   check  installs only what a downloaded emulator gets on the Pi (labwc and
#          MACEMU_RUNTIME_PKGS), then checks that build's binary loads and runs
#
# Runs as root in a fresh EMULATORS_IMAGE (debian:trixie) container, with this
# repository mounted. Configure probes for mappable low memory, so the host
# needs vm.mmap_min_addr=0 first, as setup.sh sets it on the Pi.
#
# The flags and packages come from setup.sh's "emulator build settings"
# block. The steps below mirror setup.sh's prepare_build/prepare_basilisk_build
# and do_build/do_basilisk_build; when changing them in a way that changes the
# binaries, change setup.sh to match and bump EMULATORS_RECIPE_REV there.

set -euo pipefail

die() { echo "build-emulator: $*" >&2; exit 1; }

[[ $# -eq 4 ]] || die "usage: build-emulator.sh build|check <BasiliskII|SheepShaver> <0|1> <outdir>"
mode=$1 emu=$2 perf=$3 out=$4
[[ $emu == BasiliskII || $emu == SheepShaver ]] || die "unknown emulator: $emu"
[[ $perf == 0 || $perf == 1 ]] || die "perf must be 0 or 1"
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
eval "$("$here/pin-emulators.sh" --setup "$here/../../setup.sh" settings)"
asset="$emu-perf$perf.gz"
mkdir -p "$out"
out=$(cd "$out" && pwd)   # the build cds into the source

export DEBIAN_FRONTEND=noninteractive
apt_install() {
  apt-get update -qq
  apt-get install -y -qq "$@" >/dev/null
}

build() {
  apt_install ca-certificates git "${MACEMU_BUILD_PKGS[@]}"

  local src cflags
  src=$(mktemp -d)/macemu
  git init -q "$src"
  git -C "$src" fetch -q --depth 1 "$MACEMU_REPO" "$MACEMU_COMMIT"
  git -C "$src" checkout -q --detach FETCH_HEAD

  if [[ $emu == BasiliskII ]]; then
    cd "$src/BasiliskII/src/Unix"
    cflags=$BASILISK_CFLAGS
    [[ $perf -eq 1 ]] && cflags+=" $PERF_CFLAGS"
    CFLAGS="$cflags" CXXFLAGS="$cflags" ./autogen.sh "${BASILISK_CONFIGURE[@]}"
  else
    cd "$src/SheepShaver"
    make links
    cd src/Unix
    cflags=$SHEEPSHAVER_CFLAGS
    [[ $perf -eq 1 ]] && cflags+=" $PERF_CFLAGS"
    CFLAGS="$cflags" CXXFLAGS="$cflags" ./autogen.sh "${SHEEPSHAVER_CONFIGURE[@]}"
  fi
  make -j"$(nproc)"

  check_emulator "./$emu" || die "$emu doesn't run"
  gzip -n -9 -c "$emu" > "$out/$asset"
  cp config.h "$out/$emu-perf$perf.config.h"
  echo "built $out/$asset ($(stat -c %s "$out/$asset") bytes, $emu $(stat -c %s "$emu") bytes)"
}

check() {
  [[ -f $out/$asset ]] || die "no $out/$asset to check"
  apt_install labwc "${MACEMU_RUNTIME_PKGS[@]}"
  local dir
  dir=$(mktemp -d)
  gunzip -c "$out/$asset" > "$dir/$emu"
  chmod 755 "$dir/$emu"
  check_emulator "$dir/$emu" || die "$emu doesn't run with only the runtime packages"
  echo "$asset runs with only labwc and ${MACEMU_RUNTIME_PKGS[*]}"
}

case $mode in
  build) build ;;
  check) check ;;
  *) die "unknown mode: $mode" ;;
esac
