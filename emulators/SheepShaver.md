# SheepShaver on Raspberry Pi Zero 2 W

This guide covers the software side: getting SheepShaver (a classic Mac emulator) to run on the Pi Zero. The [hardware build](../maclock-build) is a separate guide.

> SheepShaver runs PowerPC Mac OS (8.1+) and is **slow** on the Pi Zero. **Basilisk II** (68k) is the [setup script](../setup.sh) default and much faster (see the [Basilisk II guide](./BasiliskII.md)) — use this guide only if you specifically need PPC-era software.

> [!TIP]
> Did you find my work useful? [Your support](https://buymeacoffee.com/wellsriley) helps fund future projects. Thank you!


## Quick install

1. Install [Raspberry Pi OS (lite) 64-bit](https://www.raspberrypi.com/software/) onto an SD card.

2. Copy over a [MacOS disk image](https://bluescsi.com/docs/BlueSCSI-Images) and [ROM](https://www.redundantrobot.com/sheepshaver) file. Any `.hda` filename works — the script auto-discovers them in `$HOME` and prompts you to choose if there's more than one.

   ```bash
   scp ROM yourdisk.hda <user>@<pi_ip>:~/
   ```
3. SSH into the Pi and run:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/wr/macintosh-mini/main/setup.sh | bash
   ```
   
4. The script will reboot your Pi when done, and it should Just Work™️

## Alternative: manual install

You can also do everything the script does by yourself by following these steps:

### 1. Install dependencies

Build tools, runtime libraries, and the kiosk stack:

```bash
sudo apt update
sudo apt install -y \
  build-essential autoconf automake libtool pkg-config \
  libsdl2-dev libgtk-3-dev libgl1-mesa-dev libxkbcommon-dev \
  cage wlr-randr seatd \
  git
```

Enable the seat manager and put yourself in the right groups. The seatd group is `seat` on some distros and `_seatd` on Debian Trixie — adjust if `seat` doesn't exist:

```bash
sudo systemctl enable --now seatd
sudo usermod -aG _seatd,video,input,render "$USER"   # use `seat` instead of `_seatd` on older distros
```

Log out and back in (or reboot) so the new group memberships take effect.

### 2. Kernel settings (sysctl)

Both values are required on aarch64, and must be active **before** running `./autogen.sh`:

```bash
sudo tee /etc/sysctl.d/60-sheepshaver.conf <<'EOF'
vm.mmap_min_addr=0
vm.overcommit_memory=1
EOF
sudo sysctl --system
```

- `vm.mmap_min_addr=0` lets SheepShaver map Mac low-memory globals at address `0x0`. Configure's SIGSEGV-recovery probe also needs this; if it isn't 0 yet, the probe fails silently, the configure summary shows `Bad memory access recovery type ..: ` empty, and `sigsegv.cpp` won't compile.
- `vm.overcommit_memory=1` allows the ~1.58 GB virtual reservation that `MEM_BULK` makes upfront (physical pages are still allocated lazily on first touch).

### 3. Build SheepShaver

Clone and prepare the source:

```bash
cd ~
git clone https://github.com/kanjitalk755/macemu.git
cd macemu/SheepShaver
make links
cd src/Unix
./autogen.sh
```

Patch the generated `Makefile` to add `-DMEM_BULK` (required on aarch64) and bump `-O2` → `-O3`:

```bash
sed -i 's|^CXXFLAGS = -g -O2|CXXFLAGS = -DMEM_BULK -g -O3|' Makefile
sed -i 's|^CFLAGS = -g -O2|CFLAGS = -DMEM_BULK -g -O3|' Makefile
```

Build and install (takes a while on a Zero 2 W):

```bash
make -j"$(nproc)"
sudo install -m755 SheepShaver /usr/local/bin/SheepShaver
```

### 4. Place files and launcher script

For the manual install, drop this into `/usr/local/bin/sheepshaver.sh`:

```bash
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
```

Grab a startup chime from this repo (replace `StartupMacII` with any name from [`chimes/`](./chimes/)) and install both:

```bash
curl -fL -o chime.wav https://raw.githubusercontent.com/wr/macintosh-mini/main/emulators/chimes/StartupMacII.wav
sudo install -m644 chime.wav /usr/local/bin/chime.wav
sudo install -m755 sheepshaver.sh /usr/local/bin/sheepshaver.sh
```

### 5. SheepShaver preferences

```sh
nano ~/.sheepshaver_prefs
```

```text
disk <your-disk-image>.hda
rom ROM
screen dga/640/480/16
ramsize 67108864
modelid 5
cpu 4
fpu true
nogui true
nosound false
ether slirp
ignoreillegal false
```

The trailing `/16` on the `screen` line is the bit depth: `1` for B&W, `8` for 256 colors / grayscale (set Mac OS Monitors → Grays for true grayscale), `16` for thousands of colors. Mac OS persists its own depth in the disk image too — if your settings don't take, also set Monitors inside Mac OS.

For better performance, bump `ramsize 67108864` (64 MB) to `134217728` (128 MB) and add `sound_buffer 4096` on its own line. The setup script's `--perf` mode applies these by default. Building with `-mcpu=cortex-a53 -mtune=cortex-a53` in CFLAGS/CXXFLAGS gives another small win on Pi Zero 2 W.

The `ether slirp` line gives the Mac networking via user-mode NAT — no host setup needed. Inside Mac OS, set TCP/IP to **DHCP**. For file sharing, point the Chooser's **Server IP Address** button at the server (AppleTalk doesn't cross slirp).

### 6. Autologin on `tty1`

Override the getty service so your user is logged in automatically when `tty1` starts:

```bash
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear --noissue --nohostname %I \$TERM
EOF
sudo systemctl daemon-reload
```

### 7. Auto-launch SheepShaver on `tty1`

Append to `~/.profile`:

```bash
cat >> ~/.profile <<'EOF'

# Auto-start SheepShaver on tty1 (after autologin)
if [ "$(tty)" = "/dev/tty1" ] && [ -z "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
    exec /usr/local/bin/sheepshaver.sh
fi
EOF
```

### 8. Quiet boot (optional but recommended)

Send kernel/systemd console messages to `tty3` so `tty1` stays black until SheepShaver takes over, and silence the MOTD + last-login banner that flashes on every restart:

```bash
sudo sed -i 's|$| quiet loglevel=0 vt.global_cursor_default=0 console=tty3 logo.nologo|' /boot/firmware/cmdline.txt
touch ~/.hushlogin
```

### 9. Boot it

```bash
sudo reboot
```

The Pi should autologin on `tty1`, source `~/.profile`, `exec` the launcher, and within a few seconds you should be looking at the Mac OS happy-Mac and boot screen.
