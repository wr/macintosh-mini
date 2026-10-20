# Mac OS 8.1 Disk Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A downloadable, clean Mac OS 8.1 disk image for Basilisk II (not tied to the Mini, the Pi or AirWriter), plus the installer changes that build Basilisk II with the AppleTalk-only tunnel, turn AppleTalk on, and offer the image when the Pi has none.

**Architecture:** Two pieces that ship as two PRs. (1) `setup.sh` builds Basilisk II from a pinned commit of `wr/macemu` (upstream plus kanjitalk755/macemu#321 and #322) and writes the tunnel prefs. (2) A `disk-image/` folder: Python tools on the Mac fetch pinned sources and pack them onto a "Transfer" HFS disk; the image itself is installed and configured inside Basilisk II on the test Pi, driven over VNC, then checked by a script, zipped, uploaded to the Internet Archive with `ia`, and offered by `setup.sh`.

**Tech Stack:** bash (`setup.sh`, whiptail), Python 3 with `machfs` 1.3 (venv in `disk-image/.venv`), `unittest`, The Unarchiver's `unar`/`lsar`, Basilisk II, wayvnc + vncdotool for the Pi bench, the Internet Archive `ia` CLI (signed in as Wells).

**Spec:** `docs/superpowers/specs/2026-10-20-system-8-1-disk-image-design.md`

## Global Constraints

- Volume: HFS (Mac OS Standard), exactly 1 GiB (1073741824 bytes), named `Macintosh HD`. The Mac is named `Macintosh`.
- The image is Mini-, Pi- and AirWriter-agnostic: none of them is named or needed anywhere on it (Wells, 2026-10-20).
- Target emulator: Basilisk II, `modelid 14`, `screen win/640/480`, `ramsize` 64 or 128 MB, `ether slirp`. Must pass at `displaycolordepth` 16 and 8; 1 is best effort.
- macemu pin: `MACEMU_REPO="https://github.com/wr/macemu.git"`, `MACEMU_COMMIT="722458b7c9bd7148a050e40638023ebe84a67863"`.
- Tunnel prefs, exactly: `udptunnel true`, `udpport 6066`, `udpappletalkonly true`.
- Internet Archive item `macos-8.1-basilisk-ii`, title "Mac OS 8.1 for Basilisk II (clean install)"; file `macos-8.1-basilisk-ii-<version>.zip` holding `macos-8.1-basilisk-ii-<version>.hda`; first version `2026.10`. Never GitHub releases.
- Known sources: Mac OS 8.1 CD, US English, `https://archive.org/download/apple-mac-os-8.1-iso/Apple%20Mac%20OS%208.1%20(ISO)/MacOS8_1.iso`, SHA-256 `10f218f5ad4105d27b7ad3f82a7a12a8c1e2203e42cdd358936c8a27f6892c51`; ImageWriter LocalTalk Option `https://old.mac.gdn/apps/iw_0.sit`, SHA-256 `6ba91270bc4303cb8826ce268165665918815f9bbd2ceb1e35736c1d0bc9e8ec`.
- No image, ISO or third-party file in git. Caches and outputs live in `disk-image/.cache/` and `disk-image/out/` (gitignored).
- Python files carry the repo's SPDX header (`GPL-3.0-or-later`, like `maclock-build/button_handler.py`); tests run with `cd disk-image && .venv/bin/python -m unittest -v`.
- Copy users see (start page, `setup.sh` prompts, CHANGELOG entries, the Internet Archive title and description) goes to Wells before it's committed or uploaded.
- `setup.sh` never replaces, rewrites or silently reconfigures an existing disk image or prefs file. README stays a landing page; details go in `BUILD.md` or `disk-image/README.md`.
- Commit and push freely; merge only when Wells says "ship it".

**Pi bench** (from the 2026-10-20 session; scripts in `/private/tmp/claude-501/-Users-wells-Projects-macintosh-mini/00283bfe-d70f-4774-b08a-5fcdd78e5106/scratchpad/`): test Pi `wells@10.0.1.111`; `pi-vnc.sh` (re)starts wayvnc, `vnc.sh <png> <vncdo actions>` acts and screenshots, `pi-restart.sh <prefs-extra|-> <stock|patched>` shuts the Mac down and relaunches, `atping.py <net.node>` pings over AppleTalk via AirWriter's test peer. Stock binary backup: `/usr/local/bin/BasiliskII.stock`; original prefs: `~/.basilisk_ii_prefs.orig`. Mac OS 8 needs ~0.8 s between moving and clicking, press-drag-release for menus, and one key at a time when typing. AirWriter board 1 is at 10.0.1.115 (`/api/et`, `/api/status`); a print uses paper, so print one page per check.

## Review Focus

- A download that fails partway, a full SD card or a checksum mismatch must leave no `.hda` in `$HOME` (which `find_disks` would boot next time) and end with the existing "copy a disk over" message. (Task 9: `bad checksum`, `truncated download`, `no space` scenarios.)
- An update rebuilds Basilisk II once; a failed build must not write the stamp, so the next run retries; a second run after success must not rebuild. (Task 1 scenarios.)
- SheepShaver installs share `~/macemu`: pinning it to the fork must still build SheepShaver. (Task 1: SheepShaver compile check.)
- Someone with their own disk (one or several) must never see the download offer, and their disk picker must behave as before. (Task 9 scenarios.)
- While After Dark is running, AppleTalk and the web keep working: AirWriter can still reach the Mac. (Task 7: `atping.py` 5/5 during a module.)

---

## PR 1: the emulator

### Task 1: Build Basilisk II from the pinned fork

**Files:**
- Modify: `setup.sh` (constants beside `MACEMU_DIR` ~line 57; `needs_build` ~line 908; SheepShaver clone ~line 1405; Basilisk II clone/build/install ~lines 1592-1620)

**Interfaces:**
- Produces: `MACEMU_REPO`, `MACEMU_COMMIT`; `checkout_macemu()` (clone if missing, set `origin` to `MACEMU_REPO`, fetch `MACEMU_COMMIT`, `checkout --detach -f`); `needs_build <binary> [<stamp-file>]` returns 0 when the binary is missing, GTK-linked, or the stamp file's content isn't `MACEMU_COMMIT`. Basilisk II's stamp: `/usr/local/share/macintosh-mini/basilisk.commit`, written only after the binary is installed.

- [ ] **Step 1:** Replace both `git clone https://github.com/kanjitalk755/macemu.git` steps with `run "[basilisk] Fetching macemu (pinned: AppleTalk tunnel fixes)" checkout_macemu` (and the `[sheepshaver]` equivalent). SheepShaver keeps calling `needs_build` without a stamp.
- [ ] **Step 2:** Pass the stamp to every `needs_build /usr/local/bin/BasiliskII` call (step count and build block), and write the stamp right after `Installing BasiliskII binary`.
- [ ] **Step 3:** Check: `bash -n setup.sh` passes, and `shellcheck -S warning setup.sh` reports no more findings than the 2 it reports on `main`.
- [ ] **Step 4: Test on the Pi** with `--branch wells/system-8-1-disk-image`, run detached with `TERM` set (see the Pi testing memory). Expect: (a) first update clones/fetches the pin and rebuilds; `strings /usr/local/bin/BasiliskII | grep -c udpappletalkonly` ≥ 1; stamp holds the commit. (b) Second run: no "Building Basilisk II" step. (c) Break the build (`chmod -x ~/macemu/BasiliskII/src/Unix/autogen.sh`, delete the stamp), run: fails, stamp absent; restore, run: rebuilds.
- [ ] **Step 5: SheepShaver check:** the patched `ether_unix.cpp` already compiles for SheepShaver (checked on the Pi, 2026-10-20); now the whole build. In `~/macemu` at the pin, `cd SheepShaver/src/Unix && ./autogen.sh --enable-sdl-video --enable-sdl-audio --disable-jit-compiler --with-gtk=no && make -j2` succeeds (it can take an hour; run detached). Don't install the result.
- [ ] **Step 6: Commit** `git commit -m "Installer: build Basilisk II with the AppleTalk tunnel fixes"`

### Task 2: Turn on printing to AirWriter

**Files:**
- Modify: `setup.sh` (`write_basilisk_prefs` ~line 1697; `configure_existing` ~line 709; new `reconf_appletalk`; `VERSION` line 51), `CHANGELOG.md`

**Interfaces:**
- Consumes: `pref_get`, `pref_set` (~line 653).
- Produces: `reconf_appletalk <prefs>`: a yes/no that sets the three tunnel prefs (on) or `udptunnel false` and `udpappletalkonly false` (off).

- [ ] **Step 1:** Add the three tunnel lines to the new-install prefs heredoc, after `ether slirp`.
- [ ] **Step 2:** Add a Basilisk II-only row `"AppleTalk:"` to the Emulator Settings menu showing `On` when `udptunnel` and `udpappletalkonly` are both `true`, else `Off`; selecting it runs `reconf_appletalk`, a menu with `On` "AppleTalk printers and file sharing on your network, plus the internet" and `Off` "The internet only" (Wells's approved copy). Grow the menu by one row.
- [ ] **Step 3:** Draft the CHANGELOG `[1.8.0]` entry (AppleTalk printers and file sharing alongside the internet; new installs get it, existing ones in Edit settings; Basilisk II rebuilds once). Show Wells; apply his edits. Bump `VERSION="1.8.0"`.
- [ ] **Step 4: Test on the Pi.** New install path: move `~/.basilisk_ii_prefs` aside, run, expect the three lines in the new prefs; put the old file back. Update path: drive the menu with `expect` over `ssh -t`: toggle Off then On, check the prefs after each. Then with it On, the Chooser on the Mac shows "ImageWriter II" under AppleTalk ImageWriter (the test disk has the driver) and `atping.py` gets 5/5.
- [ ] **Step 5: Commit, push, open PR 1** (`gh pr create`, body: what changes for users, the Pi results; the upstream PRs it depends on). Bind it with the ccd_pr tools.

---

## PR 2: the disk image

### Task 3: Pinned sources and the fetch tool

**Files:**
- Create: `disk-image/requirements.txt` (`machfs==1.3`), `disk-image/sources.toml`, `disk-image/mmdisk/__init__.py`, `disk-image/mmdisk/sources.py`, `disk-image/fetch.py`, `disk-image/tests/test_sources.py`
- Modify: `.gitignore` (`disk-image/.venv/`, `disk-image/.cache/`, `disk-image/out/`), `REUSE.toml` (`disk-image/**/*.py`, `disk-image/*.toml`, `disk-image/requirements.txt` → GPL-3.0-or-later; everything else in `disk-image/` stays CC BY-SA)

**Interfaces:**
- Produces: `@dataclass Source(id: str, file: str, sha256: str, url: str | None, note: str)`; `load_sources(path: Path) -> list[Source]`; `fetch(src: Source, cache: Path) -> Path` (downloads to `cache/<file>.part`, verifies, renames; an existing file is only verified); `class ChecksumError(Exception)`, `class MissingSourceError(Exception)` (message names the expected path and the note). `fetch.py [--cache DIR]` fetches everything and exits 1 listing failures. `sources.toml` is a list of `[[source]]` tables with those fields.

- [ ] **Step 1: Write the failing tests:** `test_load_sources_reads_entries`; `test_fetch_downloads_and_verifies` (a `file://` URL to a temp file); `test_fetch_rejects_bad_checksum` (raises `ChecksumError`, no file or `.part` left); `test_fetch_missing_manual_source` (no URL, no file → `MissingSourceError` naming `cache/<file>`); `test_real_sources_toml_is_valid` (loads, ids unique, every sha256 is 64 hex chars).
- [ ] **Step 2: Run, expect failures:** `python3 -m venv disk-image/.venv && disk-image/.venv/bin/pip install -r disk-image/requirements.txt`, then the test command.
- [ ] **Step 3: Implement** the interfaces with `tomllib`, `urllib.request` and `hashlib`. Seed `sources.toml` with the two known sources (ids `macos81-cd`, `imagewriter-option`).
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `git commit -m "Disk image: pinned sources and fetch tool"`

### Task 4: Find and pin the rest

**Files:**
- Modify: `disk-image/sources.toml`

- [ ] **Step 1:** Find a source for each of: After Dark 4.0.3, iCab 2.9.9 (68k build), MR Browser (latest 68K build), StuffIt Expander 5.5, Disk Copy 6.3.3, Internet Explorer 4.01 (68k, the fallback). Prefer archive.org, then Macintosh Garden or Macintosh Repository. Check the test Pi's After Dark (Get Info over VNC) in case it's already 4.0.3. Where there's no stable direct URL, leave `url` empty and say in `note` where Wells or the builder got it.
- [ ] **Step 2:** Add each with its SHA-256, and run `disk-image/.venv/bin/python disk-image/fetch.py`. Expect exit 0 and every file in `disk-image/.cache/`.
- [ ] **Step 3:** For each archive, `lsar -l` it and note in `sources.toml` which member is the app (and whether it needs a serial number; if so, swap it for an equivalent, as the spec says).
- [ ] **Step 4: Commit** `git commit -m "Disk image: pin the software sources"`

### Task 5: The Transfer disk

**Files:**
- Create: `disk-image/mmdisk/macfile.py`, `disk-image/mmdisk/transfer.py`, `disk-image/transfer.toml`, `disk-image/make_transfer.py`, `disk-image/files/Start Page.html`, `disk-image/files/FrogFind.html`, `disk-image/tests/test_transfer.py`

**Interfaces:**
- Consumes: `load_sources`, `fetch` (Task 3).
- Produces: `@dataclass MacFile(name: str, data: bytes, rsrc: bytes, type: bytes, creator: bytes, flags: int = 0)`; `read_host_file(path: Path) -> MacFile` (data fork, `path/..namedfork/rsrc`, type/creator/flags from `xattr -px com.apple.FinderInfo`); `extract_archive(archive: Path, dest: Path) -> Path` (`unar -q -forks fork -o dest`); `files_from_floppy(image: bytes) -> dict[str, MacFile]` (via `machfs.Volume().read`); `build_transfer(files: dict[str, MacFile], size: int = 256 * 2**20, name: str = "Transfer") -> bytes`, each key the file's colon-separated path on the volume (folders created as needed). `make_transfer.py` reads `transfer.toml` (each entry: source id or local file, member path inside the archive, destination folder, and for local files the type and creator) and writes `disk-image/out/transfer.dsk`.

The FrogFind shortcut is a small HTML page that redirects (`<meta http-equiv="refresh">`) to `http://frogfind.com/`, typed `TEXT` with the chosen browser's creator code (iCab `iCAB`; IE `MSIE`) so a double-click opens the browser. The start page is plain, unbranded HTML 3.2 with links to FrogFind, 68k.news and `http://www.macintoshrepository.org/`.

- [ ] **Step 1: Write the failing tests:** `test_build_transfer_roundtrip` (two files in nested folders; read back with machfs: names, forks, type, creator equal); `test_files_from_floppy` (a machfs-built 800K fixture with one file); `test_read_host_file` (macOS only, `skipUnless(sys.platform == "darwin")`: write a file, set a resource fork through `..namedfork/rsrc` and FinderInfo with `xattr -wx`, read it back).
- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement** the interfaces and `transfer.toml` for every source in Task 4 plus the two local files.
- [ ] **Step 4: Run, expect PASS.** Then `make_transfer.py` produces `out/transfer.dsk`, and a machfs listing shows every app with a non-empty resource fork.
- [ ] **Step 5: Copy review:** show Wells the start page and the shortcut's title; apply his edits.
- [ ] **Step 6: Commit** `git commit -m "Disk image: Transfer disk with the apps and pages"`

### Task 6: Install and configure the image (on the test Pi)

**Files:**
- Create: `disk-image/README.md` (how to rebuild: the scripts, then the written steps below), `disk-image/expected.toml`, `disk-image/check_image.py`, `disk-image/tests/test_check_image.py`

**Interfaces:**
- Produces: `check_image(image: bytes, expected: dict) -> list[str]` (empty list means it passes); `check_image.py <image>` prints problems and exits 1 if any. `expected.toml` lists: volume name, size, required paths (`System Folder:System`, `System Folder:Finder`, `System Folder:Extensions:AppleTalk ImageWriter`, each app), desktop items (in `Desktop Folder`) and which must be aliases (Finder flag `0x8000`).

- [ ] **Step 1: Write the failing tests** for `check_image` with machfs-built fixtures: `test_passes_complete_volume`, `test_reports_missing_path`, `test_reports_wrong_size`, `test_reports_non_alias_desktop_item`.
- [ ] **Step 2: Run, expect failures; implement; run, expect PASS.**
- [ ] **Step 3: Base install.** On the Pi, `truncate -s 1G ~/macos-8.1.hda`; copy over `out/transfer.dsk` and the CD ISO. Shut the Mac down and boot with prefs (absolute paths, as the Pi's prefs use): `disk /home/wells/HD10_512.hda` (the existing 8.1 test disk, to run the installer), `disk /home/wells/macos-8.1.hda`, `disk /home/wells/transfer.dsk`, `cdrom /home/wells/MacOS8_1.iso`. Initialize the new disk as Mac OS Standard, named `Macintosh HD`. Run the CD's Mac OS Install onto it, customised to leave out Internet Access's browsers, Personal Web Sharing, speech and Java. Write each step into `disk-image/README.md` as you go.
- [ ] **Step 4: Configure.** Boot from `Macintosh HD` (first `disk` line), with the Transfer disk attached. Copy everything off the Transfer disk; install the AppleTalk ImageWriter in Extensions and After Dark (all modules for now); TCP/IP to Ethernet + DHCP; AppleTalk on, Ethernet; no printer chosen; Mac named `Macintosh`, File Sharing off; virtual memory off; no Setup Assistant or registration in Startup Items; a "Basilisk II" Extensions Manager set without the do-nothing extensions; browser home page = the start page; desktop aliases for the browser, SimpleText and MR Browser; the FrogFind shortcut on the desktop. Add each step to the README.
- [ ] **Step 5: Check.** Copy the image to the Mac; `check_image.py` passes. On the Pi, boot it alone at 16-bit and 8-bit: no dialogs at startup; the browser opens without a nag screen (if iCab nags, switch to Internet Explorer 4.01 and redo its part of Tasks 5 and 6); the start page and 68k.news load; FrogFind loads if it's up; MR Browser connects and downloads a file, and StuffIt Expander opens it; Disk Copy mounts the ImageWriter `.img`; the Chooser lists "ImageWriter II" and one page prints.
- [ ] **Step 6: Commit** `git commit -m "Disk image: install steps and image check"`

### Task 7: After Dark modules

**Files:**
- Create: `disk-image/after-dark.md` (each module: pass/fail at 16-bit and 8-bit, and why)
- Modify: `disk-image/README.md`, `disk-image/expected.toml` (the kept modules)

- [ ] **Step 1:** On the Pi at 16-bit, run every module for 2 minutes from the control panel; record whether it draws, stays responsive and wakes on mouse movement. Repeat at 8-bit.
- [ ] **Step 2:** Remove the modules that fail either depth from `After Dark Files`. Set Randomizer as the active module with every kept module, and a 5-minute delay.
- [ ] **Step 3: Soak:** an hour idle at each depth; the Mac is still responsive afterwards, and `atping.py` gets 5/5 while a module runs.
- [ ] **Step 4:** Re-run `check_image.py`. Commit `git commit -m "Disk image: After Dark modules that work on the Pi"`

### Task 8: Package and upload

**Files:**
- Create: `disk-image/package.sh` (zip with `zip -9`, write `.sha256`), `disk-image/ia-metadata.toml` (title, description, subject, mediatype `software`)

- [ ] **Step 1:** `package.sh out/macos-8.1.hda 2026.10` writes `out/macos-8.1-basilisk-ii-2026.10.zip` (holding `macos-8.1-basilisk-ii-2026.10.hda`) and its SHA-256. Unzip it into a temp folder and run `check_image.py` on the result: passes.
- [ ] **Step 2: Copy review:** show Wells the title and description (a clean Mac OS 8.1 install for Basilisk II as a Quadra; contents; known-working settings; credit to the sources; "Mac OS 8.1 and the included software are © their owners"); apply his edits.
- [ ] **Step 3:** `ia upload macos-8.1-basilisk-ii out/macos-8.1-basilisk-ii-2026.10.zip` with the metadata. Wait for `ia tasks macos-8.1-basilisk-ii` to show no pending tasks.
- [ ] **Step 4:** `curl -fL -o /tmp/check.zip https://archive.org/download/macos-8.1-basilisk-ii/macos-8.1-basilisk-ii-2026.10.zip` and compare SHA-256: equal. Record the URL, SHA-256 and size in MB for Task 9.
- [ ] **Step 5: Commit** `git commit -m "Disk image: packaging and Internet Archive metadata"`

### Task 9: Offer the image in `setup.sh`

**Files:**
- Modify: `setup.sh` (constants near `MACEMU_DIR`; `check_basilisk_assets` ~line 275; the disk discovery block ~line 560; argument parsing for a `--get-disk` flag; usage comment at the top), `README.md` (Step 2: one "or download ours" line), `BUILD.md` (what's on the disk, how setup offers it, the direct link), `CHANGELOG.md`, `VERSION`

**Interfaces:**
- Produces: `DISK_DL_VERSION`, `DISK_DL_URL`, `DISK_DL_SHA256`, `DISK_DL_MB` (from Task 8); `get_disk_image()`: checks free space in `$HOME` (zip size + 1 GiB + 100 MB), downloads to `$HOME/.macos-8.1-basilisk-ii.zip.part`, verifies with `sha256sum -c`, unzips with `python3 -m zipfile -e` into a temp folder, moves the `.hda` into `$HOME`, cleans up on every exit path, sets `DISK_IMAGE`; returns non-zero with a one-line reason on failure.

- [ ] **Step 1:** In `check_basilisk_assets`, a missing disk no longer dies when installing Basilisk II; SheepShaver still dies as today.
- [ ] **Step 2:** In the disk discovery block, when no disk is found for a new Basilisk II install: a yes/no offering the download (version, size in MB); `--get-disk` skips the question. Yes → `get_disk_image`; on failure or No → the existing `die` message. Existing installs and anyone with a disk never see it.
- [ ] **Step 3:** Draft the yes/no copy, the README line, the BUILD.md section and the CHANGELOG entry; show Wells; apply edits. Bump `VERSION` one minor version past whatever `main` has.
- [ ] **Step 4:** `bash -n` and `shellcheck` as in Task 1.
- [ ] **Step 5: Test on the Pi** with `--branch`, prefs and disks moved aside and restored after each: (a) no disk, answer Yes → downloads, verifies, boots the new image; (b) `--get-disk` → same with no question; (c) `DISK_DL_SHA256` overridden to a wrong value → clear message, no `.hda` or `.part` left, ends with the "copy a disk over" message; (d) a truncated download (point `DISK_DL_URL` at a local server that closes early) → same; (e) a tmpfs `HOME` too small → the space message before any download; (f) one existing disk → no offer, same as today; (g) two disks → the existing picker, no offer.
- [ ] **Step 6: Commit, push, open PR 2.** Bind it with the ccd_pr tools.

### Task 10: The whole thing, on the test Pi

- [ ] **Step 1:** With PR 1 and PR 2 merged into a test branch, run the spec's Testing list end to end on the test Pi: fresh install with no disk, both colour depths, browser, MR Browser + StuffIt, Disk Copy, Chooser + one printed page while browsing, After Dark after 5 minutes and an hour's soak, and a re-run of `setup.sh` keeping disk and prefs.
- [ ] **Step 2:** Put the test Pi back to its normal disk and prefs, or leave it on the new image if Wells prefers. Report results in both PRs.
