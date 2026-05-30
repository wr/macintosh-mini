# Basilisk II on Raspberry Pi Zero 2 W

This guide covers the software side: getting Basilisk II (a 68k classic Mac emulator) to run on the Pi Zero. The [hardware build](../maclock-build) is a separate guide.

Basilisk II (68k) is the [setup script](../setup.sh) default and the fastest option on the Pi Zero — a 68k guest is far lighter to interpret than PowerPC. For PowerPC software (Mac OS 8.5+), see the [SheepShaver guide](./SheepShaver.md) instead.

> [!TIP]
> Did you find my work useful? [Your support](https://buymeacoffee.com/wellsriley) helps fund future projects. Thank you!

## Quick install

1. Install [Raspberry Pi OS (lite) 64-bit](https://www.raspberrypi.com/software/) onto an SD card.

2. Copy over a disk image and a **512 KB or 1 MB 68k ROM** (Mac IIci / Quadra — try searching online for `064DC91D`). Rename the ROM `ROM` (no extension). Any disk filename works — the script auto-discovers them in `$HOME`.

   ```bash
   scp ROM yourdisk.hda <user>@<pi_ip>:~/
   ```
3. SSH into the Pi and run:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/wr/macintosh-mini/main/setup.sh | bash
   ```
4. The script will reboot your Pi when done, and it should Just Work™️

## Alternative: manual install

You can also do everything the script does by yourself by following these steps.

### 1. Install dependencies

```bash
sudo apt update
sudo apt install -y \
  build-essential autoconf automake libtool pkg-config \
  libsdl2-dev libgtk-3-dev libgl1-mesa-dev libxkbcommon-dev libmpfr-dev \
  cage wlr-randr seatd alsa-utils \
  git
```

`libmpfr-dev` is required — Basilisk II emulates the 68k FPU with MPFR.

Enable the seat manager and add yourself to the right groups. The seatd group is `seat` on some distros and `_seatd` on Debian Trixie — adjust if `seat` doesn't exist:

```bash
sudo systemctl enable --now seatd
sudo usermod -aG _seatd,video,input,render "$USER"   # use `seat` instead of `_seatd` on older distros
```

Log out and back in (or reboot) so the new group memberships take effect.

### 2. Kernel setting (sysctl)

Basilisk II maps the Mac low-memory globals at address `0x0`, so it needs `mmap_min_addr=0` — and it must be active **before** running `./autogen.sh` (configure's SIGSEGV-recovery probe needs it too):

```bash
sudo tee /etc/sysctl.d/60-basilisk.conf <<'EOF'
vm.mmap_min_addr=0
EOF
sudo sysctl --system
```

(Unlike SheepShaver, Basilisk II doesn't need `vm.overcommit_memory=1` — it has no large upfront reservation.)

### 3. Build Basilisk II

```bash
cd ~
git clone https://github.com/kanjitalk755/macemu.git
cd macemu/BasiliskII/src/Unix
CFLAGS="-g -O3 -mcpu=cortex-a53 -mtune=cortex-a53" \
CXXFLAGS="-g -O3 -mcpu=cortex-a53 -mtune=cortex-a53" \
./autogen.sh --enable-sdl-video --enable-sdl-audio --disable-jit-compiler --enable-vosf
make -j"$(nproc)"
sudo install -m755 BasiliskII /usr/local/bin/BasiliskII
```

- The JIT is x86-only, so on ARM Basilisk II runs as an interpreter — `--disable-jit-compiler` is correct.
- `--enable-vosf` re-blits only the changed parts of the screen (snappier UI); stable on this Pi.
- No `-DMEM_BULK` needed — that's a SheepShaver-on-aarch64 fix; Basilisk II uses `DIRECT_ADDRESSING` here out of the box.
- `-mcpu=cortex-a53` is a small Pi Zero 2 W win.
- Low on RAM? Use `make -j2` — four parallel compiles can OOM on a 512 MB Pi.

### 4. Launcher script

Drop this into `/usr/local/bin/basilisk.sh`:

```bash
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
```

Grab a startup chime and crash sound from the repo (any names from [`chimes/`](./chimes/)) and install everything:

```bash
curl -fL -o chime.wav https://raw.githubusercontent.com/wr/macintosh-mini/main/emulators/chimes/StartupMacII.wav
curl -fL -o crash.wav https://raw.githubusercontent.com/wr/macintosh-mini/main/emulators/chimes/CrashMacII.wav
sudo install -m644 chime.wav /usr/local/bin/chime.wav
sudo install -m644 crash.wav /usr/local/bin/crash.wav
sudo install -m755 basilisk.sh /usr/local/bin/basilisk.sh
```

### 5. Basilisk II preferences

```sh
nano ~/.basilisk_ii_prefs
```

```text
disk <your-disk-image>.hda
rom ROM
screen win/640/480
displaycolordepth 8
ramsize 134217728
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
ether slirp
```

- `displaycolordepth` is the bit depth: `1` for B&W, `8` for 256 colors / grayscale, `16` for thousands.
- `modelid 5` is a Mac IIci — right for **System 7.x**. **Mac OS 8.1 needs `modelid 14`** (a Quadra; 8.1 dropped 68030 support) paired with a 1 MB ROM (e.g. `064DC91D`).
- `ether slirp` gives networking via user-mode NAT — no host setup. Inside Mac OS set TCP/IP to **DHCP**; for file sharing use the Chooser's **Server IP Address** button (AppleTalk doesn't cross slirp).

### 6. Autologin on `tty1`

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear --noissue --nohostname %I \$TERM
EOF
sudo systemctl daemon-reload
```

### 7. Auto-launch Basilisk II on `tty1`

```bash
cat >> ~/.profile <<'EOF'

# Auto-start BasiliskII on tty1 (after autologin)
if [ "$(tty)" = "/dev/tty1" ] && [ -z "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
    exec /usr/local/bin/basilisk.sh
fi
EOF
```

### 8. Quiet boot (optional but recommended)

```bash
sudo sed -i 's|$| quiet loglevel=0 vt.global_cursor_default=0 console=tty3 logo.nologo|' /boot/firmware/cmdline.txt
touch ~/.hushlogin
```

### 9. Boot it

```bash
sudo reboot
```

The Pi autologins on `tty1`, sources `~/.profile`, `exec`s the launcher, and within a few seconds you should see the happy-Mac boot screen.
