# Install the emulator

Build and set up the emulator by hand. This is the second half of a manual install, after [setting up the Pi](../maclock-build/). You don't need it if you ran the [installer](../setup.sh), which does all of this for you.

There are two emulators, both from [kanjitalk755's macemu](https://github.com/kanjitalk755/macemu). Pick one:

- **Basilisk II**, the installer's default, emulates a 68k Mac running System 7.0 to 8.5 and is the fastest choice on a Pi Zero 2 W. It needs a 512 KB or 1 MB 68k ROM from a Mac IIci or Quadra (`064DC91D` is a common one).
- **SheepShaver** emulates a PowerPC Mac running Mac OS 8.1 or later. It needs the 4 MB [PowerPC ROM](https://www.redundantrobot.com/sheepshaver) and is very slow on a Pi Zero, so choose it only for PowerPC-only software.

Rename your ROM file to `ROM` and copy it and a disk image to your home folder on the Pi. The [build guide](../BUILD.md#5-install-the-software) lists the disk image formats that work. Where the steps below differ between the two emulators, both versions are given.

## 1. Dependencies

```bash
sudo apt update
sudo apt install -y \
  build-essential autoconf automake libtool pkg-config \
  libsdl2-dev libgl1-mesa-dev libxkbcommon-dev libmpfr-dev \
  labwc wlr-randr seatd alsa-utils git
```

`libmpfr-dev` is for Basilisk II, which emulates the 68k FPU with MPFR. SheepShaver doesn't need it.

Enable the seat manager and add yourself to the graphics groups. The seatd group is `_seatd` on Debian Trixie and `seat` on some older distros; use whichever exists:

```bash
sudo systemctl enable --now seatd
sudo usermod -aG _seatd,video,input,render "$USER"
```

Log out and back in (or reboot) so the new groups take effect.

## 2. Kernel settings

Both emulators map the Mac's low-memory globals at address `0x0`, so they need `vm.mmap_min_addr=0`. SheepShaver also needs `vm.overcommit_memory=1` for the ~1.58 GB virtual reservation that `MEM_BULK` makes upfront; physical pages are still allocated lazily, on first touch.

Set these **before** building. Configure's SIGSEGV-recovery probe needs them too: if `mmap_min_addr` isn't 0 yet, the probe fails silently, the configure summary shows `Bad memory access recovery type ..: ` empty, and `sigsegv.cpp` won't compile.

```bash
# Basilisk II
echo 'vm.mmap_min_addr=0' | sudo tee /etc/sysctl.d/60-basilisk.conf

# SheepShaver
printf 'vm.mmap_min_addr=0\nvm.overcommit_memory=1\n' | sudo tee /etc/sysctl.d/60-sheepshaver.conf

sudo sysctl --system
```

## 3. Build

```bash
git clone https://github.com/kanjitalk755/macemu.git ~/macemu
```

Basilisk II:

```bash
cd ~/macemu/BasiliskII/src/Unix
CFLAGS="-g -O3 -mcpu=cortex-a53 -mtune=cortex-a53" \
CXXFLAGS="-g -O3 -mcpu=cortex-a53 -mtune=cortex-a53" \
./autogen.sh --enable-sdl-video --enable-sdl-audio --disable-jit-compiler --enable-vosf --with-gtk=no
make -j"$(nproc)"
sudo install -m755 BasiliskII /usr/local/bin/BasiliskII
```

The JIT is x86-only, so on ARM Basilisk II runs as an interpreter. `--enable-vosf` redraws only the parts of the screen that changed, which makes the UI snappier, and is stable on this Pi.

SheepShaver:

```bash
cd ~/macemu/SheepShaver
make links
cd src/Unix
CFLAGS="-DMEM_BULK -g -O3 -mcpu=cortex-a53 -mtune=cortex-a53" \
CXXFLAGS="-DMEM_BULK -g -O3 -mcpu=cortex-a53 -mtune=cortex-a53" \
./autogen.sh --with-gtk=no
make -j"$(nproc)"
sudo install -m755 SheepShaver /usr/local/bin/SheepShaver
```

`-DMEM_BULK` is required on aarch64.

For both:

- `--with-gtk=no` leaves out the emulator's GTK dialogs, so an alert is logged to the journal instead of opening a window nobody can click.
- `-mcpu=cortex-a53` is a small speed-up on the Pi Zero 2 W. The installer adds it when its performance option is on, which it is by default.
- The build takes a while. If it runs out of memory on a 512 MB Pi, use `make -j2`.

## 4. Launcher

The launcher runs the emulator fullscreen under labwc, a Wayland compositor, on the Pi's console. When the emulator exits, the launcher decides what happens next. Shut Down in Mac OS (exit code 0), or the left button pressed twice (exit code 143), drops to a Pi prompt. A crash plays the crash sound and relaunches. Restart in Mac OS restarts the Mac inside the emulator, without exiting.

First, labwc's config, which makes every window fullscreen with no title bar:

```bash
mkdir -p ~/.config/labwc
cat > ~/.config/labwc/rc.xml <<'XML'
<?xml version="1.0"?>
<labwc_config>
  <windowRules>
    <windowRule identifier="*" serverDecoration="no" matchOnce="true">
      <action name="ToggleFullscreen"/>
    </windowRule>
  </windowRules>
</labwc_config>
XML
```

Then `mac-session`, which labwc runs as its session. It starts the emulator, saves its exit code for the launcher, and closes labwc when the emulator quits. The screen is normally rotated by the `rotate=90` overlay from [setting up the Pi](../maclock-build/README.md#1-display-audio-and-backlight); the `wlr-randr` lines are a fallback in case it wasn't.

```bash
sudo tee /usr/local/bin/mac-session >/dev/null <<'EOF'
#!/bin/sh
# labwc session command: labwc -S "mac-session <tag> <binary> <exit file>"
tag=$1; bin=$2; exitfile=$3
if wlr-randr 2>/dev/null | grep -q "Transform: normal"; then
  for o in DPI-1 Unknown-1; do
    wlr-randr --output "$o" --transform 270 2>/dev/null && break
  done
fi
systemd-cat -t "$tag" setarch -R "$bin"
echo $? > "$exitfile"
EOF
sudo chmod 755 /usr/local/bin/mac-session
```

Then the launcher. This is the Basilisk II version; for SheepShaver, change the `EMU` line as the comment says and save it as `/usr/local/bin/sheepshaver.sh` instead.

```bash
sudo tee /usr/local/bin/basilisk.sh >/dev/null <<'EOF'
#!/bin/bash
# Launches the emulator fullscreen via labwc on the current TTY.
# Exit 0 (Mac Shut Down) or 143 (double press) -> Pi prompt; crash -> relaunch.
EMU=basilisk; BIN=BasiliskII   # SheepShaver: EMU=sheepshaver; BIN=SheepShaver
ulimit -c 0   # no core dumps when the reset button stops labwc mid-render
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

rm -f /tmp/$EMU.exit
labwc -S "/usr/local/bin/mac-session $EMU $BIN /tmp/$EMU.exit"
rc=$(cat /tmp/$EMU.exit 2>/dev/null || echo 99)
rm -f /tmp/$EMU.exit

if [ "$rc" = "0" ] || [ "$rc" = "143" ]; then
  clear 2>/dev/null
  setterm --cursor on 2>/dev/null || true
  exec bash
fi

[ -f /usr/local/bin/crash.wav ] && aplay -q /usr/local/bin/crash.wav 2>/dev/null
EOF
sudo chmod 755 /usr/local/bin/basilisk.sh
```

Install a startup chime and a crash sound. Any of the files in [`chimes/`](./chimes/) work:

```bash
curl -fL -o chime.wav https://raw.githubusercontent.com/wr/macintosh-mini/main/emulators/chimes/StartupMacII.wav
curl -fL -o crash.wav https://raw.githubusercontent.com/wr/macintosh-mini/main/emulators/chimes/CrashMacII.wav
sudo install -m644 chime.wav crash.wav /usr/local/bin/
```

And the `macintosh` command, which starts the Mac again from a Pi prompt:

```bash
printf '#!/bin/bash\nexec sudo systemctl restart getty@tty1\n' | sudo tee /usr/local/bin/macintosh >/dev/null
sudo chmod 755 /usr/local/bin/macintosh
```

The installer also does two things this guide skips. It installs an invisible cursor theme for labwc, so its pointer doesn't flash on screen before the emulator starts. And it checks for a ROM and disk image before every boot, explaining on screen if one is missing. Both are in [`setup.sh`](../setup.sh) (`write_labwc_kiosk` and `write_preflight`).

## 5. Preferences

**Basilisk II.** Save this as `~/.basilisk_ii_prefs`:

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

- `displaycolordepth` is the bit depth: `1` for black and white, `8` for 256 colors or grayscale, `16` for thousands of colors.
- `ramsize 134217728` is 128 MB, what the installer uses with its performance option on. Without it, the installer uses 64 MB (`67108864`).
- **`modelid` must match the Mac OS version you boot.** `5` is a Mac IIci, right for System 7.0 and 7.1. `14` is a Quadra, required for System 7.5 and later, including Mac OS 8, which don't support the IIci's 68030; pair it with a 1 MB ROM such as `064DC91D`. The wrong one gives a sad Mac at boot: change the value and try again.

**SheepShaver.** Save this as `~/.sheepshaver_prefs`:

```text
disk <your-disk-image>.hda
rom ROM
screen dga/640/480/16
ramsize 134217728
modelid 5
cpu 4
fpu true
nogui true
nosound false
ether slirp
ignoreillegal false
sound_buffer 4096
```

- The `/16` at the end of the `screen` line is the bit depth: `1` for black and white, `8` for 256 colors or grayscale (set Monitors to Grays in Mac OS for true grayscale), `16` for thousands of colors. Mac OS also saves its own depth in the disk image, so if a setting doesn't take, set it in Monitors too.
- `ramsize 134217728` (128 MB) and `sound_buffer 4096` are what the installer's performance option uses. Without it, the installer uses 64 MB (`67108864`) and no `sound_buffer` line.

**Networking.** `ether slirp` gives the Mac networking through user-mode NAT, with no setup on the Pi. In Mac OS, set TCP/IP to DHCP. For file sharing, use the Chooser's Server IP Address button; AppleTalk doesn't cross slirp.

## 6. Start it at boot

Log in automatically on the Pi's console, `tty1`:

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --skip-login --noclear --noissue --nohostname %I \$TERM
EOF
sudo systemctl daemon-reload
```

Start the launcher when that login happens. For SheepShaver, use `sheepshaver.sh` and `sheepshaver-autostart` instead:

```bash
cat >> ~/.profile <<'EOF'

# >>> basilisk-autostart >>>
# Auto-start BasiliskII on tty1 (after autologin)
if [ "$(tty)" = "/dev/tty1" ] && [ -z "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
    exec /usr/local/bin/basilisk.sh
fi
# <<< basilisk-autostart <<<
EOF
```

Optionally, keep the boot quiet. This sends kernel and systemd messages to `tty3`, so `tty1` stays black until the Mac appears, and turns off the login banner:

```bash
sudo sed -i 's|$| quiet loglevel=0 vt.global_cursor_default=0 console=tty3 logo.nologo systemd.show_status=0|' /boot/firmware/cmdline.txt
touch ~/.hushlogin
```

Then reboot:

```bash
sudo reboot
```

The Pi logs in on `tty1`, `~/.profile` starts the launcher, and within a few seconds you should see the happy Mac.
