<img height="300" alt="Slide 16_9 - 1" src="https://github.com/user-attachments/assets/1952ccdc-c1eb-40cc-904e-79eab73d15dd" />

## What?

Turn a [Maclock](https://www.aliexpress.us/w/wholesale-maclock.html) (a simple alarm clock inside a shockingly accurate miniature Macintosh shell) into a working Mac using a Raspberry Pi Zero. Buttons, brightness, sound, and battery all work.

## Hardware you'll need
- [Maclock](https://www.aliexpress.us/w/wholesale-maclock.html)
- [Raspberry Pi Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
- [Waveshare 2.8 inch IPS LCD](https://www.waveshare.com/2.8inch-dpi-lcd.htm)
- [3D printed screen bezel](./maclock-screen-bezel)
- [Macintosh Mini breakout board](./maclock-pcb) (if you want brightness, buttons, and sound). Open source design—here's a link to a [cart on PCBway](https://www.pcbway.com/orderonline.aspx?outsideid=802d4efa-7309-4b4f-bf3a-cc70d992479b) to order your own.

<img height="100" alt="Macintosh Mini PCB" src="https://github.com/user-attachments/assets/737a05eb-cc00-4b0e-b82b-f892061ca27d" />


## The build
1. Follow the [Maclock hardware guide](https://github.com/wr/macintosh-mini/tree/main/maclock-build) for instructions for assembling the Macintosh Mini.

I recorded a walkthrough for how I assembled mine that goes into much more detail than the written guide:
[<img height="300" alt="Frame 2" src="https://github.com/user-attachments/assets/345a346a-67c7-46be-971e-8b5e387e1155" />
](https://www.youtube.com/watch?v=zAbAf5-H5Yo)

## The software—quick install (recommended)

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

## The software—manual install

You can also do everything the script does by yourself: [Maclock hardware guide](https://github.com/wr/macintosh-mini/tree/main/maclock-build) and [Sheepshaver install guide](https://github.com/wr/macintosh-mini/tree/main/sheepshaver).


**Getting help**

Feel free to open a GitHub issue!

 
**Credits**

Startup chimes and crash sounds are mirrored from D. Schaub's Apple Sounds collection at <https://froods.ca/~dschaub/sound.html>. All sounds are © Apple, Inc.

---

Copyright © 2026 Wells Riley. The [`maclock-pcb/`](./maclock-pcb/) PCB design is licensed under [CC BY-NC-SA 4.0](./maclock-pcb/LICENSE). The rest of the repository is published as-is for personal, non-commercial use.
