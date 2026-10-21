# Mac OS 8.1 disk image for Basilisk II

How the clean Mac OS 8.1 image is built: a known-working install for Basilisk II as a Quadra
(`modelid 14`), with the AppleTalk ImageWriter driver, After Dark, a browser and a few utilities.
Nothing on it is specific to the Macintosh Mini, the Pi or AirWriter. The design is in
[`docs/superpowers/specs/2026-10-20-system-8-1-disk-image-design.md`](../docs/superpowers/specs/2026-10-20-system-8-1-disk-image-design.md).

The image itself is never committed: it's built from pinned downloads and published on the
Internet Archive.

## 1. Tools (on a Mac)

```bash
brew install unar
python3 -m venv disk-image/.venv
disk-image/.venv/bin/pip install -r disk-image/requirements.txt
```

Tests: `cd disk-image && .venv/bin/python -m unittest -v`

## 2. Sources and the Transfer disk

`sources.toml` pins every download by URL and SHA-256. `fetch.py` downloads them into `.cache/`
and checks them; `make_transfer.py` unpacks them and packs what `transfer.toml` lists onto
`out/transfer.dsk`, an HFS disk the emulated Mac installs from.

```bash
cd disk-image
.venv/bin/python fetch.py
.venv/bin/python make_transfer.py
```

## 3. Install and configure (in Basilisk II)

The first build ran on a Raspberry Pi Zero 2 W with Basilisk II as a Quadra (`modelid 14`, 128 MB,
640×480); any Basilisk II host works the same way.

**Base install**

1. Make a blank 1 GiB disk: `truncate -s 1G macos-8.1.hda`. Copy `.cache/MacOS8_1.iso` and
   `out/transfer.dsk` beside it.
2. Boot an existing Mac OS 8.x disk (it only runs the installer), with the blank disk, the
   Transfer disk and the CD attached:

   ```
   disk /path/to/an-existing-8.x.hda
   disk /path/to/macos-8.1.hda
   disk /path/to/transfer.dsk
   cdrom /path/to/MacOS8_1.iso
   modelid 14
   ramsize 134217728
   ```

3. The Mac asks to initialise the unreadable disk: name it `Macintosh HD`, format
   **Mac OS Standard 1 GB**.
4. Open **Install Mac OS 8.1** on the CD. Destination:
   **Macintosh HD** (not the disk you booted from). Agree to the licence. Click **Customise** and
   leave on only **Mac OS 8.1**, **Mac OS Info Centre**, **OpenDoc** and **MacLink Plus**: untick
   Internet Access, Open Transport PPP, Mac OS Runtime for Java, Personal Web Sharing and
   QuickDraw 3D. Start, then **Easy Install** onto Macintosh HD.
5. Quit the installer, shut down, and keep a copy of the disk: that's the clean base.

**Configure**

Boot from the new disk alone, with the Transfer disk attached:

```
disk /path/to/macos-8.1.hda
disk /path/to/transfer.dsk
modelid 14
ramsize 134217728
```

1. On the first start the Mac OS Setup Assistant opens and can hang Basilisk II (the menu-bar
   clock stops). If it does, stop the emulator and start again holding Shift. Don't use the
   assistant: every setting below is made in its control panel. Check that
   `System Folder:Startup Items` ends up empty.
2. From the Transfer disk (easiest in list view):
   - `Printing:AppleTalk ImageWriter` onto `System Folder:Extensions`.
   - `After Dark:After Dark 4.0` and `After Dark:After Dark Files` onto
     `System Folder:Control Panels`.
   - The `Internet` folder onto Macintosh HD.
   - `Utilities:StuffIt Expander™` into Macintosh HD's `Utilities`. Open
     `Utilities:Disk Copy 6.3.3.smi` from the Transfer disk, copy the Disk Copy app from the disk
     it mounts into `Utilities`, and eject that disk.
   - `Fallback` holds Internet Explorer 4.01, used only if iCab stops working.

   Restart.
3. **TCP/IP**: answer Yes to make it active. The defaults are right (Ethernet, DHCP Server).
   Close it and save.
4. **AppleTalk**: Ethernet (the default).
5. **File Sharing**: Computer Name `Macintosh`; Owner Name and password blank; File Sharing and
   Program Linking stay off.
6. **Memory**: nothing to do; Basilisk II offers no virtual memory.
7. **iCab** (`Internet:iCab:iCab`), Edit ▸ Preferences:
   - Default Pages: Home page ▸ Local… ▸ `Internet:Start Page`; search page
     `http://frogfind.com/`.
   - Windows: open the home page at launch and in new windows.

   Untick File ▸ Offline Mode, then quit iCab.
8. **Desktop**: Command-Option-drag iCab, `Applications:SimpleText` and
   `Internet:MR Browser 68K v0.39` to the desktop to make aliases; rename the last one
   `MR Browser`. Throw away the Mac OS Info Center alias the installer left. Line up SimpleText,
   iCab and MR Browser in the right-hand column under the disks.
9. **Wells's preferences**:
   - Desktop Pictures ▸ Pattern: **Gray** (pattern 24 of 47) ▸ Set Desktop.
   - General Controls: untick **Warn me if computer was shut down improperly** (a Pi can lose
     power).
   - Speech ▸ Talking Alerts: both boxes off.
   - Appearance stays as installed: Chicago system font, Lavender accent, Black & White highlight.
10. Restart. **After Dark 4.0** control panel: Setup already says sleep after 5 minutes and wake
    on mouse movement. In Randomizers, delete All AD Online Channels and All Deluxe Displays (their
    packs aren't installed) and select **All 4.0 Displays** (random order, 5 minutes each).
11. Clean up what using the apps left behind: the items inside
    `System Folder:Apple Menu Items:Recent Applications` and `Recent Documents`, and `iCab Cache` and
    `iCab Global History` in `System Folder:Preferences:iCab Preferences`. Empty the Trash, close
    every window and shut down.

Don't choose a printer in the Chooser on this disk. Choosing one writes the printer's name into
the driver and puts a desktop printer on the desktop, which everyone who downloads the image would
get; Desktop Printing then won't let it be thrown away. Test printing on a copy (below).

## 4. Check

```bash
.venv/bin/python check_image.py out/macos-8.1.hda
```

It checks the volume's name and size, the files and desktop items listed in `expected.toml`, that
no printer is chosen, and that the Trash is empty.

Then boot a throwaway copy of the disk, since using the apps leaves caches, recent items and a
chosen printer behind. At 16-bit and 8-bit colour: no dialogs at startup; iCab opens the start
page, and 68k.news and FrogFind load; MR Browser connects and downloads a file, and StuffIt
Expander opens it; Disk Copy mounts an `.img`; the Chooser's AppleTalk ImageWriter lists your
printer and a page prints.
