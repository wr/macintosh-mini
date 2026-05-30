<img height="300" alt="Slide 16_9 - 1" src="https://github.com/user-attachments/assets/1952ccdc-c1eb-40cc-904e-79eab73d15dd" />

## What?

Turn a [Maclock](https://www.aliexpress.us/w/wholesale-maclock.html) (a simple alarm clock inside a shockingly accurate miniature Macintosh shell) into a working Mac using a Raspberry Pi Zero. Buttons, brightness, sound, and battery all work.

## Hardware you'll need
- [Maclock](https://www.aliexpress.us/w/wholesale-maclock.html)
- [Raspberry Pi Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
- [Waveshare 2.8 inch IPS LCD](https://www.waveshare.com/2.8inch-dpi-lcd.htm)
- [3D printed screen bezel](./maclock-screen-bezel)
- [Macintosh Mini breakout board](./maclock-pcb) (if you want brightness, buttons, and sound). Open source design—here's a link to a [cart on PCBway](https://www.pcbway.com/project/shareproject/W654223ASS41_Untitled_kicad_pcb_95cca7e3.html) to order your own.

<img height="140" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/2230bd4a-3ca1-49cb-a75f-22cee96a8ea3" />


## The build
1. Follow the [Maclock hardware guide](https://github.com/wr/macintosh-mini/tree/main/maclock-build) for instructions for assembling the Macintosh Mini.

I recorded a walkthrough [video](https://www.youtube.com/watch?v=zAbAf5-H5Yo) for how I assembled mine that goes into much more detail than the written guide:

## The software—quick install (recommended)

1. Install [Raspberry Pi OS (lite) 64-bit](https://www.raspberrypi.com/software/) onto an SD card.

2. Copy over a Mac OS disk image and a ROM file — the installer auto-discovers them in `$HOME`. It offers two emulators (it defaults to **Basilisk II**):

   - **Basilisk II** — a 68k Mac running System 7.0-8.5. On the Pi Zero 2 W this is the fastest option. Needs a **512 KB or 1 MB 68k ROM** (Mac IIci / Quadra, try searching online for `064DC91D`) and a disk image.
   - **SheepShaver** — if you *need* PowerPC running Mac OS 8.1+. Needs the **4 MB PowerPC [ROM](https://www.redundantrobot.com/sheepshaver)** and a disk image. Choose this only if you need PPC-era software as it's **very slow on a Pi Zero**.

   Rename your ROM file `ROM` (no file extension)

   Disk images are readily available online, but I recommend the [BlueSCSI image library](https://bluescsi.com/docs/BlueSCSI-Images).

   **Disk images that work:** any raw hard-disk image — `.hda`, `.img`, `.dsk`, `.hfv`, `.vhd` (the extension doesn't matter) — and Apple `.sparsebundle`.
   **Don't work:** `.dmg`, `.image`/`.smi`, `.toast`, or files still zipped (`.zip` / `.sit`).

   ```bash
   scp ROM yourdisk.hda <user>@<pi_ip>:~/
   ```
3. SSH into the Pi and run:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/wr/macintosh-mini/main/setup.sh | bash
   ```
   
4. The script will reboot your Pi when done, and it should Just Work™️

## Using it

Once installed the Pi boots straight into the Mac. A few controls:

- **Reset button** (GPIO 26): a single press restarts the emulator; a **double press quits to a Pi shell prompt**.
- **Shut Down** from inside Mac OS (Special → Shut Down) quits to the Pi prompt; **Restart** reboots the Mac in place; a crash auto-reboots.
- **`macintosh`** — run this from the prompt to boot the Mac again.
- **Networking** works out of the box (slirp NAT). In the Mac, set TCP/IP to **DHCP**.

Re-run the installer any time to **update** an existing install — it keeps your disk image and settings. To **switch emulator**, pick the other one (Basilisk II ⇄ SheepShaver); each core's prefs are preserved.

## The software: manual install

You can also do everything the script does by yourself: 
- [Maclock hardware guide](https://github.com/wr/macintosh-mini/tree/main/maclock-build)
- [Basilisk II install guide](https://github.com/wr/macintosh-mini/blob/main/emulators/BasiliskII.md)
- [SheepShaver install guide](https://github.com/wr/macintosh-mini/blob/main/emulators/SheepShaver.md).


**Getting help**

Feel free to open a GitHub issue!

 
**Credits**

Startup chimes and crash sounds are mirrored from D. Schaub's Apple Sounds collection at <https://froods.ca/~dschaub/sound.html>. All sounds are © Apple, Inc.

---

Copyright © 2026 Wells Riley. The [`maclock-pcb/`](./maclock-pcb/) PCB design is licensed under [CC BY-NC-SA 4.0](./maclock-pcb/LICENSE). The rest of the repository is published as-is for personal, non-commercial use.
