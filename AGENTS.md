# Macintosh Mini

A Maclock alarm clock rebuilt around a Raspberry Pi Zero 2 W running Basilisk II or SheepShaver, so
the tiny Mac boots System 7 or Mac OS 8. This repo holds the installer (`setup.sh` and
`maclock-build/`), the breakout board, the printed parts and the recipe for our Mac OS 8.1 disk.

**This file is current state only. Edit it in place; never append dated entries.** History is
`git log` and Linear. When a fact here stops being true, change or delete it in the same commit.

## Source of truth
- GitHub: github.com/wr/macintosh-mini (public), remote `origin`. Everything committed is public:
  no machine addresses or logins, orders or carts, supplier accounts, customer details or launch
  plans. Those, and new plans, specs, reviews and build logs, go in Wells's private notes repo
  (`~/Projects/notes/macintosh-mini/` on his Macs). `docs/superpowers/` holds a few older designs; leave them.
- Linear project: Macintosh Mini (id: 1598d0ac-9f10-4eb8-989e-89ffd628cdcd), team Personal
- Branch prefix: wells/
- PR mode: ready

## Shipping
- Owners install and update by running `setup.sh` straight from `main`, and it fetches its helper
  files, chimes and `CHANGELOG.md` from `main` too. **Merging a change to any of those reaches
  every Mini the next time its owner runs the installer.** To test an unmerged branch on a real
  Pi, run that branch's `setup.sh` with `--branch <name>` (the flag only moves where the other
  files come from).
- A change owners should hear about bumps `VERSION` in `setup.sh` and adds a line to
  `CHANGELOG.md` in the same PR. The update menu shows the entries newer than the installed
  version, so write them for owners, one line each.
- Merging is not a release. A release (tag `vX.Y.Z` plus GitHub release notes) happens only when
  Wells asks.
- Emulators: CI (`.github/workflows/emulators.yml`) builds Basilisk II and SheepShaver, plain and
  tuned, for every push that touches `setup.sh` or the emulator scripts, publishes a pre-release
  `emulators-<commit>-<settings hash>`, and a bot commits its checksums into `setup.sh` on the
  branch. After changing the upstream pin (`MACEMU_COMMIT`, from kanjitalk755/macemu, not a fork)
  or the build settings, wait for the bot commit and pull before pushing again. Main never
  re-pins: if its pins go stale, CI fails and Pis fall back to compiling (several minutes, close
  to running out of memory). Bump `EMULATORS_RECIPE_REV` when `build-emulator.sh` changes what
  it builds.
- Mac OS 8.1 disk: the image lives only on the Internet Archive (item `macos-8.1-basilisk-ii`);
  `disk-image/` is the recipe. A new version gets a new file name and a re-pin of `DISK_DL_*` in
  `setup.sh`. Never replace or re-upload an existing version: installers pin its checksum.

## Docs

| | |
|---|---|
| `README.md` | Landing page: what it is, build or buy, the install command. Keep it short and scannable; only fix what would confuse a first-time reader. Detail goes in the build guide or the folder READMEs. |
| Build guide | wells.ee/projects/macintosh-mini/. Its source, drawings included, lives in Wells's private `wr/shop` repo; edit it there, never copy it back here. |
| `CHANGELOG.md` | Installer changes, read by the update menu. |
| `maclock-build/README.md` | Setting up the Pi by hand: what `setup.sh` does, step by step. |
| `emulators/` | Installing Basilisk II or SheepShaver by hand; the startup chimes. |
| `maclock-pcb/README.md` | The breakout board: BOM and the PCBWay project. |
| `maclock-screen-bezel/`, `maclock-usb-jig/` | Printed parts, each with its own README. |
| `disk-image/README.md` | Building, checking and uploading a new Mac OS 8.1 disk. |
| `docs/setup-guide/` | The printed setup guide for finished Macs. |
| `REUSE.toml` | Which licence covers each file. |

## Board revisions
- `main` has rev 2026.05 (solder pads, only the Pi header), which the PCBWay shared project builds.
- The boards that were built and shipped say rev 2026.09 on the silk. Anything about real,
  measured or shipped boards means 2026.09, even where it says "2026.10" (PR #21's description
  does): rev 2026.10 was never built.
- Rev 2026.11 (on-board amp with its own quiet supply, HUANO dial, PicoBlade plugs) and the GPIO
  interposer are on PR #21, unbuilt. Rev 2026.09's files are in that branch's history.

## KiCad
Three tools, three jobs:
- **Scripted `pcbnew`** (KiCad's bundled Python) makes every board edit: small, single-purpose,
  re-runnable scripts. Run them from a scratch folder and never commit them; commit the resulting
  `.kicad_*` files and say why in the commit message.
- **`kicad-cli`** verifies and exports: ERC, DRC, BOM and fab outputs. It isn't on `PATH`; call it
  inside the KiCad app bundle, and check `<subcommand> --help` first (KiCad 10 flags differ).
- **Konnect** (MCP) opens, views and reads projects. It can't set a pad's net or delete board
  graphics; do those in a `pcbnew` script.

Habits:
- Edit files on disk with KiCad closed. Wells edits in the GUI between turns, so re-read the board
  from disk (and check for `~*.lck`) before every scripted edit.
- DRC gate: `kicad-cli pcb drc --refill-zones --schematic-parity --severity-all <board>`; treat
  every unconnected item as real. ERC: 0 errors. BOM from the schematic, with `--exclude-dnp`.
- After Konnect edits a schematic, run `kicad-cli sch upgrade --force` and re-check ERC.
- Let ground pads join the pour; add free-standing stitching vias, not a stub and via per pad.
- pcbnew 10 traps: after the first change in a process, getters can return bare `SwigPyObject`s,
  so read everything first, then mutate; iterate `fp.GraphicalItems()` last, in its own run. A
  pad's `(at)` is the hole and the drill offset moves the copper. When swapping a footprint, reuse
  the old one's UUID so the diff stays small.

## Printed parts
Follow airwriter's enclosure pattern (github.com/wr/airwriter, `enclosure/`): one folder per part
with `build123d` pinned in `requirements.txt`, a gitignored `.venv` made with Python 3.14
(build123d won't install on 3.15), `params.py` (every number a named constant whose docstring says
where it came from), the part module, `test_*.py` (unittest) pinning what the part is for,
`export.py`, and `build.sh`, which runs the tests and writes STEP and STL. Keep the bezel in its
original coordinates so its STL stays drop-in. Render and look at a part before calling it done.
build123d traps: `Compound & Box` returns empty (use `part.solids()[0] & probe`); booleans on
coincident faces return nothing (overshoot the cut).

## Printed guides
Start from `docs/setup-guide/` (HTML printed to PDF by headless Chrome in `build.sh`, which needs
the internet for its fonts). A guide reads
as a plain document: one column, headings and paragraphs, no window frames, boxes or side-by-side
columns; the only UI on the page is real screenshots. Typed text is blue as well as monospace.
One double-sided US Letter sheet: setup looks short on the front, the optional parts go on the
back under "Going further", help links at the end. Use Wells's wording verbatim where he gives it.

## Licensing
Hardware folders are CERN-OHL-S-2.0, `setup.sh`, `maclock-build/` and the other scripts are
GPL-3.0-or-later, everything else is CC-BY-SA-4.0. `REUSE.toml` maps every file. Adding a file
someone else made (3D model, overlay, sound, icon) means adding its `REUSE.toml` annotation in the
same change; never commit a third-party file without a licence. Lint in a scratch venv:
`pip install 'reuse[charset-normalizer]' && reuse lint` (plain `reuse` fails on macOS).

## Testing on a real Pi
- Ask before using a Pi: they're shared with other sessions, and one is Wells's everyday Mac.
  Addresses and logins are in Wells's private notes. Use the IP; `.local` names may not resolve.
- Run the installer on the Pi itself, detached (`setsid nohup`, in a pty, with `TERM` set): Wi-Fi
  drops SSH under install load and would kill it. Without `TERM`, whiptail fails and `setup.sh`
  exits 0 silently. Keep helper scripts in `~`, not `/tmp`, which the installer's reboot wipes.
- To drive the update menu remotely, give the pty a real size (60 rows by 160 columns) and press
  Enter once at "Update to version".
- A failed `ssh` is not "the emulator stopped": act only on an answer from a successful one.
- A weak charger resets the Pi when the setup hotspot starts; use a good one.
- Timed listening tests that Wells records on his phone: chat doesn't reach him in time, so play a
  distinct 1 s ready tone from the speaker, wait 2 s, then the sync beeps and the first state.
- Leave nothing behind: purge any tool you installed for a test.

## Verification
```bash
cd maclock-build && python3 -m unittest            # the Pi helpers and pieces of setup.sh
.github/scripts/test-emulators.sh                  # emulator pin plumbing
cd disk-image && .venv/bin/python -m unittest -v   # disk recipe (venv per its README)
cd maclock-screen-bezel && ./build.sh              # tests, then STEP + STL (same for maclock-usb-jig)
```
Anything an owner sees or hears on a Mini gets tried on a real Pi before it's called done.

## Layout
```
setup.sh            the installer (curl | bash from main)
maclock-build/      Pi helpers it installs (buttons, brightness, Wi-Fi setup) and their tests
emulators/          emulator notes and the startup chimes
disk-image/         recipe for the Mac OS 8.1 disk on the Internet Archive
maclock-pcb/        breakout board (KiCad 10)
maclock-screen-bezel/, maclock-usb-jig/   printed parts (build123d)
docs/setup-guide/   printed setup guide
.github/            emulator CI and the weekly upstream watch
```
