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
   - `After Dark:After Dark` and `After Dark:After Dark Files` onto
     `System Folder:Control Panels` (After Dark 2.0; see [after-dark.md](after-dark.md)).
   - The `Internet` folder onto Macintosh HD.
   - `Utilities:StuffIt Expander™` into Macintosh HD's `Utilities`. Open
     `Utilities:Disk Copy 6.3.3.smi` from the Transfer disk, copy the Disk Copy app from the disk
     it mounts into `Utilities`, and eject that disk.
   - The `Big Maclock` folder into Macintosh HD's `Applications`, and
     `After Dark:After Dark Files:BigMaclock` (its After Dark module) into
     `System Folder:Control Panels:After Dark Files` if it isn't there already.
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
   `MR Browser`, and `Applications:Big Maclock:BigMaclock`. Throw away the Mac OS Info Center alias
   the installer left. Line up SimpleText, iCab, MR Browser and BigMaclock in the right-hand column
   under the disks.

   Open BigMaclock, move the mouse to the top of the screen for its menu bar, and in
   Apple ▸ Preferences choose **12 Hour** and **MM.DD**; quit with Q. It keeps these in
   `BigMaclock Prefs` beside the app.
9. **Wells's preferences**:
   - Desktop Pictures ▸ Pattern: **Gray** (pattern 24 of 47) ▸ Set Desktop.
   - General Controls: untick **Warn me if computer was shut down improperly** (a Pi can lose
     power).
   - Speech ▸ Talking Alerts: both boxes off.
   - Appearance stays as installed: Chicago system font, Lavender accent, Black & White highlight.
10. **After Dark** control panel. The first time, it asks to personalise the copy: Name
    `Macintosh`, Organization blank. Then:
    - Select **Randomizer** in the list: Order Random, Duration 5 min (the last step before
      "1 module"), tick **Clear Screen** (otherwise a module can start on the last one's
      leftovers), Choose… ▸ All ▸ OK.
    - Select **BigMaclock**: untick 24 Hour, tick US Date (MM.DD), to match the app.
    - When: Sleep in 5 minutes (the default); tick **No sleep corners**.
    - Leave the speaker beside Demo at its lowest setting (no sound waves), which is sound off.
11. Clean up what using the apps left behind: the items inside
    `System Folder:Apple Menu Items:Recent Applications` and `Recent Documents`, and `iCab Cache` and
    `iCab Global History` in `System Folder:Preferences:iCab Preferences`. Throw away
    `System Folder:Preferences:Display Preferences` if it's there: Mac OS restores the colour
    depth it was saved at on every boot, overriding the depth Basilisk II is set to. Empty the
    Trash, close every window and shut down.

Don't choose a printer in the Chooser on this disk. Choosing one writes the printer's name into
the driver and puts a desktop printer on the desktop, which everyone who downloads the image would
get; Desktop Printing then won't let it be thrown away. Test printing on a copy (below).

## 4. Check

```bash
.venv/bin/python scrub_aliases.py out/macos-8.1.hda "SE/30" Wells
.venv/bin/python check_image.py out/macos-8.1.hda
```

The Mac OS installer copies the Sharing Setup names of the Mac that ran it (here an SE/30 disk
owned by Wells) into the aliases it makes. `scrub_aliases.py` blanks them in place; use the
names of whichever Mac ran your installer, and keep `alias_names_absent` in `expected.toml` in
step.

It checks the volume's name and size, the files and desktop items listed in `expected.toml`, that
no printer is chosen, that the Trash is empty, and that nothing listed as absent (such as
`Display Preferences`) is there.

Then boot a throwaway copy of the disk, since using the apps leaves caches, recent items and a
chosen printer behind. At 16-bit and 8-bit colour: no dialogs at startup; iCab opens the start
page, and 68k.news and FrogFind load; MR Browser connects and downloads a file, and StuffIt
Expander opens it; Disk Copy mounts an `.img`; the Chooser's AppleTalk ImageWriter lists your
printer and a page prints.
After Dark: [after-dark.md](after-dark.md) has each module's result and the hour-long soak.

## 5. Package and publish

Each version is named by year and month (with `.1`, `.2`… for another in the same month) and
gets a new file, so a checksum pinned in `setup.sh` never goes stale. `upload.py` refuses to
replace a file that's already on the archive.

```bash
./package.sh out/macos-8.1.hda 2026.10.1
cd out && ../.venv/bin/python ../upload.py macos-8.1-basilisk-ii-2026.10.1.zip
```

`package.sh` writes `out/macos-8.1-basilisk-ii-<version>.zip`, holding the image under that name,
and its `.sha256`. `upload.py` sends both to the Internet Archive item `macos-8.1-basilisk-ii` with
the title and description in `ia-metadata.toml` (and refreshes them on an existing item); it
needs the `ia` tool
(`brew install internetarchive`), signed in once with `ia configure`. Then download the zip from
`https://archive.org/download/macos-8.1-basilisk-ii/` and check its SHA-256 matches.
