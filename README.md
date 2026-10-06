<h1 align="center"><img width="50" alt="happy macs" align="center" src="https://github.com/user-attachments/assets/cb2fd525-ec2b-48ac-8d7f-acda3212f89b" /> Macintosh Mini</h1>

<p align="center">
  <strong>Turn a Maclock alarm clock into a working Mac with a Raspberry Pi</strong>
</p>

<p align="center">
  <a href="BUILD.md">Build guide</a> ⬪
  <a href="#step-2-install-the-software">Install the software</a> ⬪
  <a href="https://shop.wells.ee/products/macintosh-mini/?ref=gh-macintosh-mini">Buy a kit</a> ⬪
  <a href="#donate">Donate</a>
</p>

<p align="center">
  <a href="https://www.youtube.com/watch?v=zAbAf5-H5Yo"><img height="300" alt="Macintosh Mini booting into System 7" src="https://github.com/user-attachments/assets/345a346a-67c7-46be-971e-8b5e387e1155" /></a>
  <br />
  <a href="https://www.youtube.com/watch?v=zAbAf5-H5Yo">⏵ Watch the full build on YouTube</a>
</p>

---

## What is it?

A [Maclock](https://www.aliexpress.us/w/wholesale-maclock.html) is a cheap alarm clock built into a shockingly accurate miniature Macintosh shell. This project guts one and rebuilds it around a Raspberry Pi Zero running a 68k or PowerPC emulator, so the tiny Mac actually boots System 7, plays the startup chime, and runs vintage software. Buttons, brightness, sound, Wi-Fi, Bluetooth, and battery all work.

## Step 1: Build or buy one

The [build guide](BUILD.md) covers everything from opening the clock to the first boot: parts, assembly, software, and troubleshooting.

You can [buy a DIY kit or a finished build](https://shop.wells.ee/products/macintosh-mini/?ref=gh-macintosh-mini) from my maker shop. Faster than shipping from China, and your purchase supports the continued development of this project.

<p align="center">
  <img height="220" alt="Macintosh Mini breakout PCB rotating" src="./docs/maclock-breakout.webp" />
</p>

## Step 2: Install the software

**You will need:**
- A Mac ROM file (`064DC91D` is a common one to search for)
- A Mac OS disk image with System 7.0 to 8.5. The [BlueSCSI image library](https://bluescsi.com/docs/BlueSCSI-Images) has ready-made ones

**Prepare the MicroSD card**
1. Flash **Raspberry Pi OS Lite (64-bit)** to a microSD card with [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Set your Wi-Fi network and turn on SSH in its settings.
2. Rename your Mac ROM file to `ROM`, and copy it and a disk image to the Pi's home folder:

   ```bash
   scp ROM yourdisk.hda <user>@<pi_ip>:~/
   ```

3. The install script is automatic, and guides you through customizations like choosing a boot chime. SSH into the Pi and run:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/wr/macintosh-mini/main/setup.sh | bash
   ```

The Pi automatically restarts into Mac OS when it's done.

You can run the same command again to install future updates.

* * *

_Optional:_ If you want to skip the automatic script and install everything yourself, or see exactly what the script changes:

- [Set up the Pi](maclock-build/): display, audio, brightness dial and buttons.
-  [Install the emulator](emulators/): Basilisk II or SheepShaver.

## Getting help

Open a [GitHub issue](https://github.com/wr/macintosh-mini/issues) — I'm happy to help, and very responsive!

## Credits

Startup chimes and crash sounds are mirrored from D. Schaub's Apple Sounds collection at <https://froods.ca/~dschaub/sound.html>. All sounds are © Apple, Inc.

## Donate

While this project is free and open source, donations are deeply appreciated, and make ongoing development and support possible.
[Donate now](https://www.buymeacoffee.com/wellsworkshop)

## License

Copyright © 2026 Wells Riley. The [`maclock-pcb/`](./maclock-pcb/) PCB design is licensed under [CC BY-NC-SA 4.0](./maclock-pcb/LICENSE). The rest of the repository is published as-is for personal, non-commercial use.
