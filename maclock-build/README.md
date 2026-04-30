# Macintosh Mini hardware guide
This guide covers the hardware side: the wiring, the display drivers, and the helper scripts that make the dial control screen brightness and the buttons actually do things. The SheepShaver install is a [separate guide](../sheepshaver/).

## Video guide
I recorded a walkthrough for how I assembled mine that goes into much more detail than the written guide:
[<img height="300" alt="Frame 2" src="https://github.com/user-attachments/assets/345a346a-67c7-46be-971e-8b5e387e1155" />
](https://www.youtube.com/watch?v=zAbAf5-H5Yo)

## 0. Hardware
- [Maclock](https://www.aliexpress.us/w/wholesale-maclock.html)
- [Raspberry Pi Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
- [Waveshare 2.8 inch IPS LCD](https://www.waveshare.com/2.8inch-dpi-lcd.htm)
- [3D printed screen bezel](../maclock-screen-bezel)
- [Macintosh Mini breakout board](https://www.pcbway.com/orderonline.aspx?outsideid=802d4efa-7309-4b4f-bf3a-cc70d992479b) (if you want brightness, buttons, and sound). You can also [view the source files](../maclock-pcb).

## 1. Wiring

<img width="4363" height="1433" alt="Frame 2 1" src="https://github.com/user-attachments/assets/61e506e0-89fb-4ce9-9209-b47cebea9812" />

| Component       | Pin on breakout board | Pin on Pi Zero | Notes                      |
| --------------- | --------------------- | -------------- | -------------------------- |
| 5V              | 5V                    | 2              |                            |
| GND             | GND                   | 6              |                            |
| Button 1        | SW1                   | 13             | Bend or desolder pin on Pi |
| Rotary DT       | Dial B                | 19             | Bend or desolder pin on Pi |
| Rotary CLK      | Dial A                | 23             | Bend or desolder pin on Pi |
| Audio (PAM8302) | A+                    | 35             | Bend or desolder pin on Pi |
| Button 2        | SW2                   | 37             | Bend or desolder pin on Pi |

Bend, cut, or desolder pins 13, 19, 23, 35, and 37 so they don't plug into the Waveshare display board. Leaving them in can cause odd issues with the buttons and dial on the front of the Mac.

## 2. The software—quick install (recommended)

1. Install [Raspberry Pi OS (lite)](https://www.raspberrypi.com/software/) onto an SD card.

2. Copy over a [MacOS disk image](https://bluescsi.com/docs/BlueSCSI-Images) and [ROM](https://www.redundantrobot.com/sheepshaver) file. Any `.hda` filename works — the script auto-discovers them in `$HOME`.

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

# Audio — PWM on GPIO 18+19, only 19 is physically wired
dtparam=audio=on
dtoverlay=audremap,pins_18_19
disable_audio_dither=1

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

The stock `waveshare-28dpi-3b-4b` overlay claims GPIO 10, 11 (I2C for touch) and GPIO 18 (backlight driver). The custom overlay in this repo strips those fragments, freeing the pins.

Compile and install the overlay (source: [`waveshare-28dpi-3b-4b-notouch.dts`](./waveshare-28dpi-3b-4b-notouch.dts)):

```bash
curl -fLO https://raw.githubusercontent.com/wr/macintosh-mini/main/maclock-build/waveshare-28dpi-3b-4b-notouch.dts
dtc -I dts -O dtb -o waveshare-28dpi-3b-4b-notouch.dtbo waveshare-28dpi-3b-4b-notouch.dts
sudo cp waveshare-28dpi-3b-4b-notouch.dtbo /boot/firmware/overlays/
sudo reboot
```

Once you reboot your Pi, the screen should start working.

---

### 2. Buttons and brightness dial

Two helpers drive the rotary encoder behind the brightness dial and the two pushbuttons on the front:

- [`brightness_control.py`](./brightness_control.py) — gray-code rotary encoder reader, drives software PWM on GPIO 18 for backlight
- [`button_handler.py`](./button_handler.py) — debounced falling-edge handlers for the two front buttons. Edit the `COMMANDS` dict to change what each button does (defaults: BTN1 = shutdown, BTN2 = restart SheepShaver)

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

### 4. Install SheepShaver

The hardware side of the maclock is now done. Follow the [SheepShaver guide](../sheepshaver/) to build SheepShaver, configure prefs, and set up auto-launch on `tty1`. That guide places `sheepshaver.sh`, `chime.wav`, `crash.wav`, and `sheepshaver-restart.sh` in `/usr/local/bin/` — the autologin chain plays the chime and starts SheepShaver, and pressing Button 2 calls `sheepshaver-restart.sh` (plays the crash sound, relaunches).

---

## Known Issues

**Backlight flicker at low brightness.** Software PWM on the single-core Pi Zero W has CPU jitter. The `audremap` overlay claims both PWM channels (GPIO 18 + 19), blocking hardware PWM on GPIO 18.
