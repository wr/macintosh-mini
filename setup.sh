#!/usr/bin/env bash
# macintosh-mini setup for a fresh Raspberry Pi Zero 2 W.
#
# Run on the Pi (or `curl … | bash`). Idempotent. Reboots at the end.
#
# Place a ROM and a disk image in $HOME before running:
#   BasiliskII  (68k, Mac OS 7):     512 KB or 1 MB 68k ROM + *.hda/*.dsk
#   SheepShaver (PowerPC, OS 8.1+):  4 MB PPC ROM + *.hda
#
# Flags (skip prompts):
#   --all | --all-basilisk | --maclock | --sheepshaver | --basilisk
#   --chime <name>      e.g. StartupMacII (default)
#   --color <mode>      Color | Grayscale | "Black & White"  (also accepts color/grayscale/bw)
#   --disk <file>       disk image filename in $HOME (default: auto-discover)
#   --rom <file>        ROM filename in $HOME (default: ROM)
#   --hostname <name>   default: leave unchanged
#   --perf | --no-perf  enable/disable performance optimizations (default: prompt)
#   --debug             show all command output instead of capturing to log

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/wr/macintosh-mini/main"

# SheepShaver paths (DISK_IMAGE is auto-discovered or set via --disk)
DISK_IMAGE=""
ROM_FILE="ROM"
CHIME_FILE="chime.wav"
MACEMU_DIR="$HOME/macemu"

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
# Standard whiptail look with a black/dark-gray root background.
# NEWT_COLORS is colon-separated; setting only `root` leaves every other
# element at its default. NEWT's palette is limited to 8 named colors;
# `black` reads as dark gray on most modern terminals.
export NEWT_COLORS='root=,black'

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
USE_GAUGE=0
TOTAL_STEPS=1
CURRENT_STEP=0

start_gauge() {
  [[ $DEBUG -eq 1 ]] && return
  PROGRESS_FIFO=$(mktemp -u /tmp/macintosh-mini-progress.XXXXXX)
  mkfifo "$PROGRESS_FIFO"
  whiptail --backtitle "macintosh-mini" --title "Installing" \
    --gauge "Starting…" 8 72 0 < "$PROGRESS_FIFO" &
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
  printf 'XXX\n%s\n%s\nXXX\n' "$pct" "$msg" >&9
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
  # Args: title, prompt, default_tag, list_height, then pairs of tag/label.
  local title=$1 prompt=$2 default=$3 list_height=$4
  shift 4
  local total_height=$(( list_height + 8 ))
  whiptail --backtitle "macintosh-mini" --title "$title" \
    --default-item "$default" \
    --menu "$prompt" "$total_height" 72 "$list_height" \
    "$@" 3>&1 1>&2 2>&3 </dev/tty
}

wt_input() {
  local title=$1 prompt=$2 default=$3
  whiptail --backtitle "macintosh-mini" --title "$title" \
    --inputbox "$prompt" 10 70 "$default" \
    3>&1 1>&2 2>&3 </dev/tty
}

# --- Asset sanity check ----------------------------------------------------
# Verify ROM and at least one disk image exist in $HOME. Idempotent —
# safe to call multiple times.
check_sheepshaver_assets() {
  [[ -f "$HOME/.sheepshaver_prefs" ]] && return 0   # existing install -> update, keep config
  [[ -f "$HOME/$ROM_FILE" ]] || die "Missing $HOME/$ROM_FILE — copy it over before running"
  if [[ -n $DISK_IMAGE ]]; then
    [[ -f "$HOME/$DISK_IMAGE" ]] || die "Missing $HOME/$DISK_IMAGE (passed via --disk)"
  else
    shopt -s nullglob
    local hdas=("$HOME"/*.hda)
    shopt -u nullglob
    [[ ${#hdas[@]} -gt 0 ]] || die "No .hda disk image found in $HOME — copy one over before running"
  fi
}

# Verify a 68k ROM and a disk image exist for BasiliskII. The 68k ROM is
# 512 KB or 1 MB; reject the 4 MB PPC ROM, which is a common mix-up.
check_basilisk_assets() {
  [[ -f "$HOME/.basilisk_ii_prefs" ]] && return 0   # existing install -> update, keep config
  [[ -f "$HOME/$ROM_FILE" ]] || die "Missing $HOME/$ROM_FILE — copy a 68k Mac ROM over before running"
  local rom_size
  rom_size=$(wc -c < "$HOME/$ROM_FILE")
  if [[ $rom_size -ne 524288 && $rom_size -ne 1048576 ]]; then
    die "ROM is $rom_size bytes — BasiliskII needs a 512 KB or 1 MB 68k ROM, not the 4 MB PowerPC ROM"
  fi
  if [[ -n $DISK_IMAGE ]]; then
    [[ -f "$HOME/$DISK_IMAGE" ]] || die "Missing $HOME/$DISK_IMAGE (passed via --disk)"
  else
    shopt -s nullglob
    local disks=("$HOME"/*.hda "$HOME"/*.dsk)
    shopt -u nullglob
    [[ ${#disks[@]} -gt 0 ]] || die "No .hda or .dsk disk image found in $HOME — copy one over before running"
  fi
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
NEW_HOSTNAME=""
PERF=""   # "" = prompt, 1 = on, 0 = off

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)           INSTALL_MACLOCK=1; INSTALL_SHEEPSHAVER=1; shift ;;
    --all-basilisk)  INSTALL_MACLOCK=1; INSTALL_BASILISK=1; shift ;;
    --maclock)       INSTALL_MACLOCK=1; shift ;;
    --sheepshaver)   INSTALL_SHEEPSHAVER=1; shift ;;
    --basilisk)      INSTALL_BASILISK=1; shift ;;
    --chime)         CHIME_NAME=$2; shift 2 ;;
    --color)         COLOR_MODE=$2; shift 2 ;;
    --disk)          DISK_IMAGE=$2; shift 2 ;;
    --rom)           ROM_FILE=$2; shift 2 ;;
    --hostname)      NEW_HOSTNAME=$2; shift 2 ;;
    --perf)          PERF=1; shift ;;
    --no-perf)       PERF=0; shift ;;
    --debug)         DEBUG=1; shift ;;
    *) die "Unknown option: $1" ;;
  esac
done

# --- Header ---------------------------------------------------------------
printf '\033[1;35m╔═ macintosh-mini setup ═╗\033[0m\n'
printf '  log: %s%s\n' "$LOG_FILE" "$([[ $DEBUG -eq 1 ]] && echo '  [debug mode: verbose]' || echo '')"

[[ "$(uname -m)" == "aarch64" ]] || warn "Not aarch64 ($(uname -m)) — guide is tested on Pi Zero 2 W aarch64"

# Pre-flight asset check — bail out before any sudo prompt or apt install
# if an emulator was requested via flag but its ROM/disk is missing.
[[ $INSTALL_SHEEPSHAVER -eq 1 ]] && check_sheepshaver_assets
[[ $INSTALL_BASILISK    -eq 1 ]] && check_basilisk_assets

ensure_sudo
ensure_whiptail

# --- Whiptail prompts ------------------------------------------------------
if [[ $INSTALL_MACLOCK -eq 0 && $INSTALL_SHEEPSHAVER -eq 0 && $INSTALL_BASILISK -eq 0 ]]; then
  CHOICE=$(wt_menu "macintosh-mini" "What do you want to install?" "Both" 5 \
    "Both"        "maclock + BasiliskII (68k, Mac OS 7)" \
    "Both-PPC"    "maclock + SheepShaver (PowerPC, Mac OS 8.1+)" \
    "maclock"     "hardware only (Waveshare display, dial, buttons)" \
    "BasiliskII"  "68k emulator only (Mac OS 7)" \
    "SheepShaver" "PowerPC emulator only (Mac OS 8.1+)") || die "Cancelled"
  case "$CHOICE" in
    Both)        INSTALL_MACLOCK=1; INSTALL_BASILISK=1 ;;
    Both-PPC)    INSTALL_MACLOCK=1; INSTALL_SHEEPSHAVER=1 ;;
    maclock)     INSTALL_MACLOCK=1 ;;
    BasiliskII)  INSTALL_BASILISK=1 ;;
    SheepShaver) INSTALL_SHEEPSHAVER=1 ;;
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

# Disk image — auto-discover in $HOME, prompt if multiple, use as-is.
# SheepShaver reads *.hda; BasiliskII also reads *.dsk.
if [[ ($INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1) && -z $DISK_IMAGE && $NEED_PREFS -eq 1 ]]; then
  shopt -s nullglob
  if [[ $INSTALL_BASILISK -eq 1 ]]; then
    HDA_PATHS=("$HOME"/*.hda "$HOME"/*.dsk)
  else
    HDA_PATHS=("$HOME"/*.hda)
  fi
  shopt -u nullglob
  if [[ ${#HDA_PATHS[@]} -eq 0 ]]; then
    die "No disk image found in $HOME — copy one over before running"
  elif [[ ${#HDA_PATHS[@]} -eq 1 ]]; then
    DISK_IMAGE=$(basename "${HDA_PATHS[0]}")
  else
    WT_ARGS=()
    for p in "${HDA_PATHS[@]}"; do
      WT_ARGS+=("$(basename "$p")" "$(du -h "$p" | cut -f1)")
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

# Performance optimizations
if [[ -z $PERF ]]; then
  PERF_CHOICE=$(wt_menu "Performance" "Apply performance optimizations?" "Yes" 2 \
    "Yes"  "service masking, fsck skip, disable-bt, -mcpu=cortex-a53, 128MB RAM" \
    "No"   "stock install") || die "Cancelled"
  case "$PERF_CHOICE" in Yes) PERF=1 ;; No) PERF=0 ;; esac
fi

# Hostname
CUR_HOSTNAME=$(hostname)
if [[ -z $NEW_HOSTNAME ]]; then
  NEW_HOSTNAME=$(wt_input "Hostname" "Pi hostname (leave as-is to skip):" "$CUR_HOSTNAME") \
    || die "Cancelled"
fi
NEW_HOSTNAME=${NEW_HOSTNAME// /-}


# --- Total step count (for gauge) -----------------------------------------
TOTAL_STEPS=3   # apt update, apt install, patch_cmdline
[[ -n $NEW_HOSTNAME && $NEW_HOSTNAME != "$CUR_HOSTNAME" ]] && TOTAL_STEPS=$((TOTAL_STEPS+1))
[[ $INSTALL_MACLOCK -eq 1 ]] && TOTAL_STEPS=$((TOTAL_STEPS+5))
if [[ $INSTALL_SHEEPSHAVER -eq 1 ]]; then
  if [[ -x /usr/local/bin/SheepShaver ]]; then
    TOTAL_STEPS=$((TOTAL_STEPS+9))
  else
    TOTAL_STEPS=$((TOTAL_STEPS+12))
  fi
fi
if [[ $INSTALL_BASILISK -eq 1 ]]; then
  if [[ -x /usr/local/bin/BasiliskII ]]; then
    TOTAL_STEPS=$((TOTAL_STEPS+8))
  else
    TOTAL_STEPS=$((TOTAL_STEPS+12))
  fi
fi
[[ $PERF -eq 1 ]] && TOTAL_STEPS=$((TOTAL_STEPS+3))

# --- Open the gauge --------------------------------------------------------
start_gauge
trap 'stop_gauge' EXIT

# --- Hostname change ------------------------------------------------------
if [[ -n $NEW_HOSTNAME && $NEW_HOSTNAME != "$CUR_HOSTNAME" ]]; then
  set_host() {
    sudo hostnamectl set-hostname "$NEW_HOSTNAME" || return $?
    if grep -qE "^127\.0\.1\.1[[:space:]]+$CUR_HOSTNAME" /etc/hosts; then
      sudo sed -i "s/^127\.0\.1\.1[[:space:]]\+$CUR_HOSTNAME.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
    else
      printf '127.0.1.1\t%s\n' "$NEW_HOSTNAME" | sudo tee -a /etc/hosts >/dev/null
    fi
  }
  run "Setting hostname: $CUR_HOSTNAME → $NEW_HOSTNAME" set_host
fi

# --- apt packages ---------------------------------------------------------
APT_PKGS=(curl git)
if [[ $INSTALL_SHEEPSHAVER -eq 1 || $INSTALL_BASILISK -eq 1 ]]; then
  APT_PKGS+=(
    build-essential autoconf automake libtool pkg-config
    libsdl2-dev libgtk-3-dev libgl1-mesa-dev libxkbcommon-dev
    libmpfr-dev
    cage wlr-randr seatd
    alsa-utils
  )
fi
if [[ $INSTALL_MACLOCK -eq 1 ]]; then
  APT_PKGS+=(python3-lgpio device-tree-compiler unzip)
fi
run "Updating apt index" sudo apt-get update
run "Installing ${#APT_PKGS[@]} apt packages" sudo apt-get install -y "${APT_PKGS[@]}"

# --- Quiet boot -----------------------------------------------------------
patch_cmdline() {
  local f=/boot/firmware/cmdline.txt
  grep -q 'vt.global_cursor_default=0' "$f" && return 0
  sudo sed -i 's|$| quiet loglevel=0 vt.global_cursor_default=0 console=tty3 logo.nologo|' "$f"
}
run "Configuring quiet boot (cmdline.txt)" patch_cmdline

# --- Performance optimizations -------------------------------------------
if [[ $PERF -eq 1 ]]; then
  patch_cmdline_perf() {
    local f=/boot/firmware/cmdline.txt
    grep -q 'fsck.mode=skip' "$f" && return 0
    sudo sed -i 's|$| fsck.mode=skip noswap|' "$f"
  }
  run "[perf] cmdline: skip fsck, no swap" patch_cmdline_perf

  patch_disable_bt() {
    local f=/boot/firmware/config.txt
    grep -q '^dtoverlay=disable-bt' "$f" && return 0
    printf '\n# Disable on-board Bluetooth (perf)\ndtoverlay=disable-bt\n' \
      | sudo tee -a "$f" >/dev/null
  }
  run "[perf] Disabling on-board Bluetooth" patch_disable_bt

  mask_services() {
    local services=(
      systemd-networkd-wait-online.service
      bluetooth.service
      hciuart.service
      triggerhappy.service
      ModemManager.service
      avahi-daemon.service
      avahi-daemon.socket
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

  install_notouch_overlay() {
    local src=/tmp/waveshare-28dpi-3b-4b-notouch.dts
    local dtb=/tmp/waveshare-28dpi-3b-4b-notouch.dtbo
    curl -fL --retry 3 -o "$src" "$REPO_RAW/maclock-build/waveshare-28dpi-3b-4b-notouch.dts" || return $?
    dtc -q -I dts -O dtb -o "$dtb" "$src" || return $?
    sudo install -m644 "$dtb" /boot/firmware/overlays/ || return $?
  }
  run "[maclock] Compiling no-touch overlay" install_notouch_overlay

  patch_config() {
    local f=/boot/firmware/config.txt
    grep -qF "# >>> macintosh-mini >>>" "$f" && return 0
    sudo tee -a "$f" >/dev/null <<'EOF'

# >>> macintosh-mini >>>
# Display — custom overlay (no touch, no kernel backlight)
dtoverlay=waveshare-28dpi-3b-4b-notouch
dtoverlay=waveshare-28dpi-3b
dtoverlay=waveshare-28dpi-4b
#dtoverlay=waveshare-touch-28dpi
dtoverlay=vc4-kms-dpi-2inch8
display_rotate=3

# Audio — PWM on GPIO 18+19, only 19 is physically wired
dtparam=audio=on
dtoverlay=audremap,pins_18_19
disable_audio_dither=1

# Boot speed
initial_turbo=30
boot_delay=0
disable_splash=1
# <<< macintosh-mini <<<
EOF
  }
  run "[maclock] Patching config.txt" patch_config

  install_gpio_helpers() {
    for f in brightness_control.py button_handler.py; do
      curl -fL --retry 3 -o "/tmp/$f" "$REPO_RAW/maclock-build/$f" || return $?
      sudo install -m755 "/tmp/$f" "/usr/local/bin/$f" || return $?
    done
    for f in brightness-control.service button-handler.service; do
      curl -fL --retry 3 -o "/tmp/$f" "$REPO_RAW/maclock-build/$f" || return $?
      sudo install -m644 "/tmp/$f" "/etc/systemd/system/$f" || return $?
    done
    sudo systemctl daemon-reload
    sudo systemctl enable --now brightness-control.service button-handler.service
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
fi

# =========================================================================
# SheepShaver — emulator + kiosk autostart
# =========================================================================
if [[ $INSTALL_SHEEPSHAVER -eq 1 ]]; then
  enable_seatd() {
    sudo systemctl enable --now seatd || return $?
    local seat_group="" g
    for g in seat _seatd; do
      if getent group "$g" >/dev/null 2>&1; then seat_group=$g; break; fi
    done
    local groups="video,input,render"
    [[ -n $seat_group ]] && groups="$seat_group,$groups"
    sudo usermod -aG "$groups" "$USER"
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
      -o "$HOME/$CHIME_FILE" "$REPO_RAW/sheepshaver/chimes/${CHIME_NAME}.wav"
    run "[sheepshaver] Fetching crash sound: $CRASH_NAME" curl -fL --retry 3 \
      -o "$HOME/crash.wav" "$REPO_RAW/sheepshaver/chimes/${CRASH_NAME}.wav"
  fi

  if [[ -x /usr/local/bin/SheepShaver ]]; then
    : # already installed; no steps consumed
  else
    run "[sheepshaver] Cloning macemu (kanjitalk755 HEAD)" \
      bash -c "[[ -d '$MACEMU_DIR/.git' ]] || git clone https://github.com/kanjitalk755/macemu.git '$MACEMU_DIR'"

    prepare_build() {
      cd "$MACEMU_DIR/SheepShaver" || return $?
      make links || return $?
      cd src/Unix || return $?
      local extra_cflags=""
      [[ $PERF -eq 1 ]] && extra_cflags=" -mcpu=cortex-a53 -mtune=cortex-a53"
      CFLAGS="-DMEM_BULK -g -O3${extra_cflags}" \
      CXXFLAGS="-DMEM_BULK -g -O3${extra_cflags}" \
      ./autogen.sh || return $?
    }
    run "[sheepshaver] Configuring build" prepare_build

    do_build() {
      cd "$MACEMU_DIR/SheepShaver/src/Unix" || return $?
      make -j"$(nproc)" || return $?
    }
    run_long "[sheepshaver] Building SheepShaver" do_build

    run "[sheepshaver] Installing SheepShaver binary" \
      sudo install -m755 "$MACEMU_DIR/SheepShaver/src/Unix/SheepShaver" /usr/local/bin/SheepShaver
  fi

  install_launcher() {
    sudo tee /usr/local/bin/sheepshaver.sh >/dev/null <<'LAUNCHER'
#!/bin/bash
# Launches SheepShaver fullscreen via cage on the current TTY.
# Relaunch: exit 0 (Mac Shut Down) or 143 (double-reset) -> Pi prompt;
# crash -> relaunch; Mac Restart reboots the VM in place.
clear 2>/dev/null
printf '\033[?25l' 2>/dev/null
setterm --cursor off 2>/dev/null || true

export XDG_RUNTIME_DIR=/tmp/runtime
export LIBSEAT_BACKEND=seatd
export SDL_VIDEODRIVER=x11
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

cd ~
aplay -q /usr/local/bin/chime.wav 2>/dev/null &

rm -f /tmp/sheepshaver.exit
cage -s -- sh -c '
  sleep 1
  wlr-randr --output DPI-1 --transform 270 2>/dev/null
  wlr-randr --output Unknown-1 --transform 270 2>/dev/null
  systemd-cat -t sheepshaver setarch -R SheepShaver
  echo $? > /tmp/sheepshaver.exit
'
rc=$(cat /tmp/sheepshaver.exit 2>/dev/null || echo 99)
rm -f /tmp/sheepshaver.exit

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
ignoreillegal false$extra
EOF
  }
  run "[sheepshaver] Writing prefs ($COLOR_LABEL / ${COLOR_DEPTH}bpp)" write_prefs

  config_autologin() {
    sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
    sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear --noissue --nohostname %I \$TERM
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
    local seat_group="" g
    for g in seat _seatd; do
      if getent group "$g" >/dev/null 2>&1; then seat_group=$g; break; fi
    done
    local groups="video,input,render"
    [[ -n $seat_group ]] && groups="$seat_group,$groups"
    sudo usermod -aG "$groups" "$USER"
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
      -o "$HOME/$CHIME_FILE" "$REPO_RAW/sheepshaver/chimes/${CHIME_NAME}.wav"
    run "[basilisk] Fetching crash sound: $CRASH_NAME" curl -fL --retry 3 \
      -o "$HOME/crash.wav" "$REPO_RAW/sheepshaver/chimes/${CRASH_NAME}.wav"
  fi

  if [[ -x /usr/local/bin/BasiliskII ]]; then
    : # already installed; no steps consumed
  else
    run "[basilisk] Cloning macemu (kanjitalk755 HEAD)" \
      bash -c "[[ -d '$MACEMU_DIR/.git' ]] || git clone https://github.com/kanjitalk755/macemu.git '$MACEMU_DIR'"

    # JIT is x86-only (interpreter on ARM). VOSF on: only changed screen regions
    # get re-blitted — meaningfully snappier UI, and stable on this Pi's aarch64.
    prepare_basilisk_build() {
      cd "$MACEMU_DIR/BasiliskII/src/Unix" || return $?
      local extra_cflags=""
      [[ $PERF -eq 1 ]] && extra_cflags=" -mcpu=cortex-a53 -mtune=cortex-a53"
      CFLAGS="-g -O3${extra_cflags}" \
      CXXFLAGS="-g -O3${extra_cflags}" \
      ./autogen.sh --enable-sdl-video --enable-sdl-audio \
        --disable-jit-compiler --enable-vosf || return $?
    }
    run "[basilisk] Configuring build (SDL, no JIT, VOSF)" prepare_basilisk_build

    do_basilisk_build() {
      cd "$MACEMU_DIR/BasiliskII/src/Unix" || return $?
      make -j"$(nproc)" || return $?
    }
    run_long "[basilisk] Building BasiliskII" do_basilisk_build

    run "[basilisk] Installing BasiliskII binary" \
      sudo install -m755 "$MACEMU_DIR/BasiliskII/src/Unix/BasiliskII" /usr/local/bin/BasiliskII
  fi

  install_basilisk_launcher() {
    sudo tee /usr/local/bin/basilisk.sh >/dev/null <<'LAUNCHER'
#!/bin/bash
# Launches BasiliskII fullscreen via cage on the current TTY.
# Relaunch: exit 0 (Mac Shut Down) or 143 (double-reset) -> Pi prompt;
# crash -> relaunch; Mac Restart reboots the VM in place.
clear 2>/dev/null
printf '\033[?25l' 2>/dev/null
setterm --cursor off 2>/dev/null || true

export XDG_RUNTIME_DIR=/tmp/runtime
export LIBSEAT_BACKEND=seatd
export SDL_VIDEODRIVER=x11
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

cd ~
aplay -q /usr/local/bin/chime.wav 2>/dev/null &

rm -f /tmp/basilisk.exit
cage -s -- sh -c '
  sleep 1
  wlr-randr --output DPI-1 --transform 270 2>/dev/null
  wlr-randr --output Unknown-1 --transform 270 2>/dev/null
  systemd-cat -t basilisk setarch -R BasiliskII
  echo $? > /tmp/basilisk.exit
'
rc=$(cat /tmp/basilisk.exit 2>/dev/null || echo 99)
rm -f /tmp/basilisk.exit

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
modelid 5
cpu 4
fpu true
nogui true
nosound false
jit false
jitfpu false
frameskip 2
idlewait true
ignoresegv true
EOF
  }
  run "[basilisk] Writing prefs ($COLOR_LABEL / ${COLOR_DEPTH}bpp / 640×480)" write_basilisk_prefs

  config_autologin_basilisk() {
    sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
    sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear --noissue --nohostname %I \$TERM
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

# --- Done -----------------------------------------------------------------
emit_gauge 100 "Done"
sleep 1
stop_gauge

printf '\n\033[1;32m✓ Setup complete.\033[0m  Rebooting in 5 seconds (Ctrl-C to cancel)…\n'
printf '  log: %s\n\n' "$LOG_FILE"
sleep 5
sudo reboot
