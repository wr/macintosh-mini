# Manual install

Everything the [installer](../setup.sh) sets up on the Pi, step by step: the display, audio, backlight, brightness dial and buttons. You don't need this page if you ran the installer. It's for setting the Pi up by hand, or seeing what the installer changed. To build a Macintosh Mini, start with the [build guide](../BUILD.md).

Start from a fresh install of [Raspberry Pi OS Lite (64-bit)](https://www.raspberrypi.com/software/) with SSH turned on. When this page is done, [install the emulator](../emulators/).

## 1. Display, audio and backlight

Install the tools this step uses, then Waveshare's overlays for the display. [28DPI-DTBO.zip](https://files.waveshare.com/wiki/2.8inc-DPI-LCD/28DPI-DTBO.zip), from the [Waveshare wiki](https://www.waveshare.com/wiki/2.8inch_DPI_LCD), is the latest as of this writing.

```bash
sudo apt-get install -y device-tree-compiler unzip
wget https://files.waveshare.com/wiki/2.8inc-DPI-LCD/28DPI-DTBO.zip
unzip 28DPI-DTBO.zip && sudo cp 28DPI-DTBO/*.dtbo /boot/firmware/overlays/
```

Two stock overlays get in the way, so this repo replaces both:

- The stock `waveshare-28dpi-3b-4b` overlay claims GPIO 10 and 11 (I2C for touch) and GPIO 18 (backlight driver). [`waveshare-28dpi-3b-4b-notouch.dts`](./waveshare-28dpi-3b-4b-notouch.dts) strips those fragments, freeing the pins.
- The stock `audremap,pins_18_19` overlay hands the audio firmware both GPIO 18 and 19, even though only 19 is wired to the amp. That claim on 18 blocks every PWM driver from using it for the backlight:

  ```
  pinctrl-bcm2835: pin gpio18 already requested by 3f00b840.mailbox;
                   cannot claim for pwm_gpio@12
  ```

  [`audremap-pin19.dts`](./audremap-pin19.dts) maps audio to GPIO 19 alone, which leaves 18 free.

Compile and install both:

```bash
for o in waveshare-28dpi-3b-4b-notouch audremap-pin19; do
  curl -fLO https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/$o.dts
  dtc -I dts -O dtb -o $o.dtbo $o.dts
  sudo cp $o.dtbo /boot/firmware/overlays/
done
```

Add this to the end of `/boot/firmware/config.txt`:

```ini
# Display — custom overlay (no touch, no kernel backlight)
dtoverlay=waveshare-28dpi-3b-4b-notouch
dtoverlay=waveshare-28dpi-3b
dtoverlay=waveshare-28dpi-4b
#dtoverlay=waveshare-touch-28dpi
# rotate=90 sets the DRM panel-orientation, honored at init by the console
# and by labwc (emulator), so the first frame is already rotated
dtoverlay=vc4-kms-dpi-2inch8,rotate=90

# Audio — PWM on GPIO 19 only, which is the one physically wired
dtparam=audio=on
dtoverlay=audremap-pin19
disable_audio_dither=1

# Backlight — kernel software PWM on GPIO 18
dtoverlay=pwm-gpio,gpio=18

# Boot speed
initial_turbo=30
boot_delay=0
disable_splash=1
```

Then reboot:

```bash
sudo reboot
```

Once you reboot your Pi, the screen should start working.

---

## 2. Buttons and brightness dial

Two helpers drive the brightness dial and the two buttons on the front:

- [`brightness_control.py`](./brightness_control.py) samples the dial every 1 ms, decodes the gray code, and sets the backlight through the kernel `pwm-gpio` driver on GPIO 18 (`/sys/class/pwm`).
- [`button_handler.py`](./button_handler.py) handles the buttons. By default the right button (SW1, GPIO 27) shuts the Pi down, and the left button (SW2, GPIO 26) restarts the emulator, or quits to a prompt when pressed twice. Edit the `COMMANDS` and `DOUBLE_COMMANDS` dicts to change them.

Install both to `/usr/local/bin/`:

```bash
curl -fL -o brightness_control.py https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/brightness_control.py
curl -fL -o button_handler.py     https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/button_handler.py

sudo apt-get install -y python3-lgpio
sudo install -m755 brightness_control.py /usr/local/bin/brightness_control.py
sudo install -m755 button_handler.py     /usr/local/bin/button_handler.py
```

The left button runs two small scripts. Install them too. `sheepshaver-restart.sh` restarts whichever emulator is installed; the name is historical.

```bash
sudo tee /usr/local/bin/sheepshaver-restart.sh >/dev/null <<'EOF'
#!/bin/bash
# Left button: stop the emulator, play the crash sound, relaunch.
systemctl stop getty@tty1.service
sleep 0.5
[[ -f /usr/local/bin/crash.wav ]] && aplay -q /usr/local/bin/crash.wav 2>/dev/null
systemctl start getty@tty1.service
EOF

sudo tee /usr/local/bin/macintosh-quit.sh >/dev/null <<'EOF'
#!/bin/bash
# Left button, pressed twice: quit the emulator (exit 143), so the launcher
# drops to a Pi prompt instead of relaunching.
pkill -TERM -x BasiliskII 2>/dev/null
pkill -TERM -x SheepShaver 2>/dev/null
EOF

sudo chmod 755 /usr/local/bin/sheepshaver-restart.sh /usr/local/bin/macintosh-quit.sh
```

---

## 3. Systemd services

Service files: [`brightness-control.service`](./brightness-control.service), [`button-handler.service`](./button-handler.service).

```bash
curl -fL -o brightness-control.service https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/brightness-control.service
curl -fL -o button-handler.service     https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/button-handler.service

sudo install -m644 brightness-control.service /etc/systemd/system/brightness-control.service
sudo install -m644 button-handler.service     /etc/systemd/system/button-handler.service

sudo systemctl daemon-reload
sudo systemctl enable --now brightness-control button-handler
```

### Night dimming (optional)

The dial script can follow the sun:

- From sunset, the backlight runs at half the dial level.
- From 10 pm, the screen goes dark until an hour before sunrise.
- At sunrise, it comes back to wherever the dial was.
- Turning the dial at night wakes the screen until the next sunset.

Sunrise and sunset are worked out on the Pi, offline, for the reference city of the system timezone, from the coordinates in tzdata's zone tables. Stock Pi OS images are set to Europe/London, so set your timezone first. The installer shows the zone and offers a picker; by hand:

```bash
sudo timedatectl set-timezone America/New_York   # timedatectl list-timezones
sudo tee /etc/default/brightness-control >/dev/null <<'EOF'
NIGHT_DIM=1
LAT=
LON=
NIGHT_FACTOR=0.5
NIGHT_OFF_AT=22:00
EOF
sudo systemctl restart brightness-control
```

| Setting | What it does |
| --- | --- |
| `NIGHT_DIM` | `1` turns night dimming on. |
| `LAT`, `LON` | Optional. Your latitude and longitude in decimal degrees (north and east positive), if the timezone's city is far from you. |
| `NIGHT_FACTOR` | Scales the dial level between sunset and sunrise. |
| `NIGHT_OFF_AT` | When the screen goes dark. Leave it blank to only dim. |

Edge cases:

- A cutoff earlier than sunset (a midsummer 22:08 sunset under the 22:00 default) means dark from sunset.
- In polar night the screen only dims, since no sunrise would end the dark.
- The Pi has no clock battery, so the schedule stays off until NTP has set the time.
- A boot after the cutoff dims for the first ten minutes instead of coming up dark, then goes dark unless the dial is turned.

---

## 4. Keep the Wi-Fi awake

The Pi Zero 2 W ships with Wi-Fi power saving on. The radio parks itself when nothing is talking to it, so the Pi falls off the network while idle and is slow to answer when you come back: SSH hangs for a while before it wakes up. The installer turns power saving off unless you pass `--wifi-powersave`.

Turn it off in three places, so it holds whether NetworkManager is driving the link or not:

```bash
# 1. NetworkManager's default for new connections
printf '[connection]\nwifi.powersave = 2\n' \
  | sudo tee /etc/NetworkManager/conf.d/99-wifi-powersave-off.conf

# 2. the Wi-Fi profile you are already on
sudo nmcli connection modify "<your-ssid>" 802-11-wireless.powersave 2

# 3. a boot-time unit, for anything NetworkManager does not manage
sudo tee /etc/systemd/system/wifi-powersave-off.service <<'UNIT'
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
sudo systemctl enable --now wifi-powersave-off
```

Apply it to the running radio too, so you do not have to reboot, and check it took:

```bash
sudo iw dev wlan0 set power_save off
sudo iw dev wlan0 get power_save
```

You want `Power save: off`. `iw` lives in `/usr/sbin`, which is not on a normal user's `PATH` over SSH, hence the `sudo`.

Do **not** restart NetworkManager to apply this. It drops the Wi-Fi, which cuts the SSH session you are running these commands over.

---

## 5. Install the emulator

The Pi side is done. Next, [install the emulator](../emulators/).

---

## Design notes

**No hardware PWM for the backlight.** The Pi's PWM peripheral has two channels and the analogue audio output uses both of them, so the backlight cannot have one. Enabling a hardware PWM channel does work — the backlight dims perfectly — but it kills sound for the rest of the boot, and disabling it again does not bring sound back:

```
aplay: pcm_write:2178: write error: Input/output error
```

The kernel `pwm-gpio` driver sidesteps this. It toggles GPIO 18 from an hrtimer and never touches the PWM peripheral, so audio keeps both channels. At 1 kHz it costs under 4% CPU and shows no visible flicker down to 5% brightness, even with all four cores pinned.

**Sample the dial, do not chase its edges.** The encoder bounces hard — one flick throws hundreds of transitions, some as close together as 19 microseconds. Sampling the two pins every 1 ms steps over that chatter. Decoding every edge instead, which is what the kernel `rotary-encoder` driver does, reads the direction backwards on roughly one flick in five.

Measured across ten flicks, five each way, on a healthy unit:

| decoder                  | flicks decoded correctly |
| ------------------------ | ------------------------ |
| every edge               | 8 / 10                   |
| sampled 250 us to 6 ms   | 10 / 10                  |

Anything in that sampling range works, so 1 ms is a middle choice that costs about 4% of one core.

**A worn encoder cannot be fixed in software.** If the dial jumps around or moves the wrong way, capture the raw pins and decode the capture offline before touching the code. On a good encoder each flick nets 8 to 10 counts in one direction. A bad one nets one or two, with no consistent sign, and no sample rate rescues it — the direction is simply not in the signal. Mushy detents are the tell. Clean the contacts or replace the encoder.

`ENC_A` and `ENC_B` get no pull-up and no filter cap on the breakout board — they lean on the Pi's internal ~50 kΩ — and that turns out to be fine. Adding a 10 kΩ pull-up was tried and reverted: against a contact that has gone resistive it makes the low level *worse*, and the 100 nF that usually goes with it has a time constant longer than the gaps between real transitions. Sampling every 1 ms is the fix; the hardware needs nothing.

---

## Known issues

**cloud-init owns the hostname, and `hostnamectl` alone will not stick.** Current Pi OS images ship cloud-init, whose `update_hostname` module runs on *every* boot and rewrites the name from its own config. Set the hostname by hand and it comes back as the old one after a reboot.

Editing `hostname:` in `/boot/firmware/user-data` does not help either. cloud-init caches user-data per instance and does not re-read that file unless the instance ID changes, so it keeps applying the name it first saw. The fix is to tell it to stop managing the hostname:

```bash
printf 'preserve_hostname: true\n' \
  | sudo tee /etc/cloud/cloud.cfg.d/99-preserve-hostname.cfg
sudo hostnamectl set-hostname <your-name>
```

If `/etc/hosts` still shows the old name as an alias on the `127.0.1.1` line, that is cloud-init's `manage_etc_hosts`, which comes from the image's user-data and outranks anything in `cloud.cfg.d`. Comment the module out of the list in `/etc/cloud/cloud.cfg`:

```
# - update_etc_hosts
```

The setup script does all of this for you when you give it a hostname.

**Audio buzz at low brightness.** The onboard analogue audio is PWM on a digital pin next to the display's, so it picks up interference. Nothing on the software side fixes it — a USB DAC does.
