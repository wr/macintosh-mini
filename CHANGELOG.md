# Changelog

Notable changes to the macintosh-mini installer (`setup.sh`). Re-running on an
existing Pi shows the entries added since the installed version.

## [1.10.0] - 2026-10-27
- Quieter speaker: no hiss, burble or ticking while the Mac is silent. A faint click about 3 s after a sound is normal.
- The startup chime no longer crackles on Macs set up from a fresh card.

## [1.9.1] - 2026-10-22
- A freshly flashed card no longer stops at "Installing apt packages" when the installer starts within a few minutes of the Pi's first start. When a hostname is set in Raspberry Pi Imager, Pi OS is still installing a package of its own then; the installer now waits for it to finish.

## [1.9.0] - 2026-10-21
- No disk image? A new Basilisk II install offers to download ours: a clean Mac OS 8.1 install with a web browser, After Dark, Big Maclock and the AppleTalk ImageWriter driver, checked before it's used. `--get-disk` downloads it without asking.

## [1.8.1] - 2026-10-21
- The Mac starts again where XWayland, which the emulators draw through, had gone missing. Raspberry Pi OS's labwc stopped installing it at the end of September, so new installs since then didn't get it, and `apt autoremove` could remove it from older ones. The installer now installs it itself and keeps it.

## [1.8.0] - 2026-10-21
- AppleTalk printers and file sharing work on your network alongside the internet, so the Chooser can find an AirWriter, say, while the browser stays online. New installs have it on; on an existing Mac, turn on AppleTalk in Edit settings.
- Basilisk II is replaced once, with fixes to its AppleTalk tunnel. Macs running SheepShaver get a new one too, since it shares that network code.
- The emulators now arrive ready-built: the installer downloads the one built for this release, checks it, and compiles on the Pi only if that doesn't work. A new emulator takes seconds instead of about 8 minutes, and the Pi no longer runs short of memory compiling it. Fresh installs skip the compiler tools too.
- Turning the performance option on or off now swaps the emulator for one with or without its speed tuning, to match the setting.

## [1.7.0] - 2026-10-17
- Change Wi-Fi without opening the case: hold the left button for 10 seconds, join the "Macintosh Mini XXXX" network from your phone, and pick your network on the page that opens. A Mac with no saved Wi-Fi offers it by itself.
- A Mac with no ROM says on screen how to add one from a phone or computer on the same Wi-Fi, with a QR code that opens the page.
- Setup shows a step-by-step window on the Mac's screen and plays short sounds when it's ready, connected or something didn't work. Its web page only runs during setup.
- `--hotspot-setup` prepares a Mac for someone else: their Wi-Fi, a password and a ROM are set up from their phone when it first starts.
- `.local` names work with the performance option on.

## [1.6.1] - 2026-10-05
- Turns the Pi's audio output down 4 dB, so the loudest notes of the startup chime no longer crackle through the board's amp.

## [1.6.0] - 2026-10-05
- Finds disk images named `.img`, `.hfv` or `.sparsebundle`, as well as `.hda` and `.dsk`, for either emulator.

## [1.5.0] - 2026-09-16
- Emulator alerts (e.g. no network for slirp) log to the journal instead of a dialog nobody can click; existing installs rebuild the emulator once.
- Hide agetty's "automatic login" line and systemd status lines at boot.
- Black-and-white installer theme, after the System 7 Installer.
- Rebooting after the night cutoff dims for ten minutes instead of coming up dark.
- Brightness dial turns the right way: clockwise brightens.
- Bluetooth stays on; it is no longer switched off by the performance option (`--no-bluetooth` to turn it off). Installs that lost it get it back after a reboot.

## [1.4.0] - 2026-09-11
- Console and emulator boot in landscape, rotated from the first frame.
- Emulator runs under labwc instead of cage — no rotation flash.
- Updater applies display changes on re-run, not just fresh installs.

## [1.3.0] - 2026-09-04
- Dim the screen from sunset to sunrise (#22).
- Keep the hostname after a reboot on cloud-init images (#20).
- Keep the wi-fi radio awake so the Pi stays reachable (#19).

## [1.2.0] - 2026-08-25
- Fix backlight flicker and the brightness dial (#18).
- Don't crash when a graphics group is missing (#17).

## [1.1.0] - 2026-06-08
- Prompt for the BasiliskII model id (Mac IIci vs Quadra).

## [1.0.0] - 2026-05-28
- First versioned installer; BasiliskII (68k) added as the default core (#8, #9, #10).

[1.6.1]: https://github.com/wr/macintosh-mini/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/wr/macintosh-mini/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/wr/macintosh-mini/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/wr/macintosh-mini/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/wr/macintosh-mini/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/wr/macintosh-mini/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/wr/macintosh-mini/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/wr/macintosh-mini/releases/tag/v1.0.0
