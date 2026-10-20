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

## 4. Check

```bash
.venv/bin/python check_image.py out/macos-8.1.hda
```

It checks the volume's name and size and the files listed in `expected.toml`.
