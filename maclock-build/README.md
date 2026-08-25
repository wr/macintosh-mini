# Macintosh Mini hardware guide
This guide covers the hardware side: the wiring, the display drivers, and the helper scripts that make the dial control screen brightness and the buttons actually do things. The emulator install is a [separate guide](../emulators/).

<a href="https://www.buymeacoffee.com/wellsworkshop"><img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=wellsworkshop&button_colour=FFDD00&font_colour=000000&font_family=Arial&outline_colour=000000&coffee_colour=ffffff" /></a>

## Video guide
I recorded a walkthrough for how I assembled mine that goes into much more detail than the written guide:
[<img height="300" alt="Frame 2" src="https://github.com/user-attachments/assets/345a346a-67c7-46be-971e-8b5e387e1155" />
](https://www.youtube.com/watch?v=zAbAf5-H5Yo)

## 0. Hardware
- [Maclock](https://amzn.to/4e7FKrw)
- [Raspberry Pi Zero 2 W](https://amzn.to/4ac7FVR)
- [Waveshare 2.8 inch IPS LCD](https://amzn.to/4ue5GaP)
- [Adafruit PAM8302 audio amp](https://amzn.to/4uITeAP) + small speaker
- [3D printed screen bezel](../maclock-screen-bezel)
- [Macintosh Mini breakout board](https://www.pcbway.com/project/shareproject/W654223ASS41_Untitled_kicad_pcb_95cca7e3.html) (if you want brightness, buttons, and sound). Full [bill of materials here](../maclock-pcb).

## 1. Wiring

<img width="4363" height="1433" alt="Frame 2 1" src="https://github.com/user-attachments/assets/61e506e0-89fb-4ce9-9209-b47cebea9812" />

| Component       | Pin on breakout board | Pin on Pi Zero | Notes                      |
| --------------- | --------------------- | -------------- | -------------------------- |
| 3V3             | 3V3                   | 1              | Feeds the dial pull-ups    |
| 5V              | 5V                    | 2              |                            |
| GND             | GND                   | 6              |                            |
| Button 1        | SW1                   | 13             | Bend or desolder pin on Pi |
| Rotary DT       | Dial B                | 19             | Bend or desolder pin on Pi |
| Rotary CLK      | Dial A                | 23             | Bend or desolder pin on Pi |
| Audio (PAM8302) | A+                    | 35             | Bend or desolder pin on Pi |
| Button 2        | SW2                   | 37             | Bend or desolder pin on Pi |

Bend, cut, or desolder pins 13, 19, 23, 35, and 37 so they don't plug into the Waveshare display board. Leaving them in can cause odd issues with the buttons and dial on the front of the Mac.

## 2. The software—quick install (recommended)

1. Install [Raspberry Pi OS (lite) 64-bit](https://www.raspberrypi.com/software/) onto an SD card.

2. Copy over a [disk image](https://bluescsi.com/docs/BlueSCSI-Images) and a ROM file — the [main README](../) covers which ROM/disk to grab. The script auto-discovers them in `$HOME`.

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

### 1. Waveshare drivers

Download the latest overlays from the [Waveshare wiki](https://www.waveshare.com/wiki/2.8inch_DPI_LCD) — [2.8inch DPI LCD DTBO file](https://files.waveshare.com/wiki/2.8inc-DPI-LCD/28DPI-DTBO.zip) is the latest as of this writing.

```bash
# Download the drivers
wget https://files.waveshare.com/wiki/2.8inc-DPI-LCD/28DPI-DTBO.zip

# Unzip and install drivers
unzip 28DPI-DTBO.zip && sudo mv 28DPI-DTBO/* /boot/overlays
```

```sh
sudo nano /boot/firmware/config.txt
```

Append the following to the bottom:

```ini
# Display — custom overlay (no touch, no kernel backlight)
dtoverlay=waveshare-28dpi-3b-4b-notouch
dtoverlay=waveshare-28dpi-3b
dtoverlay=waveshare-28dpi-4b
#dtoverlay=waveshare-touch-28dpi
dtoverlay=vc4-kms-dpi-2inch8
display_rotate=3

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

```sh
sudo nano /boot/firmware/cmdline.txt
```

Append to the existing single line:

```sh
quiet logo.nologo
```

Two stock overlays get in the way, so this repo replaces both.

The stock `waveshare-28dpi-3b-4b` overlay claims GPIO 10, 11 (I2C for touch) and GPIO 18 (backlight driver). [`waveshare-28dpi-3b-4b-notouch.dts`](./waveshare-28dpi-3b-4b-notouch.dts) strips those fragments, freeing the pins.

The stock `audremap,pins_18_19` overlay hands the audio firmware both GPIO 18 and 19, even though only 19 is wired to the amp. That claim on 18 blocks every PWM driver from using it for the backlight:

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
sudo reboot
```

Once you reboot your Pi, the screen should start working.

---

### 2. Buttons and brightness dial

Two helpers drive the rotary encoder behind the brightness dial and the two pushbuttons on the front:

- [`brightness_control.py`](./brightness_control.py) — samples the dial every 1 ms, decodes the gray code, and sets the backlight through the kernel `pwm-gpio` driver on GPIO 18 (`/sys/class/pwm`)
- [`button_handler.py`](./button_handler.py) — debounced falling-edge handlers for the two front buttons. Edit the `COMMANDS` / `DOUBLE_COMMANDS` dicts to change what each does (defaults: BTN1 = shutdown; BTN2 single-press = restart the emulator, double-press = quit to a prompt)

Install both to `/usr/local/bin/`:

```bash
curl -fL -o brightness_control.py https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/brightness_control.py
curl -fL -o button_handler.py     https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/button_handler.py

sudo apt-get install -y python3-lgpio
sudo install -m755 brightness_control.py /usr/local/bin/brightness_control.py
sudo install -m755 button_handler.py     /usr/local/bin/button_handler.py
```

---

### 3. Systemd Services

Service files: [`brightness-control.service`](./brightness-control.service), [`button-handler.service`](./button-handler.service).

```bash
curl -fL -o brightness-control.service https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/brightness-control.service
curl -fL -o button-handler.service     https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/button-handler.service

sudo install -m644 brightness-control.service /etc/systemd/system/brightness-control.service
sudo install -m644 button-handler.service     /etc/systemd/system/button-handler.service

sudo systemctl daemon-reload
sudo systemctl enable --now brightness-control button-handler
```

---

### 4. Install the emulator

The hardware side of the maclock is now done. The [setup script](../setup.sh) installs **Basilisk II**; manual build steps are in the [Basilisk II guide](../emulators/BasiliskII.md) (or the [SheepShaver guide](../emulators/SheepShaver.md) for PowerPC).

---

## Known Issues

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

Note also that `ENC_A` and `ENC_B` get no pull-up and no filter cap on the breakout board, unlike the buttons and the encoder's push-switch (R1, R2, R3), so they lean on the Pi's weak internal pull-ups. 10K to 3V3 and 100nF to ground on both channels would be worth adding to a board revision.

**Audio buzz at low brightness.** The onboard analogue audio is PWM on a digital pin next to the display's, so it picks up interference. Nothing on the software side fixes it — a USB DAC does.
