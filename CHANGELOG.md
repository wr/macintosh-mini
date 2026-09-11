# Changelog

All notable changes to the macintosh-mini installer (`setup.sh`) are recorded
here. The version is the `VERSION` string in `setup.sh`; re-running the
installer on an existing Pi prints the entries added since the installed
version.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-09-11

### Added
- Landscape orientation for the text console/terminal via a `video=…,rotate=270`
  kernel argument in `cmdline.txt`. ([#24](https://github.com/wr/macintosh-mini/pull/24))

### Fixed
- The updater now applies `cmdline.txt` and `config.txt` display changes when
  re-run on an existing install. `patch_cmdline` is idempotent per-token, so an
  update adds only what is missing instead of bailing the moment one old token
  is found. ([#25](https://github.com/wr/macintosh-mini/pull/25))
- Stale `display_rotate=3` (ignored under the vc4-kms driver) is removed from
  older `config.txt` installs.
- The emulator's landscape rotation is applied as soon as the compositor is
  ready instead of after a blind one-second wait, shrinking the brief
  un-rotated flash at launch.

## [1.3.0] - 2026-09-04

### Added
- Dim the screen automatically from sunset to sunrise. ([#22](https://github.com/wr/macintosh-mini/pull/22))

### Fixed
- Keep the configured hostname after a reboot on cloud-init images. ([#20](https://github.com/wr/macintosh-mini/pull/20))
- Keep the wi-fi radio awake so the Pi stays reachable instead of dropping off
  the network when idle. ([#19](https://github.com/wr/macintosh-mini/pull/19))

## [1.2.0] - 2026-08-25

### Fixed
- Fix backlight flicker and the brightness dial. ([#18](https://github.com/wr/macintosh-mini/pull/18))
- Don't crash when a graphics group is missing. ([#17](https://github.com/wr/macintosh-mini/pull/17))

## [1.1.0] - 2026-06-08

### Added
- Prompt for the BasiliskII model id — 5 (Mac IIci, System 7.0–7.1) or 14
  (Quadra, 7.5+/OS 8).

## [1.0.0] - 2026-05-28

### Added
- Version the installer. ([#10](https://github.com/wr/macintosh-mini/pull/10))
- BasiliskII (68k) emulator, now the default core.

### Fixed
- Suppress emulator core dumps and check the SheepShaver ROM size. ([#9](https://github.com/wr/macintosh-mini/pull/9))
- Clearer installer menu. ([#8](https://github.com/wr/macintosh-mini/pull/8))

[1.4.0]: https://github.com/wr/macintosh-mini/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/wr/macintosh-mini/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/wr/macintosh-mini/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/wr/macintosh-mini/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/wr/macintosh-mini/releases/tag/v1.0.0
