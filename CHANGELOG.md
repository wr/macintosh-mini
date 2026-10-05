# Changelog

Notable changes to the macintosh-mini installer (`setup.sh`). Re-running on an
existing Pi shows the entries added since the installed version.

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

[1.5.0]: https://github.com/wr/macintosh-mini/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/wr/macintosh-mini/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/wr/macintosh-mini/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/wr/macintosh-mini/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/wr/macintosh-mini/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/wr/macintosh-mini/releases/tag/v1.0.0
