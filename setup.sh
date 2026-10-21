#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# macintosh-mini setup for a fresh Raspberry Pi Zero 2 W.
#
# Run on the Pi (or `curl … | bash`). Idempotent. Reboots at the end.
#
# Place a ROM and a disk image in $HOME before running:
#   BasiliskII  (68k, Mac OS 7):     512 KB or 1 MB 68k ROM
#   SheepShaver (PowerPC, OS 8.1+):  4 MB PPC ROM
# and a disk image: *.hda, *.dsk, *.img, *.hfv or *.sparsebundle
# (with no disk image, a new Basilisk II install offers to download ours).
#
# Flags (skip prompts):
#   --all | --all-basilisk | --maclock | --sheepshaver | --basilisk
#   --chime <name>      e.g. StartupMacII (default)
#   --color <mode>      Color | Grayscale | "Black & White"  (also accepts color/grayscale/bw)
#   --modelid <n>       BasiliskII modelid: 5 (Mac IIci, System 7.0-7.1) or 14 (Quadra, 7.5+/OS 8)
#   --disk <file>       disk image filename in $HOME (default: auto-discover)
#   --get-disk          with no disk image in $HOME, download our Mac OS 8.1
#                       disk for Basilisk II without asking (default: ask)
#   --rom <file>        ROM filename in $HOME (default: ROM)
#   --hostname <name>   default: leave unchanged
#   --perf | --no-perf  enable/disable performance optimizations (default: prompt)
#   --bluetooth | --no-bluetooth
#                       keep the on-board Bluetooth radio, or turn it off to
#                       save a second at boot (default: on; re-runs keep the
#                       installed choice)
#   --wifi-powersave | --no-wifi-powersave
#                       leave the wi-fi radio's power saving alone, or turn it
#                       off so the Pi stays reachable when idle (default: off)
#   --night-dim | --no-night-dim
#                       dim the screen from sunset to sunrise (default: prompt)
#   --night-off <t>     when the screen turns off at night: never, or HH:MM
#                       (default: prompt; 22:00 on a fresh install)
#   --timezone <zone>   Area/City for the sunrise schedule (default: keep, or
#                       prompt when the Pi is still on UTC)
#   --branch <name>     fetch the helper files from a branch other than main
#   --hotspot-setup     prepare this Mac for someone else, who sets up Wi-Fi from
#                       a phone instead of a network saved on the card. Installs
#                       without a ROM and names the Mac macintosh-mini-xxxx, then
#                       erases its saved Wi-Fi, SSH keys, login password and ROM
#                       and shuts down. On its next start it offers an open
#                       "Macintosh Mini XXXX" Wi-Fi network; joining it opens a
#                       page for Wi-Fi, a password and a ROM. Flash the card with
#                       the username "mac" first: the new owner keeps it.
#   --debug             show all command output instead of capturing to log

set -euo pipefail

REPO_BRANCH="main"   # --branch: test an unmerged branch on a real Pi
REPO_RAW="https://raw.githubusercontent.com/wr/macintosh-mini/$REPO_BRANCH"
VERSION="1.9.0"

# SheepShaver paths (DISK_IMAGE is auto-discovered or set via --disk)
DISK_IMAGE=""
ROM_FILE="ROM"
CHIME_FILE="chime.wav"
MACEMU_DIR="$HOME/macemu"
# kanjitalk755/macemu as of its PRs #321 (the Pi's address) and #322
# (AppleTalk-only tunnel), the UDP tunnel fixes that let the Mac print to
# an AirWriter and stay online.
MACEMU_REPO="https://github.com/kanjitalk755/macemu.git"
MACEMU_COMMIT="b9a71d7a4ef109ef3b0a218a37481af37aa2974a"
# What each installed emulator was built from (see needs_build).
BASILISK_STAMP=/usr/local/share/macintosh-mini/basilisk.commit
SHEEPSHAVER_STAMP=/usr/local/share/macintosh-mini/sheepshaver.commit
# Our clean Mac OS 8.1 disk for Basilisk II (disk-image/ in this repo), offered
# when $HOME has no disk image. Each version is a new file: pin all four.
DISK_DL_VERSION="2026.10"
DISK_DL_URL="https://archive.org/download/macos-8.1-basilisk-ii/macos-8.1-basilisk-ii-$DISK_DL_VERSION.zip"
DISK_DL_SHA256="ae16ea985bd3da7cf36c7f7ff092a04653fa2b20b9e2b5a794c1cf73216f2e8f"
DISK_DL_MB=52

# How both emulators are built, on the Pi and by CI: CI reads this block (and
# MACEMU_REPO/MACEMU_COMMIT above) from this file and builds the same way in
# .github/scripts/build-emulator.sh, so keep it self-contained.
# >>> emulator build settings >>>
MACEMU_BUILD_PKGS=(build-essential autoconf automake libtool pkg-config
  libsdl2-dev libgl1-mesa-dev libxkbcommon-dev libmpfr-dev)
MACEMU_RUNTIME_PKGS=(libsdl2-2.0-0 libmpfr6)   # what a downloaded build needs
BASILISK_CFLAGS="-g -O3"
# JIT is x86-only (interpreter on ARM). VOSF on: only changed screen regions
# get re-blitted — meaningfully snappier UI, and stable on this Pi's aarch64.
BASILISK_CONFIGURE=(--enable-sdl-video --enable-sdl-audio
  --disable-jit-compiler --enable-vosf --with-gtk=no)
SHEEPSHAVER_CFLAGS="-DMEM_BULK -g -O3"
SHEEPSHAVER_CONFIGURE=(--with-gtk=no)
PERF_CFLAGS="-mcpu=cortex-a53 -mtune=cortex-a53"   # added by the performance option
EMULATORS_IMAGE="debian:trixie"   # CI builds in this, to match Raspberry Pi OS 13
EMULATORS_RECIPE_REV=1   # bump when build-emulator.sh changes what it builds

# The release a matching download comes from. A hash of everything above that
# shapes the binaries (not the runtime packages), so a Pi only downloads what
# was built from exactly its pin and settings.
emulators_recipe() {
  printf '%s\n' "$MACEMU_REPO" "$MACEMU_COMMIT" "${MACEMU_BUILD_PKGS[*]}" \
    "$BASILISK_CFLAGS" "${BASILISK_CONFIGURE[*]}" "$SHEEPSHAVER_CFLAGS" \
    "${SHEEPSHAVER_CONFIGURE[*]}" "$PERF_CFLAGS" "$EMULATORS_IMAGE" \
    "$EMULATORS_RECIPE_REV" | sha256sum | cut -c1-8
}
emulators_tag() { echo "emulators-${MACEMU_COMMIT:0:7}-$(emulators_recipe)"; }

# An emulator binary is usable when every library it needs is there and it
# starts: both print their usage and exit on --help (SheepShaver opens SDL
# first, hence the dummy drivers, which need no screen or sound card).
check_emulator() {
  local out
  if ldd "$1" | grep 'not found'; then return 1; fi
  out=$(SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 30 "$1" --help 2>&1) ||
    { echo "$out" | tail -n 5; return 1; }
  grep -q 'Build Date' <<<"$out" || { echo "$out" | tail -n 5; return 1; }
}

# The download for emulator $1 (BasiliskII or SheepShaver) at the current
# performance setting, and its checksum from the pins below.
prebuilt_asset() { echo "$1-perf${PERF:-0}.gz"; }
prebuilt_sha() {
  local entry
  for entry in ${EMULATORS_SHA256[@]+"${EMULATORS_SHA256[@]}"}; do
    [[ ${entry%% *} == "$1" ]] && { echo "${entry#* }"; return 0; }
  done
  return 1
}
# Whether the pins are for exactly this build and cover emulator $1. After a
# change to the pin or the settings they aren't until CI re-pins, and the Pi
# compiles meanwhile.
prebuilt_pinned() {
  [[ $EMULATORS_RELEASE == "$(emulators_tag)" ]] &&
    prebuilt_sha "$(prebuilt_asset "$1")" >/dev/null
}
# <<< emulator build settings <<<

# The CI release to download the emulators from, and their checksums. Written
# by CI (.github/workflows/emulators.yml), never by hand.
# >>> prebuilt emulators >>>
EMULATORS_RELEASE="emulators-b9a71d7-d656fad2"
EMULATORS_SHA256=(
  "BasiliskII-perf0.gz b3ec933eff82aede27dfca85a0c61a6ed0927f994ed419d7f9deaae0c5f5dc2e"
  "BasiliskII-perf1.gz 1a453b6deef23b63a2d0b1572eb97a517dd7bde8db2d3655756f69a39786f907"
  "SheepShaver-perf0.gz 9830d332f04643c6b660c483055ca09d1f83bb37913c8a9d77797dc2b2f8e60f"
  "SheepShaver-perf1.gz 12e078d82fdbfb04007a464bd44c0102bef64f3ed376b8319be9b56603968a48"
)
# <<< prebuilt emulators <<<
EMULATORS_URL="https://github.com/wr/macintosh-mini/releases/download"

# tag (clean display name) | description | filename (without .wav)
CHIMES_DATA=(
  "Macintosh I|1984|StartupMacI"
  "Macintosh II|1987|StartupMacII"
  "Macintosh LC|1990|StartupMacLC"
  "Quadra|1991|StartupMacQuadra"
  "Quadra AV|1993|StartupMacQuadraAV"
  "Power Mac|1994|StartupPowerMac"
  "Power Mac PCI|variant|StartupPowerMacCard"
  "Twentieth Anniversary|1997|StartupTwentiethAnniversaryMac"
)
DEFAULT_CHIME_TAG="Macintosh II"
DEFAULT_CHIME="StartupMacII"

LOG_FILE=$(mktemp /tmp/macintosh-mini-setup.XXXXXX.log)
DEBUG=0

# --- Whiptail color theme --------------------------------------------------
# Black-and-white, after the System 7 Installer: gray desktop, white windows
# with black borders and titles, black-on-white buttons that invert when
# focused, a solid black progress bar. NEWT_COLORS wants colon-separated
# element=fg,bg pairs from newt's 16 named colors.
NEWT_THEME=(
  root=black,lightgray
  roottext=black,lightgray
  helpline=black,lightgray
  window=black,white
  border=black,white
  shadow=black,black
  title=black,white
  label=black,white
  textbox=black,white
  acttextbox=white,black
  entry=black,white
  disentry=lightgray,white
  checkbox=black,white
  actcheckbox=white,black
  listbox=black,white
  actlistbox=white,black
  sellistbox=white,black
  actsellistbox=white,black
  button=black,white
  actbutton=white,black
  compactbutton=black,white
  emptyscale=black,lightgray
  fullscale=white,black
)
export NEWT_COLORS=$(IFS=:; echo "${NEWT_THEME[*]}")

# --- Output helpers --------------------------------------------------------
log()  { printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

dump_log_on_failure() {
  printf '\n\033[1;31m--- last 80 lines of %s ---\033[0m\n' "$LOG_FILE"
  tail -n 80 "$LOG_FILE" || true
  printf '\033[1;31m--- end ---\033[0m\n\n'
  printf '(full log: %s)\n' "$LOG_FILE"
}

# --- Progress gauge --------------------------------------------------------
PROGRESS_FIFO=""
GAUGE_PID=""
GAUGE_NOTE="
This will take a while. Go make yourself a coffee :)
Your device will automatically reboot when finished."
USE_GAUGE=0
TOTAL_STEPS=1
CURRENT_STEP=0

start_gauge() {
  [[ $DEBUG -eq 1 ]] && return
  PROGRESS_FIFO=$(mktemp -u /tmp/macintosh-mini-progress.XXXXXX)
  mkfifo "$PROGRESS_FIFO"
  whiptail --backtitle "macintosh-mini" --title "Installing" \
    --gauge "$GAUGE_NOTE

Starting…" 11 72 0 < "$PROGRESS_FIFO" &
  GAUGE_PID=$!
  exec 9> "$PROGRESS_FIFO"
  USE_GAUGE=1
}

stop_gauge() {
  [[ $USE_GAUGE -eq 0 ]] && return
  exec 9>&- 2>/dev/null || true
  wait "$GAUGE_PID" 2>/dev/null || true
  [[ -n $PROGRESS_FIFO ]] && rm -f "$PROGRESS_FIFO"
  USE_GAUGE=0
}

emit_gauge() {
  local pct=$1 msg=$2
  [[ $USE_GAUGE -eq 1 ]] || return 0
  printf 'XXX\n%s\n%s\n\n%s\nXXX\n' "$pct" "$GAUGE_NOTE" "$msg" >&9
}

step_pct() { echo $(( CURRENT_STEP * 100 / TOTAL_STEPS )); }

# --- Run helpers -----------------------------------------------------------
# Quietly run a command/function; capture to LOG_FILE; on success advance the
# gauge, on failure dump the log and exit. With --debug, runs verbose.
run() {
  local label=$1; shift
  CURRENT_STEP=$((CURRENT_STEP + 1))
  if [[ $DEBUG -eq 1 ]]; then
    printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$label"
    "$@"
    return $?
  fi
  emit_gauge "$(step_pct)" "$label"
  local rc=0
  { "$@"; } >>"$LOG_FILE" 2>&1 || rc=$?
  if [[ $rc -ne 0 ]]; then
    stop_gauge
    printf '\n\033[1;31m✗ Failed:\033[0m %s\n' "$label"
    dump_log_on_failure
    exit "$rc"
  fi
}

# Like run, but a failure is logged and handed back instead of ending the install.
try_run() {
  local label=$1; shift
  CURRENT_STEP=$((CURRENT_STEP + 1))
  if [[ $DEBUG -eq 1 ]]; then
    printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$label"
    "$@"
    return $?
  fi
  emit_gauge "$(step_pct)" "$label"
  local rc=0
  { "$@"; } >>"$LOG_FILE" 2>&1 || rc=$?
  [[ $rc -eq 0 ]] || echo "--- $label: didn't work (exit $rc), carrying on" >>"$LOG_FILE"
  return $rc
}

# Like run but updates the gauge message every 30s with elapsed time.
run_long() {
  local label=$1; shift
  CURRENT_STEP=$((CURRENT_STEP + 1))
  if [[ $DEBUG -eq 1 ]]; then
    printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$label"
    "$@"
    return $?
  fi
  emit_gauge "$(step_pct)" "$label"
  ( "$@" >>"$LOG_FILE" 2>&1 ) &
  local pid=$! start=$SECONDS
  while kill -0 "$pid" 2>/dev/null; do
    sleep 30
    if kill -0 "$pid" 2>/dev/null; then
      local elapsed=$(( (SECONDS - start) / 60 ))
      emit_gauge "$(step_pct)" "$label  (${elapsed}m elapsed)"
    fi
  done
  local rc=0
  wait "$pid" || rc=$?
  if [[ $rc -ne 0 ]]; then
    stop_gauge
    printf '\n\033[1;31m✗ Failed:\033[0m %s\n' "$label"
    dump_log_on_failure
    exit "$rc"
  fi
}

# --- Whiptail helpers ------------------------------------------------------
ensure_whiptail() {
  command -v whiptail >/dev/null 2>&1 && return
  log "Installing whiptail (required for menus)"
  ensure_sudo
  sudo apt-get update -qq
  sudo apt-get install -y whiptail
}

wt_menu() {
  # Args: [--nocancel], title, prompt, default_tag, list_height, then tag/label
  # pairs. --nocancel drops the Cancel button (use when an Exit item in the
  # list already covers leaving, so the button isn't a redundant duplicate).
  local nocancel=""
  [[ $1 == --nocancel ]] && { nocancel=--nocancel; shift; }
  local title=$1 prompt=$2 default=$3 list_height=$4
  shift 4
  local extra=8; [[ -z $prompt ]] && extra=7
  # One row per line of prompt as whiptail shows it, long lines wrapped
  local rows; rows=$(printf '%s\n' "$prompt" | fold -s -w 74 | wc -l)
  extra=$(( extra + rows - 1 ))
  local total_height=$(( list_height + extra ))
  # Never taller than the screen: whiptail centres the box, so a taller one
  # starts above the top and hides its title and buttons. A long prompt (the
  # update's what's new) then scrolls instead (Tab to it, then the arrow keys).
  local screen_rows scroll=""
  screen_rows=$(stty size </dev/tty 2>/dev/null) && screen_rows=${screen_rows%% *}
  [[ $screen_rows =~ ^[0-9]+$ ]] || screen_rows=${LINES:-24}
  local max_height=$(( screen_rows - 2 ))   # the backtitle row, and the box's shadow
  (( max_height < list_height + 7 )) && max_height=$(( list_height + 7 ))
  if (( total_height > max_height )); then
    total_height=$max_height
    scroll=--scrolltext
  fi
  whiptail --backtitle "macintosh-mini" --title "$title" $nocancel $scroll \
    --default-item "$default" \
    --menu "$prompt" "$total_height" 78 "$list_height" \
    "$@" 3>&1 1>&2 2>&3 </dev/tty
}

wt_input() {
  local title=$1 prompt=$2 default=$3
  whiptail --backtitle "macintosh-mini" --title "$title" \
    --inputbox "$prompt" 10 70 "$default" \
    3>&1 1>&2 2>&3 </dev/tty
}

# --- Asset sanity check ----------------------------------------------------
# Disk images either emulator opens: a raw image under any of these names, or
# an Apple .sparsebundle (a directory). Not .vhd: the emulators read it only
# when built with libvhd, which these builds aren't. Sets DISKS.
DISK_TYPES=".hda, .dsk, .img, .hfv or .sparsebundle"
find_disks() {
  shopt -s nullglob
  DISKS=("$HOME"/*.{hda,dsk,img,hfv,sparsebundle})
  shopt -u nullglob
}

# Verify ROM and at least one disk image exist in $HOME. Idempotent —
# safe to call multiple times.
check_sheepshaver_assets() {
  [[ -f "$HOME/.sheepshaver_prefs" ]] && return 0   # existing install -> update, keep config
  if [[ $HOTSPOT_SETUP -ne 1 ]]; then   # --hotspot-setup: the new owner adds the ROM
    [[ -f "$HOME/$ROM_FILE" ]] || die "Missing $HOME/$ROM_FILE — copy it over before running"
    local rom_size; rom_size=$(wc -c < "$HOME/$ROM_FILE")
    if [[ $rom_size -eq 524288 || $rom_size -eq 1048576 ]]; then
      die "ROM is $rom_size bytes (a 68k ROM) — SheepShaver needs the 4 MB PowerPC ROM"
    fi
  fi
  if [[ -n $DISK_IMAGE ]]; then
    [[ -e "$HOME/$DISK_IMAGE" ]] || die "Missing $HOME/$DISK_IMAGE (passed via --disk)"
  else
    find_disks
    [[ ${#DISKS[@]} -gt 0 ]] || die "No disk image ($DISK_TYPES) found in $HOME — copy one over before running"
  fi
}

# Verify a 68k ROM exists for BasiliskII, and the disk passed with --disk. The
# 68k ROM is 512 KB or 1 MB; reject the 4 MB PPC ROM, a common mix-up.
check_basilisk_assets() {
  [[ -f "$HOME/.basilisk_ii_prefs" ]] && return 0   # existing install -> update, keep config
  if [[ $HOTSPOT_SETUP -ne 1 ]]; then   # --hotspot-setup: the new owner adds the ROM
    [[ -f "$HOME/$ROM_FILE" ]] || die "Missing $HOME/$ROM_FILE — copy a 68k Mac ROM over before running"
    local rom_size
    rom_size=$(wc -c < "$HOME/$ROM_FILE")
    if [[ $rom_size -ne 524288 && $rom_size -ne 1048576 ]]; then
      die "ROM is $rom_size bytes — BasiliskII needs a 512 KB or 1 MB 68k ROM, not the 4 MB PowerPC ROM"
    fi
  fi
  if [[ -n $DISK_IMAGE ]]; then
    [[ -e "$HOME/$DISK_IMAGE" ]] || die "Missing $HOME/$DISK_IMAGE (passed via --disk)"
  fi
  # No disk image is fine: the disk step offers to download ours.
}

# Download our Mac OS 8.1 disk into $HOME and set DISK_IMAGE. The download and
# the unzip use hidden names find_disks never picks up, so nothing lands in
# $HOME unless every check passes. On failure, DISK_DL_ERROR says why.
get_disk_image() {
  local hda="macos-8.1-basilisk-ii-$DISK_DL_VERSION.hda"
  local part="$HOME/.macos-8.1-basilisk-ii.zip.part" tmp free need rc=0
  rm -rf "$HOME"/.macos-8.1-basilisk-ii.*   # left by an interrupted try
  need=$(( DISK_DL_MB + 1024 + 100 ))       # the zip, the 1 GB disk, room to spare
  free=$(df -Pm "$HOME" | awk 'NR == 2 { print $4 }')
  if [[ -z $free || $free -lt $need ]]; then
    DISK_DL_ERROR="it needs $need MB free and there's ${free:-?} MB"
    return 1
  fi
  tmp=$(mktemp -d "$HOME/.macos-8.1-basilisk-ii.XXXXXX") || {
    DISK_DL_ERROR="couldn't make a folder for it in $HOME"; return 1; }
  # Stopped part-way (Ctrl-C), don't leave up to 1 GB behind in hidden files.
  # shellcheck disable=SC2064  # expanded now: the paths are this function's locals
  trap "rm -rf $(printf %q "$tmp") $(printf %q "$part"); exit 130" INT TERM HUP
  printf 'Downloading Mac OS 8.1 (%s MB)…\n' "$DISK_DL_MB"
  if ! curl -fL --retry 3 --connect-timeout 20 --speed-limit 1024 --speed-time 60 \
       --progress-bar -o "$part" "$DISK_DL_URL"; then
    DISK_DL_ERROR="the download didn't finish"; rc=1
  elif ! echo "$DISK_DL_SHA256  $part" | sha256sum -c --status -; then
    DISK_DL_ERROR="the download is damaged (its checksum doesn't match)"; rc=1
  elif ! printf 'Unpacking it (a minute or two)…\n' ||
       ! python3 -m zipfile -e "$part" "$tmp" || [[ ! -f $tmp/$hda ]]; then
    DISK_DL_ERROR="it didn't unzip"; rc=1
  elif ! mv "$tmp/$hda" "$HOME/$hda"; then
    DISK_DL_ERROR="it couldn't be moved into $HOME"; rc=1
  else
    DISK_IMAGE=$hda
  fi
  rm -rf "$tmp" "$part"
  trap - INT TERM HUP
  return $rc
}

# With no disk image in $HOME: ask (or, with --get-disk, don't) and download
# ours. Returns non-zero when there's still no disk.
offer_disk_image() {
  local msg
  if [[ $GET_DISK -ne 1 ]]; then
    msg="There's no disk image in your home folder."
    msg+=$'\n\n'"Download a ready-to-use Mac OS 8.1 disk? It's a clean install set up for this Mac, with a web browser and After Dark. Version $DISK_DL_VERSION, $DISK_DL_MB MB, from the Internet Archive."
    msg+=$'\n\n'"Or choose No and copy your own disk image over first."
    whiptail --backtitle "macintosh-mini" --title "Disk image" \
      --yes-button "Download" --no-button "No" --yesno "$msg" 14 72 </dev/tty || return 1
  fi
  get_disk_image && return 0
  warn "Couldn't download the disk image: $DISK_DL_ERROR."
  return 1
}

# `macintosh` command: boot/reboot the Mac on the display (re-triggers the tty1
# autologin -> ~/.profile -> launcher chain). Works from the console or SSH.
write_macintosh_cmd() {
  sudo tee /usr/local/bin/macintosh >/dev/null <<'MAC'
#!/bin/bash
exec sudo systemctl restart getty@tty1
MAC
  sudo chmod 755 /usr/local/bin/macintosh
}

# Boot preflight: confirm a ROM + disk are present (auto-fill prefs if exactly
# one candidate of each exists), else explain on-screen instead of failing blind.
write_preflight() {
  sudo tee /usr/local/bin/mac-preflight >/dev/null <<'PREFLIGHT'
#!/bin/bash
# Usage: mac-preflight basilisk|sheepshaver. Exit 0 = ready to boot,
# 2 = only the ROM is missing.
case $1 in
  basilisk)    prefs=$HOME/.basilisk_ii_prefs; sizes="524288 1048576" ;;
  sheepshaver) prefs=$HOME/.sheepshaver_prefs; sizes="4194304" ;;
  *) echo "mac-preflight: unknown emulator '$1'" >&2; exit 1 ;;
esac
get() { sed -n "s/^$1 //p" "$prefs" 2>/dev/null | head -1; }
abs() { case $1 in /*) printf '%s' "$1" ;; ?*) printf '%s/%s' "$HOME" "$1" ;; esac; }
rom=$(abs "$(get rom)"); disk=$(abs "$(get disk)")
[ -f "$rom" ] && [ -e "$disk" ] && exit 0
roms=(); for f in "$HOME"/*; do [ -f "$f" ] && for s in $sizes; do [ "$(stat -c%s "$f")" = "$s" ] && roms+=("$f"); done; done
shopt -s nullglob
disks=( "$HOME"/*.{hda,dsk,img,hfv,sparsebundle} )
shopt -u nullglob
set_pref() { grep -q "^$1 " "$prefs" 2>/dev/null && sed -i "s#^$1 .*#$1 $2#" "$prefs" || printf '%s %s\n' "$1" "$2" >> "$prefs"; }
if [ ${#roms[@]} -eq 1 ] && [ ${#disks[@]} -eq 1 ]; then
  set_pref rom "${roms[0]}"; set_pref disk "${disks[0]}"; exit 0
fi
# Only the ROM missing: exit 2, and the launcher shows the Wi-Fi setup
# screen, whose ROM page can add one from a phone or computer.
if [ ! -f "$rom" ] && [ ${#roms[@]} -eq 0 ] && [ -x /usr/local/bin/mac-setup ]; then
  if [ -e "$disk" ] || [ ${#disks[@]} -eq 1 ]; then
    [ -e "$disk" ] || set_pref disk "${disks[0]}"
    exit 2
  fi
fi
clear 2>/dev/null
echo
echo "  The Macintosh can't start yet."
[ ${#roms[@]} -eq 0 ]  && echo "  - No ROM found in $HOME."
[ ${#roms[@]} -gt 1 ]  && echo "  - ${#roms[@]} ROMs in $HOME - set one in $prefs (rom <file>)."
[ ${#disks[@]} -eq 0 ] && echo "  - No disk image found in $HOME (.hda/.dsk/.img/.hfv/.sparsebundle)."
[ ${#disks[@]} -gt 1 ] && echo "  - ${#disks[@]} disk images in $HOME - set one in $prefs (disk <file>)."
echo
echo "  Fix that, then run:  macintosh"
echo
exit 1
PREFLIGHT
  sudo chmod 755 /usr/local/bin/mac-preflight
}

# Four hex digits from the Pi's serial number: the end of the hostname
# --hotspot-setup picks and of the setup hotspot's name. mac_setup.py works it
# out the same way. Not the Wi-Fi MAC: NetworkManager randomises that while
# scanning.
setup_suffix() {
  local s
  s=$(tr -d '\0' < /sys/firmware/devicetree/base/serial-number 2>/dev/null)
  [[ ${#s} -ge 4 ]] || s=$(cat /etc/machine-id)
  s=${s,,}
  printf '%s' "${s: -4}"
}

# The ROM the installed emulator's prefs point at, as an absolute path, or
# nothing. Safe under `set -e -o pipefail` when a prefs file is missing.
installed_rom_path() {
  local prefs=$HOME/.basilisk_ii_prefs rom
  [[ $INSTALL_SHEEPSHAVER -eq 1 ]] && prefs=$HOME/.sheepshaver_prefs
  rom=$(sed -n 's/^rom //p' "$prefs" 2>/dev/null | head -1) || true
  [[ -n $rom && $rom != /* ]] && rom=$HOME/$rom
  printf '%s' "$rom"
}

# --- Sudo bootstrap --------------------------------------------------------
ensure_sudo() {
  if sudo -n true 2>/dev/null; then return; fi
  log "Enabling passwordless sudo for $USER (one-time, kiosk setup)"
  sudo -v || die "sudo authentication failed"
  sudo tee "/etc/sudoers.d/010-${USER}-nopasswd" >/dev/null <<EOF
$USER ALL=(ALL) NOPASSWD:ALL
EOF
  sudo chmod 440 "/etc/sudoers.d/010-${USER}-nopasswd"
  sudo visudo -c -f "/etc/sudoers.d/010-${USER}-nopasswd" >/dev/null \
    || die "sudoers file failed validation"
}

# --- Argument parsing ------------------------------------------------------
INSTALL_MACLOCK=0
INSTALL_SHEEPSHAVER=0
INSTALL_BASILISK=0
CHIME_NAME=""
COLOR_MODE=""
MODELID=""   # BasiliskII only: 5 (Mac IIci) or 14 (Quadra)
NEW_HOSTNAME=""
PERF=""   # "" = prompt, 1 = on, 0 = off
BLUETOOTH=""   # "" = installed choice or on, 1 = on, 0 = off
WIFI_POWERSAVE=0   # 0 = turn the radio's power saving off, 1 = leave it alone
NIGHT_DIM=""       # "" = prompt, 1 = dim the screen at night, 0 = don't
NIGHT_OFF=""       # "" = prompt, "never", or HH:MM to turn the screen off
TIMEZONE=""        # Area/City to set; the night schedule needs a real one
NIGHT_CONF=/etc/default/brightness-control
HOTSPOT_SETUP=0    # 1 = --hotspot-setup: prepare the Mac for phone setup
GET_DISK=0         # 1 = --get-disk: download our disk without asking

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)           INSTALL_MACLOCK=1; INSTALL_SHEEPSHAVER=1; shift ;;
    --all-basilisk)  INSTALL_MACLOCK=1; INSTALL_BASILISK=1; shift ;;
    --maclock)       INSTALL_MACLOCK=1; shift ;;
    --sheepshaver)   INSTALL_SHEEPSHAVER=1; shift ;;
    --basilisk)      INSTALL_BASILISK=1; shift ;;
    --chime)         CHIME_NAME=$2; shift 2 ;;
    --color)         COLOR_MODE=$2; shift 2 ;;
    --modelid)       MODELID=$2; shift 2 ;;
    --disk)          DISK_IMAGE=$2; shift 2 ;;
    --get-disk)      GET_DISK=1; shift ;;
    --rom)           ROM_FILE=$2; shift 2 ;;
    --hostname)      NEW_HOSTNAME=$2; shift 2 ;;
    --perf)          PERF=1; shift ;;
    --no-perf)       PERF=0; shift ;;
    --bluetooth)     BLUETOOTH=1; shift ;;
    --no-bluetooth)  BLUETOOTH=0; shift ;;
    --wifi-powersave)    WIFI_POWERSAVE=1; shift ;;
    --no-wifi-powersave) WIFI_POWERSAVE=0; shift ;;
    --night-dim)     NIGHT_DIM=1; shift ;;
    --no-night-dim)  NIGHT_DIM=0; shift ;;
    --night-off)     NIGHT_OFF=$2; shift 2 ;;
    --timezone)      TIMEZONE=$2; shift 2 ;;
    --hotspot-setup) HOTSPOT_SETUP=1; shift ;;
    --branch)        REPO_BRANCH=$2; REPO_RAW="https://raw.githubusercontent.com/wr/macintosh-mini/$REPO_BRANCH"; shift 2 ;;
    --debug)         DEBUG=1; shift ;;
    *) die "Unknown option: $1" ;;
  esac
done

# A Mac prepared for phone setup gets Basilisk II and the Maclock hardware
# unless the command says otherwise.
if [[ $HOTSPOT_SETUP -eq 1 && $INSTALL_MACLOCK -eq 0 && $INSTALL_SHEEPSHAVER -eq 0 \
      && $INSTALL_BASILISK -eq 0 ]]; then
  INSTALL_MACLOCK=1; INSTALL_BASILISK=1
fi

# --- Header ---------------------------------------------------------------
printf '\033[1;35m╔═ macintosh-mini installer v%s ═╗\033[0m\n' "$VERSION"
printf '  log: %s%s\n' "$LOG_FILE" "$([[ $DEBUG -eq 1 ]] && echo '  [debug mode: verbose]' || echo '')"

[[ "$(uname -m)" == "aarch64" ]] || warn "Not aarch64 ($(uname -m)) — guide is tested on Pi Zero 2 W aarch64"

# Pre-flight asset check — bail out before any sudo prompt or apt install
# if an emulator was requested via flag but its ROM/disk is missing.
[[ $INSTALL_SHEEPSHAVER -eq 1 ]] && check_sheepshaver_assets
[[ $INSTALL_BASILISK    -eq 1 ]] && check_basilisk_assets

ensure_sudo
ensure_whiptail

if [[ $HOTSPOT_SETUP -eq 1 ]]; then
  ho_msg="This prepares the Mac for someone else to set up from their phone."
  ho_msg+=$'\n\n'"When it's done it erases this Mac's saved Wi-Fi, SSH keys, login password and ROM, then shuts down. You can't log in again until it has been set up from a phone."
  if [[ $USER != mac ]]; then
    ho_msg+=$'\n\n'"Your username is \"$USER\", and the new owner will keep it. Flash the card with the username \"mac\" to avoid that."
  fi
  whiptail --backtitle "macintosh-mini" --title "Prepare for phone setup" --defaultno \
    --yes-button "Continue" --no-button "Cancel" --yesno "$ho_msg" 17 72 </dev/tty || die "Cancelled"
fi

# --- Existing install? -----------------------------------------------------
# The installer records what it set up so a re-run knows it is an update.
# Installs before 1.3.0 left no record, so fall back to what is on disk.
INSTALL_STATE=/etc/macintosh-mini.conf
state_get() { { sed -n "s/^$1=//p" "$INSTALL_STATE" | head -1; } 2>/dev/null || true; }
INSTALLED_VERSION=$(state_get VERSION)
INSTALLED_MACLOCK=$(state_get MACLOCK)
INSTALLED_EMULATOR=$(state_get EMULATOR)
INSTALLED_PERF=$(state_get PERF)
INSTALLED_BLUETOOTH=$(state_get BLUETOOTH)
if [[ -z $INSTALLED_VERSION ]]; then
  [[ -f /etc/systemd/system/brightness-control.service ]] && INSTALLED_MACLOCK=1
  grep -qsF "# >>> basilisk-autostart >>>" "$HOME/.profile" && INSTALLED_EMULATOR=basilisk
  grep -qsF "# >>> sheepshaver-autostart >>>" "$HOME/.profile" && INSTALLED_EMULATOR=sheepshaver
  grep -qs "fsck.mode=skip" /boot/firmware/cmdline.txt && INSTALLED_PERF=1
fi

# Print the CHANGELOG.md bullet lines added since the installed version, as
# compact "New in <ver>:" blocks for the update menu. CHANGELOG.md in the repo
# is the source of truth. Best-effort: prints nothing if offline, missing, or
# unparseable, so the caller just shows the menu without a what's-new section.
changelog_since() {
  local from=${1:-} md v versions show=()
  md=$(curl -fsSL --retry 2 "$REPO_RAW/CHANGELOG.md" 2>/dev/null) || return 0
  [[ -n $md ]] || return 0
  versions=$(printf '%s\n' "$md" | sed -n 's/^## \[\([0-9][0-9.]*\)\].*/\1/p')
  [[ -n $versions ]] || return 0
  while IFS= read -r v; do
    [[ -n $v ]] || continue
    # skip anything newer than what we are installing…
    [[ "$v" != "$VERSION" && "$(printf '%s\n%s\n' "$v" "$VERSION" | sort -V | tail -1)" == "$v" ]] && continue
    # …and anything at or older than what is already installed.
    if [[ -n $from ]]; then
      [[ "$v" == "$from" ]] && continue
      [[ "$(printf '%s\n%s\n' "$v" "$from" | sort -V | tail -1)" == "$from" ]] && continue
    fi
    show+=("$v")
  done <<< "$versions"
  [[ ${#show[@]} -gt 0 ]] || return 0
  for v in "${show[@]}"; do
    printf 'New in %s:\n' "$v"
    printf '%s\n' "$md" | awk -v ver="$v" '
      $0 ~ "^## \\[" ver "\\]" {p=1; next}
      p && /^## \[/ {exit}
      p && /^- / {print}
    '
  done
}

UPDATE_MODE=""   # "" = fresh install or flags given, quick = keep settings
# An existing install with no flags is an update. Detect it here so the fresh
# menu and prefs prompts below skip; the update menu itself is shown later (at
# the reconfigure step), once the emulator settings editor it opens is defined.
IS_UPDATE=0
if [[ $INSTALL_MACLOCK -eq 0 && $INSTALL_SHEEPSHAVER -eq 0 && $INSTALL_BASILISK -eq 0 \
      && ( -n $INSTALLED_MACLOCK || -n $INSTALLED_EMULATOR ) ]]; then
  IS_UPDATE=1
  [[ $INSTALLED_MACLOCK == 1 ]] && INSTALL_MACLOCK=1
  case "$INSTALLED_EMULATOR" in
    basilisk)    INSTALL_BASILISK=1 ;;
    sheepshaver) INSTALL_SHEEPSHAVER=1 ;;
  esac
fi

# --- Whiptail prompts ------------------------------------------------------
if [[ $INSTALL_MACLOCK -eq 0 && $INSTALL_SHEEPSHAVER -eq 0 && $INSTALL_BASILISK -eq 0 ]]; then
  # Single-column menu (label = tag, blank item).
  opt_full="Basilisk II + Maclock hardware (default)"
  opt_ppc="SheepShaver + Maclock hardware (laggy)"
  opt_hw="Maclock hardware only"
  opt_b2="Basilisk II only"
  opt_ss="SheepShaver only"
  CHOICE=$(wt_menu "Macintosh Mini Installer v$VERSION" "" "$opt_full" 5 \
    "$opt_full" "" \
    "$opt_ppc" "" \
    "$opt_hw" "" \
    "$opt_b2" "" \
    "$opt_ss" "") || die "Cancelled"
  case "$CHOICE" in
    "$opt_full") INSTALL_MACLOCK=1; INSTALL_BASILISK=1 ;;
    "$opt_ppc")  INSTALL_MACLOCK=1; INSTALL_SHEEPSHAVER=1 ;;
    "$opt_hw")   INSTALL_MACLOCK=1 ;;
    "$opt_b2")   INSTALL_BASILISK=1 ;;
    "$opt_ss")   INSTALL_SHEEPSHAVER=1 ;;
    *)           die "Cancelled" ;;
  esac
  # User just chose an emulator via the menu — re-check assets now.
  [[ $INSTALL_SHEEPSHAVER -eq 1 ]] && check_sheepshaver_assets
  [[ $INSTALL_BASILISK    -eq 1 ]] && check_basilisk_assets
fi

# An existing prefs file means re-running is an update / core switch: keep the
# user's prefs and skip the disk/chime/color prompts that only feed them.
NEED_PREFS=0
[[ $INSTALL_BASILISK    -eq 1 && ! -f $HOME/.basilisk_ii_prefs ]] && NEED_PREFS=1
[[ $INSTALL_SHEEPSHAVER -eq 1 && ! -f $HOME/.sheepshaver_prefs ]] && NEED_PREFS=1

# Disk image — auto-discover in $HOME (see find_disks), prompt if multiple,
# use as-is.
if [[ ($INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1) && -z $DISK_IMAGE && $NEED_PREFS -eq 1 ]]; then
  find_disks
  HDA_PATHS=("${DISKS[@]}")
  if [[ ${#HDA_PATHS[@]} -eq 0 ]]; then
    # Our disk is Mac OS 8.1 for Basilisk II as a Quadra; SheepShaver doesn't get the offer.
    if [[ $INSTALL_BASILISK -eq 1 && $INSTALL_SHEEPSHAVER -eq 0 ]] && offer_disk_image; then
      [[ ${MODELID:-14} -ne 14 ]] && warn "Mac OS 8.1 needs a Quadra: using modelid 14, not $MODELID"
      MODELID=14
    else
      die "No disk image ($DISK_TYPES) found in $HOME — copy one over before running"
    fi
  elif [[ ${#HDA_PATHS[@]} -eq 1 ]]; then
    DISK_IMAGE=$(basename "${HDA_PATHS[0]}")
  else
    WT_ARGS=()
    for p in "${HDA_PATHS[@]}"; do
      WT_ARGS+=("$(basename "$p")" "$(du -sh "$p" | cut -f1)")
    done
    DISK_IMAGE=$(wt_menu "Disk image" "Multiple disk images in \$HOME — pick one:" \
      "$(basename "${HDA_PATHS[0]}")" "${#HDA_PATHS[@]}" "${WT_ARGS[@]}") \
      || die "Cancelled"
  fi
fi

# Chime — show clean tags, resolve to filename via lookup
if [[ ($INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1) && -z $CHIME_NAME && $NEED_PREFS -eq 1 ]]; then
  WT_ARGS=()
  for entry in "${CHIMES_DATA[@]}"; do
    IFS='|' read -r tag desc _ <<< "$entry"
    WT_ARGS+=("$tag" "$desc")
  done
  CHIME_TAG=$(wt_menu "Boot chime" "Which startup chime?" "$DEFAULT_CHIME_TAG" 8 \
    "${WT_ARGS[@]}") || die "Cancelled"
  for entry in "${CHIMES_DATA[@]}"; do
    IFS='|' read -r tag _ filename <<< "$entry"
    if [[ "$tag" == "$CHIME_TAG" ]]; then
      CHIME_NAME=$filename
      break
    fi
  done
fi
[[ -z $CHIME_NAME ]] && CHIME_NAME=$DEFAULT_CHIME
[[ -n ${CHIME_TAG:-} ]] && printf '%s\n' "$CHIME_TAG" > "$HOME/.macintosh_chime"

# Color — BasiliskII defaults to 8-bit (lighter), SheepShaver to 16-bit.
if [[ ($INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1) && -z $COLOR_MODE && $NEED_PREFS -eq 1 ]]; then
  color_default="Color"
  [[ $INSTALL_BASILISK -eq 1 ]] && color_default="Grayscale"
  COLOR_MODE=$(wt_menu "Color mode" "Color depth:" "$color_default" 3 \
    "Color"          "16-bit" \
    "Grayscale"      "8-bit" \
    "Black & White"  "1-bit") || die "Cancelled"
fi
[[ -z $COLOR_MODE ]] && COLOR_MODE="Color"

case "$COLOR_MODE" in
  "Color"|color)                COLOR_DEPTH=16; COLOR_LABEL="Color" ;;
  "Grayscale"|grayscale)        COLOR_DEPTH=8;  COLOR_LABEL="Grayscale" ;;
  "Black & White"|bw)           COLOR_DEPTH=1;  COLOR_LABEL="Black & White" ;;
  *) die "Invalid color mode: $COLOR_MODE" ;;
esac

# Mac model (BasiliskII only) — modelid 5 (Mac IIci) is right for System 7.0/7.1.
# System 7.5+ and Mac OS 8 need modelid 14 (Quadra; the IIci's 68030 isn't
# supported there). Most people install 7.5+, so default to 14.
if [[ $INSTALL_BASILISK -eq 1 && -z $MODELID && $NEED_PREFS -eq 1 ]]; then
  MODELID_TAG=$(wt_menu "Mac model" "Which Mac OS will you boot?" "Quadra (14)" 2 \
    "Quadra (14)"   "System 7.5+ / Mac OS 8" \
    "Mac IIci (5)"  "System 7.0 / 7.1") || die "Cancelled"
  case "$MODELID_TAG" in
    "Mac IIci (5)") MODELID=5 ;;
    "Quadra (14)")  MODELID=14 ;;
  esac
fi
[[ -z $MODELID ]] && MODELID=14
case "$MODELID" in
  5|14) ;;
  *) die "Invalid modelid: $MODELID (must be 5 or 14)" ;;
esac

# Era-matched crash sound for the chosen chime.
crash_for_chime() {
  case "$1" in
    StartupMacI|StartupMacII)              echo "CrashMacII" ;;
    StartupMacLC)                          echo "CrashMacLC" ;;
    StartupMacQuadra)                      echo "CrashMacQuadra" ;;
    StartupMacQuadraAV)                    echo "CrashMacQuadraAV" ;;
    StartupPowerMac|StartupPowerMacCard)   echo "CrashMacQuadraAV" ;;
    StartupTwentiethAnniversaryMac)        echo "CrashMacQuadraAV" ;;
    *)                                     echo "CrashMacII" ;;
  esac
}
CRASH_NAME=$(crash_for_chime "$CHIME_NAME")

# --- Reconfigure an existing install ---------------------------------------
# When prefs already exist for the chosen emulator, offer to keep them or
# change individual settings in place (instead of silently keeping them).
pref_get() { sed -n "s/^$2 //p" "$1" 2>/dev/null | head -1; }
pref_set() {
  if grep -q "^$2 " "$1" 2>/dev/null; then sed -i "s#^$2 .*#$2 $3#" "$1"
  else printf '%s %s\n' "$2" "$3" >> "$1"; fi
}

reconf_disk() {   # $1=prefs  $2=is_basilisk
  local img p; local args=() paths=()
  find_disks
  paths=("${DISKS[@]}")
  if [[ ${#paths[@]} -eq 0 ]]; then
    whiptail --backtitle "macintosh-mini" --msgbox "No disk image in $HOME — copy one over first." 8 64 </dev/tty
    return 0
  fi
  for p in "${paths[@]}"; do args+=("$(basename "$p")" "$(du -sh "$p" | cut -f1)"); done
  img=$(wt_menu "Disk image" "Pick the disk to boot:" "$(basename "${paths[0]}")" "${#paths[@]}" "${args[@]}") || return 0
  if [[ $2 -eq 1 ]]; then pref_set "$1" disk "$HOME/$img"; else pref_set "$1" disk "$img"; fi
}

reconf_color() {  # $1=prefs  $2=is_basilisk
  local mode depth
  mode=$(wt_menu "Color depth" "Color depth:" "Color" 3 \
    "Color" "16-bit" "Grayscale" "8-bit" "Black & White" "1-bit") || return 0
  case "$mode" in "Color") depth=16 ;; "Grayscale") depth=8 ;; "Black & White") depth=1 ;; esac
  if [[ $2 -eq 1 ]]; then pref_set "$1" displaycolordepth "$depth"
  else sed -i "s#^\(screen .*\)/[0-9]*\$#\1/$depth#" "$1"; fi
}

reconf_modelid() {  # $1=prefs (BasiliskII only)
  local tag id
  tag=$(wt_menu "Mac model" "Which Mac OS will you boot?" "Quadra (14)" 2 \
    "Quadra (14)"   "System 7.5+ / Mac OS 8" \
    "Mac IIci (5)"  "System 7.0 / 7.1") || return 0
  case "$tag" in
    "Mac IIci (5)") id=5 ;;
    "Quadra (14)")  id=14 ;;
    *) return 0 ;;
  esac
  pref_set "$1" modelid "$id"
}

# AppleTalk on the network: AppleTalk goes through Basilisk II's UDP tunnel,
# where printers (an AirWriter, say) and other Macs on the network hear it, and
# everything else through slirp, so the Mac stays online.
appletalk_on() { [[ $(pref_get "$1" udptunnel) == true && $(pref_get "$1" udpappletalkonly) == true ]]; }

reconf_appletalk() {  # $1=prefs (BasiliskII only)
  local cur=Off pick
  appletalk_on "$1" && cur=On
  pick=$(wt_menu "AppleTalk" "" "$cur" 2 \
    "On"  "AppleTalk printers and file sharing on your network, plus the internet" \
    "Off" "The internet only") || return 0
  if [[ $pick == On ]]; then
    pref_set "$1" udptunnel true
    pref_set "$1" udpport 6066
    pref_set "$1" udpappletalkonly true
  else
    pref_set "$1" udptunnel false
    pref_set "$1" udpappletalkonly false
  fi
}

reconf_chime() {
  local tag name="" crash entry t d f; local args=()
  for entry in "${CHIMES_DATA[@]}"; do IFS='|' read -r t d _ <<< "$entry"; args+=("$t" "$d"); done
  tag=$(wt_menu "Boot chime" "Which startup chime?" "$DEFAULT_CHIME_TAG" 8 "${args[@]}") || return 0
  for entry in "${CHIMES_DATA[@]}"; do IFS='|' read -r t _ f <<< "$entry"; [[ "$t" == "$tag" ]] && name=$f; done
  [[ -n $name ]] || return 0
  printf '%s\n' "$tag" > "$HOME/.macintosh_chime"
  crash=$(crash_for_chime "$name")
  curl -fL --retry 3 -o "$HOME/$CHIME_FILE" "$REPO_RAW/emulators/chimes/${name}.wav" \
    && sudo install -m644 "$HOME/$CHIME_FILE" /usr/local/bin/chime.wav
  curl -fL --retry 3 -o "$HOME/crash.wav" "$REPO_RAW/emulators/chimes/${crash}.wav" \
    && sudo install -m644 "$HOME/crash.wav" /usr/local/bin/crash.wav
  return 0
}

configure_existing() {  # $1=prefs  $2=is_basilisk
  local prefs=$1 isb=$2 cur_disk cur_depth cur_chime cur_color cur_modelid cur_model cur_atalk pick
  while true; do
    cur_disk=$(basename "$(pref_get "$prefs" disk)" 2>/dev/null)
    if [[ $isb -eq 1 ]]; then cur_depth=$(pref_get "$prefs" displaycolordepth)
    else cur_depth=$(pref_get "$prefs" screen | sed 's#.*/##'); fi
    cur_chime=$(cat "$HOME/.macintosh_chime" 2>/dev/null || true)
    case "${cur_depth:-}" in
      16) cur_color="Color 16-bit" ;;
      8)  cur_color="Grayscale 8-bit" ;;
      1)  cur_color="Black & White 1-bit" ;;
      *)  cur_color="${cur_depth:-?}-bit" ;;
    esac
    # Each row edits its setting in place (applied immediately). Select = edit
    # the highlighted setting; Back = return to the previous menu.
    if [[ $isb -eq 1 ]]; then
      cur_modelid=$(pref_get "$prefs" modelid)
      case "${cur_modelid:-}" in
        5)  cur_model="Mac IIci (5) — System 7.0/7.1" ;;
        14) cur_model="Quadra (14) — System 7.5+ / OS 8" ;;
        *)  cur_model="modelid ${cur_modelid:-?}" ;;
      esac
      cur_atalk=Off; appletalk_on "$prefs" && cur_atalk=On
      pick=$(whiptail --backtitle "macintosh-mini" --title "Emulator Settings" \
          --ok-button "Select" --cancel-button "Back" --menu "" 14 72 5 \
          "Disk image:"    "${cur_disk:-unknown}" \
          "Startup chime:" "${cur_chime:-—}" \
          "Color depth:"   "$cur_color" \
          "Mac model:"     "$cur_model" \
          "AppleTalk:"     "$cur_atalk" \
          3>&1 1>&2 2>&3 </dev/tty) || break
    else
      pick=$(whiptail --backtitle "macintosh-mini" --title "Emulator Settings" \
          --ok-button "Select" --cancel-button "Back" --menu "" 12 72 3 \
          "Disk image:"    "${cur_disk:-unknown}" \
          "Startup chime:" "${cur_chime:-—}" \
          "Color depth:"   "$cur_color" \
          3>&1 1>&2 2>&3 </dev/tty) || break
    fi
    case "$pick" in
      "Disk image:")    reconf_disk    "$prefs" "$isb" || true ;;
      "Startup chime:") reconf_chime                   || true ;;
      "Color depth:")   reconf_color   "$prefs" "$isb" || true ;;
      "Mac model:")     reconf_modelid "$prefs"        || true ;;
      "AppleTalk:")     reconf_appletalk "$prefs"      || true ;;
    esac
  done
}

if [[ $IS_UPDATE -eq 1 ]]; then
  # The update's main menu. "Edit settings" opens the emulator settings editor
  # as a modal (its Back returns here); "Update to version X" proceeds, keeping
  # every other setting. Cancel/Esc exits. What's new is folded into the prompt
  # (wt_menu grows the box per newline) so it's on the first screen.
  opt_up="Update to version $VERSION"
  opt_edit="Edit settings"
  up_prompt="Version ${INSTALLED_VERSION:-1.2.0 or earlier} is installed."
  up_news=$(changelog_since "$INSTALLED_VERSION")
  [[ -n $up_news ]] && up_prompt="$up_prompt"$'\n\n'"$up_news"
  while true; do
    CHOICE=$(wt_menu "Macintosh Mini Installer v$VERSION" \
      "$up_prompt" "$opt_up" 2 \
      "$opt_up"   "" \
      "$opt_edit" "") || exit 0
    case "$CHOICE" in
      "$opt_up") break ;;
      "$opt_edit")
        if   [[ $INSTALL_BASILISK    -eq 1 ]]; then configure_existing "$HOME/.basilisk_ii_prefs" 1
        elif [[ $INSTALL_SHEEPSHAVER -eq 1 ]]; then configure_existing "$HOME/.sheepshaver_prefs" 0
        else whiptail --backtitle "macintosh-mini" --title "Edit settings" \
               --msgbox "No editable settings for a hardware-only install." 8 60 </dev/tty || true
        fi ;;
      *) exit 0 ;;
    esac
  done
  UPDATE_MODE=quick   # keep every other setting at its installed value
  [[ -z $PERF ]] && PERF=${INSTALLED_PERF:-0}
  [[ -z $NEW_HOSTNAME ]] && NEW_HOSTNAME=$(hostname)
elif [[ $NEED_PREFS -eq 0 && $INSTALL_BASILISK -eq 1 ]]; then
  configure_existing "$HOME/.basilisk_ii_prefs" 1
elif [[ $NEED_PREFS -eq 0 && $INSTALL_SHEEPSHAVER -eq 1 ]]; then
  configure_existing "$HOME/.sheepshaver_prefs" 0
fi

# Bluetooth: on unless asked otherwise. No prompt — a re-run keeps what the
# last run recorded. Before 1.5.0 the perf option turned Bluetooth off as a
# side effect and recorded nothing, so those installs get it back.
[[ -z $BLUETOOTH ]] && BLUETOOTH=${INSTALLED_BLUETOOTH:-1}

# Performance optimizations
if [[ -z $PERF ]]; then
  def=Yes; [[ ${INSTALLED_PERF:-1} == 0 ]] && def=No
  PERF_CHOICE=$(wt_menu "Performance Optimizations" "" "$def" 2 \
    "Yes"  "Faster — more RAM, fewer background services" \
    "No"   "Stock install") || die "Cancelled"
  case "$PERF_CHOICE" in Yes) PERF=1 ;; No) PERF=0 ;; esac
fi

# Hostname
CUR_HOSTNAME=$(hostname)
[[ $HOTSPOT_SETUP -eq 1 && -z $NEW_HOSTNAME ]] && NEW_HOSTNAME="macintosh-mini-$(setup_suffix)"
if [[ -z $NEW_HOSTNAME ]]; then
  NEW_HOSTNAME=$(wt_input "Hostname" "Pi hostname (leave as-is to skip):" "$CUR_HOSTNAME") \
    || die "Cancelled"
fi
NEW_HOSTNAME=${NEW_HOSTNAME// /-}

# Night dimming (maclock only). Sunset to sunrise the backlight runs at half
# the dial level and goes dark from NIGHT_OFF_AT; see brightness_control.py.
# The script takes its location from the timezone, so a Pi still on UTC gets
# a picker like raspi-config's. A re-run defaults to whatever the last run chose.
conf_get() { { sed -n "s/^$1=//p" "$NIGHT_CONF" | head -1; } 2>/dev/null || true; }

current_timezone() {
  local tz
  tz=$(timedatectl show -p Timezone --value 2>/dev/null) || tz=$(cat /etc/timezone 2>/dev/null) || true
  # Etc/* zones (UTC, GMT+5 ...) have no city, so no place to compute a
  # sunrise for
  case "$tz" in ""|UTC|Universal|GMT|Etc/*) return 1 ;; esac
  printf '%s' "$tz"
}

pick_timezone() {
  # zone.tab, not zone1970.tab: the latter folds Oslo, Stockholm, Amsterdam
  # and a hundred others into one zone each, and nobody will find their
  # city under Berlin. raspi-config reads the same table.
  local tab=/usr/share/zoneinfo/zone.tab
  [[ -f $tab ]] || tab=/usr/share/zoneinfo/zone1970.tab
  [[ -f $tab ]] || die "No tzdata zone table at /usr/share/zoneinfo"
  local areas=() cities=() item area city
  while read -r item; do areas+=("$item" ""); done \
    < <(awk -F'\t' '!/^#/ { split($3, p, "/"); print p[1] }' "$tab" | sort -u)
  area=$(wt_menu "Timezone" "Pick your area:" "${areas[0]}" 12 "${areas[@]}") \
    || return 1
  while read -r item; do cities+=("$item" ""); done \
    < <(awk -F'\t' -v a="$area/" '!/^#/ && index($3, a) == 1 { print substr($3, length(a) + 1) }' "$tab" | sort)
  city=$(wt_menu "Timezone" "Pick the nearest city in $area:" "${cities[0]}" 14 "${cities[@]}") \
    || return 1
  TIMEZONE="$area/$city"
}

if [[ -n $TIMEZONE && ! -f /usr/share/zoneinfo/$TIMEZONE ]]; then
  die "Unknown timezone: $TIMEZONE (see: timedatectl list-timezones)"
fi
if [[ -n $NIGHT_OFF && ! $NIGHT_OFF =~ ^(never|([01][0-9]|2[0-3]):[0-5][0-9])$ ]]; then
  die "--night-off takes 'never' or HH:MM, not '$NIGHT_OFF'"
fi
if [[ $INSTALL_MACLOCK -eq 1 && $UPDATE_MODE != quick ]]; then
  if [[ -z $NIGHT_DIM ]]; then
    # Stock Pi OS images ship Europe/London, so a zone that looks set may
    # not be. Show it and offer the picker either way.
    tz=${TIMEZONE:-$(current_timezone || echo "not set")}
    yes_tag="Yes (timezone: $tz)"
    cur=No; [[ $(conf_get NIGHT_DIM) == 1 ]] && cur=$yes_tag
    NIGHT_CHOICE=$(wt_menu "Night Dimming" \
      "Do you want your screen to dim automatically from sunset to sunrise?
Useful if your Macintosh Mini is a desk accessory or display piece." "$cur" 3 \
      "$yes_tag"          "" \
      "Update timezone"   "" \
      "No"                "") || die "Cancelled"
    case "$NIGHT_CHOICE" in
      "Yes"*)            NIGHT_DIM=1 ;;
      "Update timezone") NIGHT_DIM=1; pick_timezone || die "Cancelled" ;;
      No)                NIGHT_DIM=0 ;;
    esac
  fi
  # The schedule needs a real zone: UTC has no reference city
  if [[ $NIGHT_DIM -eq 1 && -z $TIMEZONE ]] && ! current_timezone >/dev/null; then
    pick_timezone || die "Cancelled"
  fi
  if [[ $NIGHT_DIM -eq 1 && -z $NIGHT_OFF ]]; then
    # A hand-edited time that is not one of the presets gets its own entry,
    # so pressing Enter keeps it
    off_now=$(conf_get NIGHT_OFF_AT); keep=()
    case "$off_now" in
      21:00) cur="9 PM" ;;  22:00) cur="10 PM" ;;  23:00) cur="11 PM" ;;
      00:00) cur="12 AM" ;; 01:00) cur="1 AM" ;;
      "") if grep -q '^NIGHT_OFF_AT=$' "$NIGHT_CONF" 2>/dev/null; then cur=Never; else cur="10 PM"; fi ;;
      *) cur="Keep $off_now"; keep=("$cur" "") ;;
    esac
    OFF_CHOICE=$(wt_menu "Night Dimming" "Do you want your screen to turn off at night?
(It comes back on 1 hour before sunrise.)" "$cur" $(( 6 + ${#keep[@]} / 2 )) \
      "Never" "" "9 PM" "" "10 PM" "" "11 PM" "" "12 AM" "" "1 AM" "" ${keep[@]+"${keep[@]}"}) || die "Cancelled"
    case "$OFF_CHOICE" in
      Keep*)   NIGHT_OFF=$off_now ;;
      Never)   NIGHT_OFF=never ;;
      "9 PM")  NIGHT_OFF=21:00 ;;
      "10 PM") NIGHT_OFF=22:00 ;;
      "11 PM") NIGHT_OFF=23:00 ;;
      "12 AM") NIGHT_OFF=00:00 ;;
      "1 AM")  NIGHT_OFF=01:00 ;;
    esac
  fi
fi


# An emulator binary needs (re)building when it is missing or was built against
# GTK. With GTK, every WarningAlert (e.g. slirp finding no DNS server while
# offline) is a modal dialog the kiosk can't dismiss — `nogui true` doesn't
# cover alerts in the SDL build. Builds are now configured --with-gtk=no so
# alerts go to the journal instead; a GTK-linked binary from an older install
# gets rebuilt once on update. It is also rebuilt when its stamp file ($2)
# is missing or holds another line than emu_build: built from another macemu
# commit, or with the performance option set the other way.
needs_build() {
  [[ -x $1 ]] || return 0
  [[ $(cat "$2" 2>/dev/null) != "$(emu_build)" ]] && return 0
  ldd "$1" 2>/dev/null | grep -q libgtk
}

# How the emulators are built, as one line for the stamp files: the macemu
# commit, and whether the performance option added -mcpu=cortex-a53.
emu_build() { echo "$MACEMU_COMMIT perf=${PERF:-0}"; }

# Written only once the binary is in place: a failed build retries next run.
record_build() {
  sudo mkdir -p "$(dirname "$1")" && emu_build | sudo tee "$1" >/dev/null
}

# Whether emulator $1 can be downloaded instead of compiled: CI builds for
# Raspberry Pi OS 13 (Debian trixie), 64-bit, only.
prebuilt_available() {
  [[ $(dpkg --print-architecture 2>/dev/null) == arm64 ]] || return 1
  # shellcheck source=/dev/null
  [[ $(. /etc/os-release 2>/dev/null && echo "${VERSION_CODENAME:-}") == trixie ]] || return 1
  prebuilt_pinned "$1"
}

# Download emulator $1 from CI's release, check it, install it and record the
# build in stamp $2. A download that fails any check is never installed.
install_prebuilt() {
  local asset sha dir rc=0
  asset=$(prebuilt_asset "$1") && sha=$(prebuilt_sha "$asset") || return 1
  dir=$(mktemp -d) || return 1
  # Time limits, so a stalled download falls back to compiling within about
  # five minutes, retries included, instead of hanging (2.5 MB in 150 s needs
  # only ~17 KB/s).
  { curl -fsSL --retry 3 --retry-max-time 150 --connect-timeout 20 --max-time 150 \
      -o "$dir/$asset" "$EMULATORS_URL/$EMULATORS_RELEASE/$asset" &&
    echo "$sha  $dir/$asset" | sha256sum -c - &&
    gunzip -c "$dir/$asset" > "$dir/$1" && chmod 755 "$dir/$1" &&
    check_emulator "$dir/$1" &&
    sudo install -m755 "$dir/$1" "/usr/local/bin/$1" &&
    record_build "$2"; } || rc=1
  rm -rf "$dir"
  return $rc
}

# Compiling needs these; only Pis that compile install them.
install_build_tools() { sudo apt-get install -y "${MACEMU_BUILD_PKGS[@]}"; }

# Steps to get emulator $1 in place: none when it's current, one to download
# it, or the compile's six (build tools, fetch, configure, build, install,
# record). $2 = its binary, $3 = its stamp.
EMU_BUILD_STEPS=6
emu_steps() {
  if ! needs_build "$2" "$3"; then echo 0
  elif prebuilt_available "$1"; then echo 1
  else echo "$EMU_BUILD_STEPS"
  fi
}

# Clone macemu if needed and check out MACEMU_COMMIT, whatever the clone
# tracked before (installs before 1.8.0 cloned kanjitalk755 HEAD).
checkout_macemu() {
  [[ -d $MACEMU_DIR/.git ]] || git clone "$MACEMU_REPO" "$MACEMU_DIR" || return $?
  git -C "$MACEMU_DIR" remote set-url origin "$MACEMU_REPO" || return $?
  git -C "$MACEMU_DIR" fetch origin "$MACEMU_COMMIT" || return $?
  git -C "$MACEMU_DIR" checkout --detach -f "$MACEMU_COMMIT"
}

# --- Total step count (for gauge) -----------------------------------------
TOTAL_STEPS=4   # apt update, apt install, patch_cmdline, record_install
[[ $WIFI_POWERSAVE -eq 0 ]] && TOTAL_STEPS=$((TOTAL_STEPS+1))
[[ -n $NEW_HOSTNAME && $NEW_HOSTNAME != "$CUR_HOSTNAME" ]] && TOTAL_STEPS=$((TOTAL_STEPS+1))
[[ -n $TIMEZONE ]] && TOTAL_STEPS=$((TOTAL_STEPS+1))
[[ $INSTALL_MACLOCK -eq 1 ]] && TOTAL_STEPS=$((TOTAL_STEPS+7))
if [[ $INSTALL_SHEEPSHAVER -eq 1 ]]; then
  TOTAL_STEPS=$((TOTAL_STEPS + 8 + $(emu_steps SheepShaver /usr/local/bin/SheepShaver "$SHEEPSHAVER_STAMP")))
fi
if [[ $INSTALL_BASILISK -eq 1 ]]; then
  TOTAL_STEPS=$((TOTAL_STEPS + 8 + $(emu_steps BasiliskII /usr/local/bin/BasiliskII "$BASILISK_STAMP")))
fi
[[ $PERF -eq 1 ]] && TOTAL_STEPS=$((TOTAL_STEPS+2))
TOTAL_STEPS=$((TOTAL_STEPS+1))   # bluetooth
[[ $INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1 ]] && TOTAL_STEPS=$((TOTAL_STEPS+1))   # Wi-Fi setup

# --- Open the gauge --------------------------------------------------------
start_gauge
trap 'stop_gauge' EXIT

# --- Hostname change ------------------------------------------------------
if [[ -n $NEW_HOSTNAME && $NEW_HOSTNAME != "$CUR_HOSTNAME" ]]; then
  set_host() {
    sudo hostnamectl set-hostname "$NEW_HOSTNAME" || return $?
    # Collapse every 127.0.1.1 line into a single one carrying the new name.
    # Matching on the old hostname instead would append a second line whenever
    # /etc/hosts and the running hostname disagree, which is exactly what
    # cloud-init leaves behind.
    local tmp; tmp=$(mktemp)
    awk -v name="$NEW_HOSTNAME" '
      /^127\.0\.1\.1[ \t]/ { if (!seen++) print "127.0.1.1\t" name; next }
      { print }
      END { if (!seen) print "127.0.1.1\t" name }
    ' /etc/hosts > "$tmp"
    # Never copy a short write over /etc/hosts: losing it breaks localhost
    # resolution and every later sudo on a machine with no console.
    if [[ -s $tmp ]] && grep -qE "^127\.0\.1\.1[[:space:]]" "$tmp"; then
      sudo cp "$tmp" /etc/hosts
    fi
    rm -f "$tmp"

    # Current Pi OS images ship cloud-init, which rewrites the hostname from
    # its own cached config on every boot and puts the old name straight back.
    # Tell it to leave the hostname alone.
    [[ -f /etc/cloud/cloud.cfg ]] || return 0
    sudo install -d /etc/cloud/cloud.cfg.d
    printf '# Hostname is set locally; do not let cloud-init reset it each boot.\npreserve_hostname: true\n' \
      | sudo tee /etc/cloud/cloud.cfg.d/99-preserve-hostname.cfg >/dev/null

    # cloud-init also regenerates /etc/hosts when manage_etc_hosts is on, which
    # re-adds the old short name as an alias. That setting comes from the image's
    # user-data, which outranks anything dropped in cloud.cfg.d, so switch the
    # module off instead.
    if grep -qE '^[[:space:]]*-[[:space:]]+update_etc_hosts[[:space:]]*$' /etc/cloud/cloud.cfg; then
      [[ -f /etc/cloud/cloud.cfg.orig ]] \
        || sudo cp /etc/cloud/cloud.cfg /etc/cloud/cloud.cfg.orig
      sudo sed -i -E 's|^([[:space:]]*)-[[:space:]]+update_etc_hosts[[:space:]]*$|\1# - update_etc_hosts   # disabled by macintosh-mini: /etc/hosts is managed locally|' \
        /etc/cloud/cloud.cfg
    fi
  }
  run "Setting hostname: $CUR_HOSTNAME → $NEW_HOSTNAME" set_host
fi

# --- Timezone -------------------------------------------------------------
if [[ -n $TIMEZONE ]]; then
  run "Setting timezone: $TIMEZONE" sudo timedatectl set-timezone "$TIMEZONE"
fi

# --- apt packages ---------------------------------------------------------
APT_PKGS=(curl git iw qrencode dnsmasq-base)
if [[ $INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1 ]]; then
  APT_PKGS+=(
    "${MACEMU_RUNTIME_PKGS[@]}"
    labwc wlr-randr seatd
    alsa-utils
  )
fi
if [[ $INSTALL_MACLOCK -eq 1 ]]; then
  APT_PKGS+=(python3-lgpio device-tree-compiler unzip)
fi
run "Updating apt index" sudo apt-get update
run "Installing ${#APT_PKGS[@]} apt packages" sudo apt-get install -y "${APT_PKGS[@]}"

# --- Quiet boot -----------------------------------------------------------
# Ensure each kernel arg is present. Idempotent per-token so re-running on an
# existing install adds anything new instead of bailing the moment one old
# token is found. cmdline.txt is a single line. Display rotation is handled
# entirely at the device-tree level (config.txt overlay rotate=90 -> DRM
# panel-orientation, which rotates fbcon too), so there is no video= arg here.
patch_cmdline() {
  local f=/boot/firmware/cmdline.txt t
  local tokens=(
    quiet
    loglevel=0
    vt.global_cursor_default=0
    console=tty3
    logo.nologo
    systemd.show_status=0
  )
  # #24 briefly put a video=…rotate=270 arg on main to rotate the console.
  # Rotation now comes from the device-tree panel-orientation (which also rotates
  # fbcon), so strip that arg — left in place it double-rotates the console
  # against rotate=90. Harmless no-op on 1.3.0 installs, which never had it.
  sudo sed -i 's| video=DPI-1:480x640M@60,rotate=270||g' "$f"
  for t in "${tokens[@]}"; do
    grep -qF -- "$t" "$f" || sudo sed -i "s|\$| $t|" "$f"
  done
}
run "Configuring quiet boot (cmdline.txt)" patch_cmdline

# Shared labwc kiosk config, written when an emulator launcher is
# installed. rc.xml strips the titlebar for the emulator windows; mac-session
# runs one emulator and lets `labwc -S` terminate the compositor when it exits.
write_labwc_kiosk() {
  mkdir -p "$HOME/.config/labwc"
  # Single-app kiosk: force every window fullscreen and undecorated. Fullscreen
  # gives the emulator exclusive pointer focus so it hides the host cursor —
  # otherwise the compositor cursor and the guest (Mac) cursor both show. "*"
  # matches all windows, so this doesn't depend on the emulator's WM_CLASS.
  cat > "$HOME/.config/labwc/rc.xml" <<'XML'
<?xml version="1.0"?>
<labwc_config>
  <windowRules>
    <windowRule identifier="*" serverDecoration="no" matchOnce="true">
      <action name="ToggleFullscreen"/>
    </windowRule>
  </windowRules>
</labwc_config>
XML
  sudo tee /usr/local/bin/mac-session >/dev/null <<'SESSION'
#!/bin/sh
# labwc session command: labwc -S "mac-session <tag> <bin> <exitfile>".
# labwc exits when this returns. Rotation is meant to come from the DRM
# panel-orientation (config.txt overlay rotate=90), which labwc applies before
# the first frame — no flash. Only if the panel came up un-rotated (overlay
# ignored rotate=) do we fall back to a one-shot wlr-randr transform; that
# reintroduces the brief flash, so it is only a safety net. Target the DPI
# panel connector by name — never a stray output — so an emulator-only install
# on some other display (e.g. HDMI) is left alone.
tag=$1; bin=$2; exitfile=$3
if wlr-randr 2>/dev/null | grep -q "Transform: normal"; then
  for o in DPI-1 Unknown-1; do
    wlr-randr --output "$o" --transform 270 2>/dev/null && break
  done
fi
systemd-cat -t "$tag" setarch -R "$bin"
echo $? > "$exitfile"
SESSION
  sudo chmod 755 /usr/local/bin/mac-session

  # Hide labwc's own pointer cursor. The emulator draws the Mac cursor into its
  # framebuffer, so the compositor cursor is a second, redundant arrow — and it
  # shows for the moment before the emulator maps. Install a cursor theme whose
  # every shape is a 1x1 transparent image and point XCURSOR at it (launchers
  # set XCURSOR_THEME=transparent only on the labwc command, not exported), so
  # labwc renders nothing; the Mac cursor lives in the emulator's surface and is
  # unaffected. Nothing else on the system selects this theme, so a desktop or
  # the fallback shell keeps its normal cursor. This relies on the emulator
  # being the only window labwc ever shows: the builds use --with-gtk=no so
  # emulator alerts log to the journal instead of opening a (pointer-less)
  # dialog.
  local cdir="$HOME/.local/share/icons/transparent/cursors"
  mkdir -p "$cdir"
  base64 -d > "$cdir/left_ptr" <<'CUR'
WGN1chAAAAAAAAEAAQAAAAIA/f8BAAAAHAAAACQAAAACAP3/AQAAAAEAAAABAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAA=
CUR
  local n
  for n in default arrow top_left_arrow left_ptr_watch watch xterm text \
           hand1 hand2 pointer fleur crosshair sb_h_double_arrow sb_v_double_arrow; do
    ln -sf left_ptr "$cdir/$n"
  done
  cat > "$HOME/.local/share/icons/transparent/index.theme" <<'IDX'
[Icon Theme]
Name=transparent
Comment=Invisible cursor for kiosk
IDX
}

# --- Wi-Fi power saving ---------------------------------------------------
# The radio parks itself when nothing is talking to it, so the Pi drops off the
# network while idle and takes a while to answer again. Turn that off three
# ways: a NetworkManager default, the saved wi-fi profile, and a boot-time unit
# for anything NetworkManager does not manage. Applied live with iw as well, so
# it takes effect without restarting NetworkManager and dropping this session.
if [[ $WIFI_POWERSAVE -eq 0 ]]; then
  disable_wifi_powersave() {
    sudo install -d /etc/NetworkManager/conf.d
    printf '[connection]\nwifi.powersave = 2\n' \
      | sudo tee /etc/NetworkManager/conf.d/99-wifi-powersave-off.conf >/dev/null

    # Match on UUID, not name: nmcli's terse output escapes a colon in a
    # profile name as \:, which splits wrong on -F: and drops the profile, and
    # two profiles can share a name but never a UUID.
    local uuid
    while IFS= read -r uuid; do
      [[ -n $uuid ]] || continue
      sudo nmcli connection modify "$uuid" 802-11-wireless.powersave 2 || true
    done < <(nmcli -t -f UUID,TYPE connection show 2>/dev/null \
             | awk -F: '$2 == "802-11-wireless" { print $1 }')

    sudo tee /etc/systemd/system/wifi-powersave-off.service >/dev/null <<'UNIT'
[Unit]
Description=Disable Wi-Fi power saving
Wants=sys-subsystem-net-devices-wlan0.device
After=sys-subsystem-net-devices-wlan0.device NetworkManager.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=-/usr/sbin/iw dev wlan0 set power_save off

[Install]
WantedBy=multi-user.target
UNIT
    sudo systemctl daemon-reload
    sudo systemctl enable wifi-powersave-off.service
    sudo systemctl restart wifi-powersave-off.service
  }
  run "Turning off Wi-Fi power saving" disable_wifi_powersave
fi

# --- Performance optimizations -------------------------------------------
if [[ $PERF -eq 1 ]]; then
  patch_cmdline_perf() {
    local f=/boot/firmware/cmdline.txt
    grep -q 'fsck.mode=skip' "$f" && return 0
    sudo sed -i 's|$| fsck.mode=skip noswap|' "$f"
  }
  run "[perf] cmdline: skip fsck, no swap" patch_cmdline_perf

  mask_services() {
    local services=(
      systemd-networkd-wait-online.service
      triggerhappy.service
      ModemManager.service
      cups.service
      cups-browsed.service
      apt-daily.service
      apt-daily.timer
      apt-daily-upgrade.service
      apt-daily-upgrade.timer
      man-db.timer
      logrotate.timer
      e2scrub_all.timer
      fstrim.timer
      dphys-swapfile.service
    )
    for s in "${services[@]}"; do
      sudo systemctl mask "$s" 2>/dev/null || true
    done
  }
  run "[perf] Masking unused services" mask_services
fi

# --- Bluetooth -------------------------------------------------------------
# Disabling it buys about a second at boot and a few MB; nothing for the
# emulator. Both directions are applied every run so a flipped choice (or an
# old install that had it off) takes effect after the next reboot.
apply_bluetooth() {
  local f=/boot/firmware/config.txt
  if [[ $BLUETOOTH -eq 1 ]]; then
    sudo sed -i '/^# Disable on-board Bluetooth (perf)$/d; /^dtoverlay=disable-bt$/d' "$f"
    sudo systemctl unmask bluetooth.service hciuart.service 2>/dev/null || true
    sudo systemctl enable bluetooth.service hciuart.service 2>/dev/null || true
  else
    grep -q '^dtoverlay=disable-bt' "$f" \
      || printf '\n# Disable on-board Bluetooth (perf)\ndtoverlay=disable-bt\n' \
         | sudo tee -a "$f" >/dev/null
    sudo systemctl mask bluetooth.service hciuart.service 2>/dev/null || true
  fi
}
if [[ $BLUETOOTH -eq 1 ]]; then run "Keeping Bluetooth on" apply_bluetooth
else run "Turning Bluetooth off" apply_bluetooth; fi

# =========================================================================
# maclock — hardware setup
# =========================================================================
if [[ $INSTALL_MACLOCK -eq 1 ]]; then
  install_waveshare() {
    local tmp; tmp=$(mktemp -d)
    curl -fL --retry 3 -o "$tmp/28DPI-DTBO.zip" \
      https://files.waveshare.com/wiki/2.8inc-DPI-LCD/28DPI-DTBO.zip || return $?
    unzip -o -q "$tmp/28DPI-DTBO.zip" -d "$tmp" || return $?
    sudo install -m644 "$tmp"/28DPI-DTBO/*.dtbo /boot/firmware/overlays/ || return $?
    rm -rf "$tmp"
  }
  run "[maclock] Installing Waveshare overlays" install_waveshare

  compile_overlay() {
    local name=$1
    local src=/tmp/$name.dts
    local dtb=/tmp/$name.dtbo
    curl -fL --retry 3 -o "$src" "$REPO_RAW/maclock-build/$name.dts" || return $?
    dtc -q -I dts -O dtb -o "$dtb" "$src" || return $?
    sudo install -m644 "$dtb" /boot/firmware/overlays/ || return $?
  }
  run "[maclock] Compiling no-touch overlay" \
    compile_overlay waveshare-28dpi-3b-4b-notouch
  run "[maclock] Compiling audio-pin overlay" \
    compile_overlay audremap-pin19

  patch_config() {
    local f=/boot/firmware/config.txt
    if grep -qF "# >>> macintosh-mini >>>" "$f"; then
      # Older installs put audio on GPIO 18+19, which blocked the backlight
      # PWM on 18. Migrate them. See issue #15.
      sudo sed -i 's|^# Audio — PWM on GPIO 18+19, only 19 is physically wired$|# Audio — PWM on GPIO 19 only, which is the one physically wired|' "$f"
      sudo sed -i 's|^dtoverlay=audremap,pins_18_19$|dtoverlay=audremap-pin19|' "$f"
      # Only after the first match: some installs carry the block twice, and
      # loading the overlay twice just makes the second probe fail.
      grep -q '^dtoverlay=pwm-gpio,gpio=18$' "$f" || sudo sed -i \
        '0,/^dtoverlay=audremap-pin19$/s//&\ndtoverlay=pwm-gpio,gpio=18/' "$f"
      # display_rotate=3 (shipped through 1.3.0) is ignored under vc4-kms — drop
      # the dead line.
      sudo sed -i '/^display_rotate=3$/d' "$f"
      # Add the panel rotation: rotate=90 on the DPI overlay sets the DRM
      # panel-orientation, honored at init by fbcon (console) and labwc
      # (emulator) — a rotated first frame, no flash. (Idempotent: a line that
      # already carries ,rotate=90 no longer matches the bare form.)
      sudo sed -i \
        's|^dtoverlay=vc4-kms-dpi-2inch8$|dtoverlay=vc4-kms-dpi-2inch8,rotate=90|' "$f"
      return 0
    fi
    sudo tee -a "$f" >/dev/null <<'EOF'

# >>> macintosh-mini >>>
# Display — custom overlay (no touch, no kernel backlight)
dtoverlay=waveshare-28dpi-3b-4b-notouch
dtoverlay=waveshare-28dpi-3b
dtoverlay=waveshare-28dpi-4b
#dtoverlay=waveshare-touch-28dpi
# rotate=90 sets the DRM panel-orientation, honored at init by fbcon (console)
# and labwc (emulator) — rotated from the first frame, no flash.
dtoverlay=vc4-kms-dpi-2inch8,rotate=90

# Audio — PWM on GPIO 19 only, which is the one physically wired. The stock
# audremap,pins_18_19 also claims GPIO 18 and blocks the backlight PWM.
dtparam=audio=on
dtoverlay=audremap-pin19
disable_audio_dither=1

# Backlight — kernel software PWM on GPIO 18. The PWM peripheral itself is
# owned by the audio firmware; enabling it there kills sound until reboot.
dtoverlay=pwm-gpio,gpio=18

# Boot speed
initial_turbo=30
boot_delay=0
disable_splash=1
# <<< macintosh-mini <<<
EOF
  }
  run "[maclock] Patching config.txt" patch_config

  write_night_conf() {
    [[ -n $NIGHT_DIM ]] || return 0
    local lat lon factor off_at
    # A hand-set location survives re-runs
    lat=$(conf_get LAT); lon=$(conf_get LON)
    factor=$(conf_get NIGHT_FACTOR); factor=${factor:-0.5}
    if [[ $NIGHT_OFF == never ]]; then
      off_at=""
    elif [[ -n $NIGHT_OFF ]]; then
      off_at=$NIGHT_OFF
    elif grep -q '^NIGHT_OFF_AT=' "$NIGHT_CONF" 2>/dev/null; then
      # Blank is a valid setting (dim, never dark), so only fall back to
      # the default when the key is absent entirely.
      off_at=$(conf_get NIGHT_OFF_AT)
    else
      off_at=22:00
    fi
    sudo tee "$NIGHT_CONF" >/dev/null <<EOF
# Night dimming for the maclock backlight. Read by brightness-control.service;
# after editing: sudo systemctl restart brightness-control
NIGHT_DIM=$NIGHT_DIM
# Optional. Blank, the location is the timezone's reference city from tzdata.
# Set both in decimal degrees (north and east positive) for a closer fix.
LAT=$lat
LON=$lon
# Sunset to sunrise, the dial level is multiplied by this
NIGHT_FACTOR=$factor
# From this time the screen goes fully dark, until an hour before sunrise.
# Blank to only dim.
NIGHT_OFF_AT=$off_at
EOF
  }

  install_gpio_helpers() {
    for f in brightness_control.py button_handler.py; do
      curl -fL --retry 3 -o "/tmp/$f" "$REPO_RAW/maclock-build/$f" || return $?
      sudo install -m755 "/tmp/$f" "/usr/local/bin/$f" || return $?
    done
    for f in brightness-control.service button-handler.service; do
      curl -fL --retry 3 -o "/tmp/$f" "$REPO_RAW/maclock-build/$f" || return $?
      sudo install -m644 "/tmp/$f" "/etc/systemd/system/$f" || return $?
    done
    write_night_conf || return $?
    sudo systemctl daemon-reload
    # reenable, not enable: the unit moved from multi-user.target to
    # sysinit.target, and plain enable only adds the new symlink.
    sudo systemctl reenable brightness-control.service button-handler.service
    # restart, not start: on an update the old script is still running
    sudo systemctl restart brightness-control.service button-handler.service
  }

  run "[maclock] Installing GPIO helpers + systemd units" install_gpio_helpers

  install_restart_wrapper() {
    sudo tee /usr/local/bin/sheepshaver-restart.sh >/dev/null <<'WRAPPER'
#!/bin/bash
# Reset button (single press): stop the emulator, play the crash sound, relaunch.
systemctl stop getty@tty1.service
sleep 0.5
[[ -f /usr/local/bin/crash.wav ]] && aplay -q /usr/local/bin/crash.wav 2>/dev/null
systemctl start getty@tty1.service
WRAPPER
    sudo tee /usr/local/bin/macintosh-quit.sh >/dev/null <<'QUIT'
#!/bin/bash
# Reset button (double press): force-quit the emulator (exit 143); the launcher
# then drops to a Pi prompt instead of relaunching. `macintosh` boots it again.
pkill -TERM -x BasiliskII 2>/dev/null
pkill -TERM -x SheepShaver 2>/dev/null
QUIT
    sudo chmod 755 /usr/local/bin/sheepshaver-restart.sh /usr/local/bin/macintosh-quit.sh
  }
  run "[maclock] Installing reset-button wrappers" install_restart_wrapper

  # Full-scale PWM audio (~3.3 Vpp) through the breakout amp's 2.6x gain asks
  # for more swing than the amp can put across 8 ohms from the clock's ~4 V
  # battery supply, and every chime peaks at 0 dBFS, so the loudest notes
  # crackle. 4 dB of headroom keeps them clean; alsa-restore brings the stored
  # level back on every boot.
  set_audio_level() {
    if ! amixer -q -c Headphones sset PCM -- -4dB; then
      echo "No Headphones card yet; audio level left at its default"
      return 0
    fi
    sudo alsactl store
  }
  run "[maclock] Setting audio level to -4 dB" set_audio_level
fi

# =========================================================================
# SheepShaver — emulator + kiosk autostart
# =========================================================================
if [[ $INSTALL_SHEEPSHAVER -eq 1 ]]; then
  enable_seatd() {
    sudo systemctl enable --now seatd || return $?
    # Only add groups that actually exist — usermod aborts if any listed
    # group is missing, and distros vary on which of these they ship.
    local groups="" g
    for g in seat _seatd video input render; do
      getent group "$g" >/dev/null 2>&1 && groups="${groups:+$groups,}$g"
    done
    if [[ -n $groups ]]; then
      sudo usermod -aG "$groups" "$USER"
    fi
  }
  run "[sheepshaver] Enabling seatd; adding $USER to graphics groups" enable_seatd

  # Sysctls must be active *before* configure runs — its SIGSEGV recovery
  # probe mmaps low addresses, which requires vm.mmap_min_addr=0.
  write_sysctl() {
    sudo tee /etc/sysctl.d/60-sheepshaver.conf >/dev/null <<'SYSCTL'
vm.mmap_min_addr=0
vm.overcommit_memory=1
SYSCTL
    sudo sysctl --system >/dev/null
  }
  run "[sheepshaver] Writing sysctls (mmap_min_addr, overcommit)" write_sysctl

  if [[ $NEED_PREFS -eq 1 ]]; then
    run "[sheepshaver] Fetching chime: $CHIME_NAME" curl -fL --retry 3 \
      -o "$HOME/$CHIME_FILE" "$REPO_RAW/emulators/chimes/${CHIME_NAME}.wav"
    run "[sheepshaver] Fetching crash sound: $CRASH_NAME" curl -fL --retry 3 \
      -o "$HOME/crash.wav" "$REPO_RAW/emulators/chimes/${CRASH_NAME}.wav"
  fi

  if ! needs_build /usr/local/bin/SheepShaver "$SHEEPSHAVER_STAMP"; then
    : # already installed; no steps consumed
  elif prebuilt_available SheepShaver &&
       try_run "[sheepshaver] Downloading SheepShaver (built by GitHub)" \
         install_prebuilt SheepShaver "$SHEEPSHAVER_STAMP"; then
    : # downloaded and checked
  else
    # Compile it here. If a download was on offer, the step count assumed it.
    prebuilt_available SheepShaver && TOTAL_STEPS=$((TOTAL_STEPS + EMU_BUILD_STEPS))
    run "[sheepshaver] Installing build tools" install_build_tools
    run "[sheepshaver] Fetching macemu (pinned: AppleTalk tunnel fixes)" checkout_macemu

    prepare_build() {
      cd "$MACEMU_DIR/SheepShaver" || return $?
      make links || return $?
      cd src/Unix || return $?
      make distclean >/dev/null 2>&1 || true   # existing clone: drop old configure
      local cflags=$SHEEPSHAVER_CFLAGS
      [[ $PERF -eq 1 ]] && cflags+=" $PERF_CFLAGS"
      CFLAGS="$cflags" CXXFLAGS="$cflags" \
      ./autogen.sh "${SHEEPSHAVER_CONFIGURE[@]}" || return $?
    }
    run "[sheepshaver] Configuring build (no GTK)" prepare_build

    do_build() {
      cd "$MACEMU_DIR/SheepShaver/src/Unix" || return $?
      make -j"$(nproc)" || return $?
    }
    run_long "[sheepshaver] Building SheepShaver (be patient!)" do_build

    run "[sheepshaver] Installing SheepShaver binary" \
      sudo install -m755 "$MACEMU_DIR/SheepShaver/src/Unix/SheepShaver" /usr/local/bin/SheepShaver
    run "[sheepshaver] Recording the build" record_build "$SHEEPSHAVER_STAMP"
  fi

  install_launcher() {
    write_labwc_kiosk
    sudo tee /usr/local/bin/sheepshaver.sh >/dev/null <<'LAUNCHER'
#!/bin/bash
# Launches SheepShaver fullscreen via labwc on the current TTY.
# Relaunch: exit 0 (Mac Shut Down) or 143 (double-reset) -> Pi prompt;
# crash -> relaunch; Mac Restart reboots the VM in place.
ulimit -c 0   # no core dumps when killed abruptly (reset stops labwc mid-render)
clear 2>/dev/null
printf '\033[?25l' 2>/dev/null
setterm --cursor off 2>/dev/null || true

export XDG_RUNTIME_DIR=/tmp/runtime
export LIBSEAT_BACKEND=seatd
export SDL_VIDEODRIVER=x11
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

cd ~

# Wi-Fi setup asked for (left button held) or no Wi-Fi saved: the setup
# screen instead of the Mac. It exits when setup is over, and getty starts
# this launcher again.
if [ -x /usr/local/bin/mac-setup ] && /usr/local/bin/mac-setup needed; then
  exec /usr/local/bin/mac-setup screen
fi

/usr/local/bin/mac-preflight sheepshaver; pre=$?
if [ $pre -eq 2 ]; then
  exec /usr/local/bin/mac-setup screen   # only the ROM is missing
fi
if [ $pre -ne 0 ]; then
  printf '\033[?25h' 2>/dev/null; setterm --cursor on 2>/dev/null || true
  exec bash
fi

aplay -q /usr/local/bin/chime.wav 2>/dev/null &

rm -f /tmp/sheepshaver.exit
start=$(date +%s)
# labwc reads ~/.config/labwc/rc.xml and rotates the output from the DRM
# panel-orientation at init (rotated first frame, no flash). -S runs the
# session command and terminates labwc when it (the emulator) exits.
# XCURSOR_* is set only for labwc (not exported) so the invisible cursor never
# leaks into the fallback shell or a desktop started from it.
XCURSOR_THEME=transparent XCURSOR_PATH="$HOME/.local/share/icons:/usr/share/icons" \
  labwc -S "/usr/local/bin/mac-session sheepshaver SheepShaver /tmp/sheepshaver.exit"
rc=$(cat /tmp/sheepshaver.exit 2>/dev/null || echo 99)
rm -f /tmp/sheepshaver.exit

# A ROM just added on the setup page that quits within a minute didn't work:
# move it out of the way, so the setup screen asks for another.
if [ -e /run/mac-setup/rom-trial ] && [ $(( $(date +%s) - start )) -lt 60 ]; then
  rom=$(sed -n 's/^rom //p' ~/.sheepshaver_prefs | head -1)
  [ -n "$rom" ] && mv -f "$rom" "$HOME/.ROM.rejected"
  exit 0
fi

if [ "$rc" = "0" ] || [ "$rc" = "143" ]; then
  clear 2>/dev/null
  setterm --cursor on 2>/dev/null || true
  exec bash
fi

[ -f /usr/local/bin/crash.wav ] && aplay -q /usr/local/bin/crash.wav 2>/dev/null
LAUNCHER
    sudo chmod 755 /usr/local/bin/sheepshaver.sh
    [[ -f "$HOME/$CHIME_FILE" ]] && sudo install -m644 "$HOME/$CHIME_FILE" /usr/local/bin/chime.wav
    [[ -f "$HOME/crash.wav" ]] && sudo install -m644 "$HOME/crash.wav" /usr/local/bin/crash.wav
    write_macintosh_cmd
    write_preflight
    touch "$HOME/.hushlogin"
  }
  run "[sheepshaver] Installing launcher + sounds" install_launcher

  write_prefs() {
    [[ -f "$HOME/.sheepshaver_prefs" ]] && return 0   # update: keep existing prefs
    local ramsize=67108864     # 64 MB
    local extra=""
    if [[ $PERF -eq 1 ]]; then
      ramsize=134217728        # 128 MB
      extra=$'\nsound_buffer 4096'
    fi
    cat > "$HOME/.sheepshaver_prefs" <<EOF
disk $DISK_IMAGE
rom $ROM_FILE
screen dga/640/480/$COLOR_DEPTH
ramsize $ramsize
modelid 5
cpu 4
fpu true
nogui true
nosound false
ether slirp
ignoreillegal false$extra
EOF
  }
  run "[sheepshaver] Writing prefs ($COLOR_LABEL / ${COLOR_DEPTH}bpp)" write_prefs

  config_autologin() {
    sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
    sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --skip-login --noclear --noissue --nohostname %I \$TERM
EOF
    sudo systemctl daemon-reload
  }
  run "[sheepshaver] Configuring tty1 autologin for $USER" config_autologin

  patch_profile() {
    # Drop any BasiliskII autostart so SheepShaver wins on tty1.
    sed -i '/# >>> basilisk-autostart >>>/,/# <<< basilisk-autostart <<</d' "$HOME/.profile" 2>/dev/null || true
    local marker="# >>> sheepshaver-autostart >>>"
    grep -qF "$marker" "$HOME/.profile" 2>/dev/null && return 0
    cat >> "$HOME/.profile" <<EOF

$marker
# Auto-start SheepShaver on tty1 (after autologin)
if [ "\$(tty)" = "/dev/tty1" ] && [ -z "\$WAYLAND_DISPLAY" ] && [ -z "\$DISPLAY" ]; then
    exec /usr/local/bin/sheepshaver.sh
fi
# <<< sheepshaver-autostart <<<
EOF
  }
  run "[sheepshaver] Appending autostart to ~/.profile" patch_profile
fi

# =========================================================================
# BasiliskII — emulator + kiosk autostart (Mac OS 7.x, 68k ROM)
# =========================================================================
if [[ $INSTALL_BASILISK -eq 1 ]]; then
  enable_seatd_basilisk() {
    sudo systemctl enable --now seatd || return $?
    # Only add groups that actually exist — usermod aborts if any listed
    # group is missing, and distros vary on which of these they ship.
    local groups="" g
    for g in seat _seatd video input render; do
      getent group "$g" >/dev/null 2>&1 && groups="${groups:+$groups,}$g"
    done
    if [[ -n $groups ]]; then
      sudo usermod -aG "$groups" "$USER"
    fi
  }
  run "[basilisk] Enabling seatd; adding $USER to graphics groups" enable_seatd_basilisk

  # BasiliskII maps the Mac low-memory globals; needs mmap_min_addr=0.
  write_basilisk_sysctl() {
    sudo tee /etc/sysctl.d/60-basilisk.conf >/dev/null <<'SYSCTL'
vm.mmap_min_addr=0
SYSCTL
    sudo sysctl --system >/dev/null
  }
  run "[basilisk] Writing sysctl (mmap_min_addr)" write_basilisk_sysctl

  if [[ $NEED_PREFS -eq 1 ]]; then
    run "[basilisk] Fetching chime: $CHIME_NAME" curl -fL --retry 3 \
      -o "$HOME/$CHIME_FILE" "$REPO_RAW/emulators/chimes/${CHIME_NAME}.wav"
    run "[basilisk] Fetching crash sound: $CRASH_NAME" curl -fL --retry 3 \
      -o "$HOME/crash.wav" "$REPO_RAW/emulators/chimes/${CRASH_NAME}.wav"
  fi

  if ! needs_build /usr/local/bin/BasiliskII "$BASILISK_STAMP"; then
    : # already installed; no steps consumed
  elif prebuilt_available BasiliskII &&
       try_run "[basilisk] Downloading Basilisk II (built by GitHub)" \
         install_prebuilt BasiliskII "$BASILISK_STAMP"; then
    : # downloaded and checked
  else
    # Compile it here. If a download was on offer, the step count assumed it.
    prebuilt_available BasiliskII && TOTAL_STEPS=$((TOTAL_STEPS + EMU_BUILD_STEPS))
    run "[basilisk] Installing build tools" install_build_tools
    run "[basilisk] Fetching macemu (pinned: AppleTalk tunnel fixes)" checkout_macemu

    prepare_basilisk_build() {
      cd "$MACEMU_DIR/BasiliskII/src/Unix" || return $?
      make distclean >/dev/null 2>&1 || true   # existing clone: drop old configure
      local cflags=$BASILISK_CFLAGS
      [[ $PERF -eq 1 ]] && cflags+=" $PERF_CFLAGS"
      CFLAGS="$cflags" CXXFLAGS="$cflags" \
      ./autogen.sh "${BASILISK_CONFIGURE[@]}" || return $?
    }
    run "[basilisk] Configuring build (SDL, no JIT, VOSF, no GTK)" prepare_basilisk_build

    do_basilisk_build() {
      cd "$MACEMU_DIR/BasiliskII/src/Unix" || return $?
      make -j"$(nproc)" || return $?
    }
    run_long "[basilisk] Building Basilisk II (be patient!)" do_basilisk_build

    run "[basilisk] Installing BasiliskII binary" \
      sudo install -m755 "$MACEMU_DIR/BasiliskII/src/Unix/BasiliskII" /usr/local/bin/BasiliskII
    run "[basilisk] Recording the build" record_build "$BASILISK_STAMP"
  fi

  install_basilisk_launcher() {
    write_labwc_kiosk
    sudo tee /usr/local/bin/basilisk.sh >/dev/null <<'LAUNCHER'
#!/bin/bash
# Launches BasiliskII fullscreen via labwc on the current TTY.
# Relaunch: exit 0 (Mac Shut Down) or 143 (double-reset) -> Pi prompt;
# crash -> relaunch; Mac Restart reboots the VM in place.
ulimit -c 0   # no core dumps when killed abruptly (reset stops labwc mid-render)
clear 2>/dev/null
printf '\033[?25l' 2>/dev/null
setterm --cursor off 2>/dev/null || true

export XDG_RUNTIME_DIR=/tmp/runtime
export LIBSEAT_BACKEND=seatd
export SDL_VIDEODRIVER=x11
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

cd ~

# Wi-Fi setup asked for (left button held) or no Wi-Fi saved: the setup
# screen instead of the Mac. It exits when setup is over, and getty starts
# this launcher again.
if [ -x /usr/local/bin/mac-setup ] && /usr/local/bin/mac-setup needed; then
  exec /usr/local/bin/mac-setup screen
fi

/usr/local/bin/mac-preflight basilisk; pre=$?
if [ $pre -eq 2 ]; then
  exec /usr/local/bin/mac-setup screen   # only the ROM is missing
fi
if [ $pre -ne 0 ]; then
  printf '\033[?25h' 2>/dev/null; setterm --cursor on 2>/dev/null || true
  exec bash
fi

aplay -q /usr/local/bin/chime.wav 2>/dev/null &

rm -f /tmp/basilisk.exit
start=$(date +%s)
# labwc reads ~/.config/labwc/rc.xml and rotates the output from the DRM
# panel-orientation at init (rotated first frame, no flash). -S runs the
# session command and terminates labwc when it (the emulator) exits.
# XCURSOR_* is set only for labwc (not exported) so the invisible cursor never
# leaks into the fallback shell or a desktop started from it.
XCURSOR_THEME=transparent XCURSOR_PATH="$HOME/.local/share/icons:/usr/share/icons" \
  labwc -S "/usr/local/bin/mac-session basilisk BasiliskII /tmp/basilisk.exit"
rc=$(cat /tmp/basilisk.exit 2>/dev/null || echo 99)
rm -f /tmp/basilisk.exit

# A ROM just added on the setup page that quits within a minute didn't work:
# move it out of the way, so the setup screen asks for another.
if [ -e /run/mac-setup/rom-trial ] && [ $(( $(date +%s) - start )) -lt 60 ]; then
  rom=$(sed -n 's/^rom //p' ~/.basilisk_ii_prefs | head -1)
  [ -n "$rom" ] && mv -f "$rom" "$HOME/.ROM.rejected"
  exit 0
fi

if [ "$rc" = "0" ] || [ "$rc" = "143" ]; then
  clear 2>/dev/null
  setterm --cursor on 2>/dev/null || true
  exec bash
fi

[ -f /usr/local/bin/crash.wav ] && aplay -q /usr/local/bin/crash.wav 2>/dev/null
LAUNCHER
    sudo chmod 755 /usr/local/bin/basilisk.sh
    [[ -f "$HOME/$CHIME_FILE" ]] && sudo install -m644 "$HOME/$CHIME_FILE" /usr/local/bin/chime.wav
    [[ -f "$HOME/crash.wav" ]] && sudo install -m644 "$HOME/crash.wav" /usr/local/bin/crash.wav
    write_macintosh_cmd
    write_preflight
    touch "$HOME/.hushlogin"
  }
  run "[basilisk] Installing launcher + sounds" install_basilisk_launcher

  write_basilisk_prefs() {
    [[ -f "$HOME/.basilisk_ii_prefs" ]] && return 0   # update: keep existing prefs
    local ramsize=67108864     # 64 MB
    [[ $PERF -eq 1 ]] && ramsize=134217728   # 128 MB
    cat > "$HOME/.basilisk_ii_prefs" <<EOF
disk $HOME/$DISK_IMAGE
rom $HOME/$ROM_FILE
screen win/640/480
displaycolordepth $COLOR_DEPTH
ramsize $ramsize
modelid $MODELID
cpu 4
fpu true
nogui true
nosound false
ether slirp
udptunnel true
udpport 6066
udpappletalkonly true
jit false
jitfpu false
frameskip 2
idlewait true
ignoresegv true
EOF
  }
  case "$MODELID" in
    5)  MODEL_LABEL="Mac IIci" ;;
    14) MODEL_LABEL="Quadra" ;;
    *)  MODEL_LABEL="modelid $MODELID" ;;
  esac
  run "[basilisk] Writing prefs ($MODEL_LABEL / $COLOR_LABEL / ${COLOR_DEPTH}bpp / 640×480)" write_basilisk_prefs

  config_autologin_basilisk() {
    sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
    sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --skip-login --noclear --noissue --nohostname %I \$TERM
EOF
    sudo systemctl daemon-reload
  }
  run "[basilisk] Configuring tty1 autologin for $USER" config_autologin_basilisk

  patch_profile_basilisk() {
    # Drop any SheepShaver autostart so BasiliskII wins on tty1.
    sed -i '/# >>> sheepshaver-autostart >>>/,/# <<< sheepshaver-autostart <<</d' "$HOME/.profile" 2>/dev/null || true
    local marker="# >>> basilisk-autostart >>>"
    grep -qF "$marker" "$HOME/.profile" 2>/dev/null && return 0
    cat >> "$HOME/.profile" <<EOF

$marker
# Auto-start BasiliskII on tty1 (after autologin)
if [ "\$(tty)" = "/dev/tty1" ] && [ -z "\$WAYLAND_DISPLAY" ] && [ -z "\$DISPLAY" ]; then
    exec /usr/local/bin/basilisk.sh
fi
# <<< basilisk-autostart <<<
EOF
  }
  run "[basilisk] Appending autostart to ~/.profile" patch_profile_basilisk
fi

# --- Wi-Fi setup from a phone -----------------------------------------------
# mac-setup offers an open "Macintosh Mini XXXX" hotspot when no Wi-Fi is saved
# or the left button is held for 10 s, with a setup page phones open by
# themselves; and, while there's no ROM, a ROM page on the owner's network.
# See maclock-build/mac_setup.py.
if [[ $INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1 ]]; then
  install_mac_setup() {
    local f emulator=basilisk prefs="$HOME/.basilisk_ii_prefs"
    if [[ $INSTALL_SHEEPSHAVER -eq 1 ]]; then
      emulator=sheepshaver; prefs="$HOME/.sheepshaver_prefs"
    fi
    sudo install -d /usr/local/lib/mac-setup || return $?
    for f in mac_setup.py mac_setup_rom.py mac_setup_web.py mac_setup_screen.py; do
      curl -fL --retry 3 -o "/tmp/$f" "$REPO_RAW/maclock-build/$f" || return $?
      sudo install -m644 "/tmp/$f" "/usr/local/lib/mac-setup/$f" || return $?
    done
    curl -fL --retry 3 -o /tmp/mac-setup.service "$REPO_RAW/maclock-build/mac-setup.service" || return $?
    sudo install -m644 /tmp/mac-setup.service /etc/systemd/system/mac-setup.service || return $?
    sudo tee /usr/local/bin/mac-setup >/dev/null <<'WRAPPER'
#!/bin/sh
# Wi-Fi setup from a phone: see /usr/local/lib/mac-setup/mac_setup.py.
if [ "$1" = needed ]; then
  # The launcher asks this on every start, so no Python here. Setup is due when
  # the left button asked for it, or when no Wi-Fi is saved. If NetworkManager
  # can't answer, say no: never keep the Mac from starting.
  [ -e /run/mac-setup/requested ] && exit 0
  saved=$(nmcli -t -f NAME,TYPE connection show 2>/dev/null) || exit 1
  printf '%s\n' "$saved" | grep -v '^mac-setup-hotspot:' | grep -q ':802-11-wireless$' && exit 1
  # No Wi-Fi saved, but on a wired network (USB Ethernet): not a first run.
  nmcli -t -f TYPE connection show --active 2>/dev/null | grep -q '^802-3-ethernet$' && exit 1
  exit 0
fi
exec python3 /usr/local/lib/mac-setup/mac_setup.py "$@"
WRAPPER
    sudo chmod 755 /usr/local/bin/mac-setup
    printf 'USER=%s\nHOME=%s\nEMULATOR=%s\nPREFS=%s\n' "$USER" "$HOME" "$emulator" "$prefs" \
      | sudo tee /etc/mac-setup.conf >/dev/null
    # On the hotspot every name points at the Mac, so phones' "is there
    # internet?" checks land on the setup page and they pop it up.
    sudo install -d /etc/NetworkManager/dnsmasq-shared.d
    printf '%s\n' '# Wi-Fi setup hotspot (mac-setup)' 'address=/#/10.42.0.1' \
      | sudo tee /etc/NetworkManager/dnsmasq-shared.d/mac-setup.conf >/dev/null
    # The setup screen sends people to <hostname>.local, which avahi answers.
    # Installs before 1.7.0 masked it with the performance options.
    sudo systemctl unmask avahi-daemon.service avahi-daemon.socket 2>/dev/null || true
    sudo systemctl enable --now avahi-daemon.service 2>/dev/null || true
    sudo systemctl daemon-reload
    sudo systemctl enable mac-setup.service
    # restart, not start: on an update the old service is still running
    sudo systemctl restart mac-setup.service
  }
  run "Installing Wi-Fi setup (hotspot + setup page)" install_mac_setup
fi

# --- Record what was installed, so the next run knows it is an update -----
record_install() {
  local emulator=$INSTALLED_EMULATOR maclock=${INSTALLED_MACLOCK:-0}
  [[ $INSTALL_BASILISK -eq 1 ]] && emulator=basilisk
  [[ $INSTALL_SHEEPSHAVER -eq 1 ]] && emulator=sheepshaver
  [[ $INSTALL_MACLOCK -eq 1 ]] && maclock=1
  printf 'VERSION=%s\nMACLOCK=%s\nEMULATOR=%s\nPERF=%s\nBLUETOOTH=%s\n' \
    "$VERSION" "$maclock" "$emulator" "${PERF:-0}" "$BLUETOOTH" | sudo tee "$INSTALL_STATE" >/dev/null
}
run "Recording the install" record_install

# --- Done -----------------------------------------------------------------
emit_gauge 100 "Done"
sleep 1
stop_gauge

# --hotspot-setup: erase what belongs to whoever ran this, then shut down. It
# runs detached, because forgetting the Wi-Fi ends this SSH session.
if [[ $HOTSPOT_SETUP -eq 1 ]]; then
  ho_rom=$(installed_rom_path)
  sudo tee /run/mac-setup-handoff.sh >/dev/null <<'HANDOFF'
#!/bin/bash
# Prepare a Mac for phone setup (setup.sh --hotspot-setup). Args: user home log rom
user=$1 home=$2 log=$3 rom=$4
sleep 3
# Keep the Wi-Fi country: cloud-init, which may have set it, is cleared below.
cc=$(iw reg get 2>/dev/null | sed -n 's/^country \([A-Z][A-Z]\):.*/\1/p' | head -1)
if [ -n "$cc" ] && [ "$cc" != 00 ] && command -v raspi-config >/dev/null; then
  raspi-config nonint do_wifi_country "$cc"
fi
# SSH by password: the one the new owner picks is the only way in.
install -d /etc/ssh/sshd_config.d
printf '%s\n' '# Prepared for phone setup: log in with the password chosen there.' \
  'PasswordAuthentication yes' > /etc/ssh/sshd_config.d/10-mac-setup.conf
rm -f /etc/ssh/sshd_config.d/50-cloud-init.conf
systemctl enable ssh 2>/dev/null
passwd -l "$user"
rm -rf "$home/.ssh"
rm -f /root/.ssh/authorized_keys "$home/.bash_history" "$home/.ROM.rejected" "$log"
# No ROM ships: the one in prefs, and anything mac-preflight would take for one.
[ -n "$rom" ] && rm -f "$rom"
find "$home" -maxdepth 1 -type f \( -size 524288c -o -size 1048576c -o -size 4194304c \) \
  ! -name '*.hda' ! -name '*.dsk' ! -name '*.img' ! -name '*.hfv' -delete
# A hand-set location for night dimming is a precise address.
[ -f /etc/default/brightness-control ] &&
  sed -i 's/^LAT=.*/LAT=/;s/^LON=.*/LON=/' /etc/default/brightness-control
install -d /var/lib/mac-setup
touch /var/lib/mac-setup/needs-password
# cloud-init carried the preparer's Wi-Fi and login: turn it off and clear it.
touch /etc/cloud/cloud-init.disabled
rm -rf /var/lib/cloud
# Backup copies too: a user-data.bak holds the login as much as user-data does.
rm -f /boot/firmware/user-data* /boot/firmware/network-config* /var/log/cloud-init*.log
# Forget every Wi-Fi network. If this session is over Wi-Fi, it ends here.
nmcli -t -f UUID,TYPE connection show | awk -F: '$2 == "802-11-wireless" { print $1 }' |
  while read -r uuid; do nmcli connection delete uuid "$uuid"; done
grep -ls '^type=wifi' /etc/NetworkManager/system-connections/* 2>/dev/null | xargs -r rm -f
for f in /etc/netplan/*.yaml; do grep -qs 'wifis:' "$f" && rm -f "$f"; done
# What NetworkManager remembers about those networks: access points seen (with
# the network name, enough to find a home on public Wi-Fi maps) and leases.
rm -f /var/lib/NetworkManager/seen-bssids /var/lib/NetworkManager/timestamps \
  /var/lib/NetworkManager/*.lease
# End the preparer's sessions now: a shell saves its history when it is hung
# up on at shutdown, after the rm above.
pkill -KILL -u "$user"
sleep 2
rm -f "$home/.bash_history"
journalctl --rotate >/dev/null 2>&1
journalctl --vacuum-time=1s >/dev/null 2>&1
sync
poweroff
HANDOFF
  printf '\n\033[1;32m✓ Setup complete.\033[0m  Erasing this Mac'"'"'s Wi-Fi, keys and password, then shutting down…\n'
  printf '  When it next starts, it offers the Wi-Fi network "Macintosh Mini %s".\n\n' "$(setup_suffix | tr a-f A-F)"
  sudo systemd-run --unit=mac-setup-handoff --collect /bin/bash /run/mac-setup-handoff.sh \
    "$USER" "$HOME" "$LOG_FILE" "$ho_rom" >/dev/null
  exit 0
fi

printf '\n\033[1;32m✓ Setup complete.\033[0m  Rebooting in 5 seconds (Ctrl-C to cancel)…\n'
printf '  log: %s\n\n' "$LOG_FILE"
sleep 5
sudo reboot
