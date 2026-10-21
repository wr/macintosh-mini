# Prebuilt Emulators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CI builds Basilisk II and SheepShaver (plain and tuned) once per pinned macemu commit, and `setup.sh` downloads and verifies them instead of compiling on the Pi, falling back to the compile.

**Architecture:** One marked settings block in `setup.sh` defines flags, packages, the run check and the release tag. The on-Pi compile and CI both use it. CI publishes a pre-release per tag and commits a second marked block of checksums back to the branch. The Pi downloads only when that block is current for its own settings.

**Tech Stack:** bash, GitHub Actions (`ubuntu-24.04-arm`, `docker run debian:trixie`), `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-10-20-prebuilt-emulators-design.md`

## Global Constraints

- Prebuilts only when `dpkg --print-architecture` = `arm64` and `VERSION_CODENAME` = `trixie`.
- Release tag `emulators-<commit7>-<recipe8>`; assets `BasiliskII-perf0.gz`, `BasiliskII-perf1.gz`, `SheepShaver-perf0.gz`, `SheepShaver-perf1.gz`, `SHA256SUMS`.
- Release URL base `https://github.com/wr/macintosh-mini/releases/download`.
- Pre-release, never latest, created as a draft then published, never overwriting an asset.
- The build record line stays `"<commit> perf=N"` (PR #45's `emu_build`), whichever path installed the binary.
- New scripts carry `SPDX-FileCopyrightText: 2026 Wells Riley` / `SPDX-License-Identifier: GPL-3.0-or-later`. `REUSE.toml` gets PR #46's exact line.
- Ships in 1.8.0 (no `VERSION` bump), stacked on `ww/emulator-rebuild-stamps`.

## Review Focus

1. A pin block written for an older commit or older flags: the Pi must compile, not download. Covered by `test-emulators.sh` (stale-tag case).
2. A download that 404s, is truncated, or has the wrong checksum: the Pi logs why and compiles, ending with a working Mac. Covered by the Pi fallback test (Task 5).
3. `--debug` runs: `try_run` must not exit on failure, and the fallback must run. Checked by reading the code (`run` in debug mode already returns rc).
4. A fresh install with only the runtime packages: the binary loads every library. Covered by the clean-container check in CI's build job (Task 3).
5. Two pushes racing on one branch: the bot never commits pins for a tag that is no longer the tip's. Covered by `pin-emulators.sh check` before commit (Task 3).

---

### Task 1: Shared build settings in setup.sh (no behaviour change)

**Files:** Modify `setup.sh` (block after `MACEMU_COMMIT`; `prepare_build`, `prepare_basilisk_build`; `APT_PKGS`). Create `.github/scripts/test-emulators.sh`.

**Interfaces (produces):**
- Arrays `MACEMU_BUILD_PKGS`, `MACEMU_RUNTIME_PKGS=(libsdl2-2.0-0 libmpfr6)`, `BASILISK_CONFIGURE`, `SHEEPSHAVER_CONFIGURE`. Strings `BASILISK_CFLAGS`, `SHEEPSHAVER_CFLAGS`, `PERF_CFLAGS`, `EMULATORS_IMAGE=debian:trixie`, `EMULATORS_RECIPE_REV=1`.
- `emulators_recipe` → 8 hex digits. `emulators_tag` → `emulators-<commit7>-<recipe8>`.
- `check_emulator <binary>` → 0 if `ldd` has no `not found` and `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 30 <binary> --help` exits 0 and prints `Build Date`.
- All of this sits between `# >>> emulator build settings` and `# <<< emulator build settings <<<` and must be `eval`-able on its own (with `MACEMU_REPO`/`MACEMU_COMMIT`).

- [ ] Write `test-emulators.sh` with `load_settings <setup.sh>` (sed the two pin lines plus the block, eval). Tests: the tag matches `^emulators-b9a71d7-[0-9a-f]{8}$`; it's stable across two loads; changing `BASILISK_CFLAGS` changes it; the flags equal today's literals (`-g -O3`, `-DMEM_BULK -g -O3`, `--enable-sdl-video --enable-sdl-audio --disable-jit-compiler --enable-vosf --with-gtk=no`, `--with-gtk=no`, `-mcpu=cortex-a53 -mtune=cortex-a53`).
- [ ] Run it and see it fail (no block yet).
- [ ] Add the block. Make the two prepare functions use it. Replace the literal build packages in `APT_PKGS` with `"${MACEMU_BUILD_PKGS[@]}"` for now (Task 2 moves them).
- [ ] Run `bash -n setup.sh` and the tests: pass.
- [ ] Commit.

### Task 2: Download path on the Pi

**Files:** Modify `setup.sh` (pin block after the settings block; helpers after `record_build`; step count; apt list; both emulator sections). Extend `test-emulators.sh`.

**Interfaces:**
- Pin block between `# >>> prebuilt emulators` and `# <<< prebuilt emulators <<<`: `EMULATORS_RELEASE=""`, `EMULATORS_SHA256=()` (entries `"<asset> <sha256>"`).
- `EMULATORS_URL="https://github.com/wr/macintosh-mini/releases/download"`
- `prebuilt_asset <Emulator>` → `<Emulator>-perf${PERF:-0}.gz`. `prebuilt_sha <asset>` → its sha or return 1.
- `prebuilt_available <Emulator>`: arm64, trixie, `EMULATORS_RELEASE == $(emulators_tag)`, and a sha for the asset.
- `install_prebuilt <Emulator> <stamp>`: curl into `mktemp -d`, `sha256sum -c`, gunzip, `check_emulator`, `sudo install -m755` to `/usr/local/bin/<Emulator>`, `record_build <stamp>`. It always cleans up the temp dir.
- `try_run <label> cmd…`: like `run`, but returns rc and logs `"(<label> didn't work; building on the Pi instead)"`.
- `install_build_tools`: `sudo apt-get install -y "${MACEMU_BUILD_PKGS[@]}"`.

- [ ] Tests: `prebuilt_available` is false with an empty block, and false when `EMULATORS_RELEASE` is the tag for another commit. `prebuilt_sha` picks the right line. Run them and see them fail.
- [ ] Implement the helpers.
- [ ] Main apt list: `MACEMU_RUNTIME_PKGS` in place of the build packages.
- [ ] Sections: `needs_build`, then `prebuilt_available && try_run "[basilisk] Downloading Basilisk II (built by GitHub)" install_prebuilt …`. Otherwise `TOTAL_STEPS += 6` if a download was tried, then `run "[basilisk] Installing build tools" install_build_tools`, then today's five steps. The same for SheepShaver.
- [ ] Step count: a build that's due is +9 with a prebuilt, +14 without, for each emulator (was +13).
- [ ] Run `bash -n` and the tests: pass. Commit.

### Task 3: CI scripts and workflow

**Files:** Create `.github/scripts/build-emulator.sh`, `.github/scripts/pin-emulators.sh`, `.github/workflows/emulators.yml`. Modify `REUSE.toml`.

**Interfaces:**
- `build-emulator.sh <BasiliskII|SheepShaver> <0|1> <outdir>` runs inside `debian:trixie` as root with the repo at `/repo`. It loads the settings via `pin-emulators.sh`'s loader, installs git and the build packages, clones and checks out the pin, configures and builds as `setup.sh` does, then runs `check_emulator`. It writes `<outdir>/<Emulator>-perf<N>.gz` (`gzip -n -9`) and `<outdir>/<Emulator>-perf<N>.config.h`. It then runs `check_emulator` again in a fresh `debian:trixie` with only `labwc` and the runtime packages, as a separate workflow step.
- `pin-emulators.sh tag` prints the tag. `pin-emulators.sh status` prints `current` (the release exists and the pins match), `repin` (the release exists and the pins differ) or `build`. `pin-emulators.sh write <SHA256SUMS>` rewrites the pin block. `pin-emulators.sh notes` prints the release notes.
- Workflow jobs: `plan` → `build` (4-way matrix, `ubuntu-24.04-arm`, `sudo sysctl -w vm.mmap_min_addr=0`) → `publish` (draft, upload, publish `--prerelease --latest=false`) → `pin` (rebase on the branch tip, re-check the tag, write, commit, push; on main, fail if the pins are stale).

- [ ] `test-emulators.sh`: `pin-emulators.sh write` on a copy of `setup.sh` replaces only the block, and doing it twice is a no-op. See it fail, implement, see it pass.
- [ ] Write the build script and the workflow. Add the REUSE line.
- [ ] `bash -n`, `shellcheck` if available, and `actionlint` if available.
- [ ] Commit, push, and watch the first run. Fix until all four builds pass, the release is published, and the bot's pin commit lands. Then push a no-op `setup.sh` comment change and check that `plan` says `current`.

### Task 4: Docs

**Files:** `emulators/README.md` (the maintainer checklist from PR #45), `CHANGELOG.md` (1.8.0).

- [ ] The checklist gets the step: wait for "Prebuilt emulators", pull the bot commit, and check the update log says it downloaded. It also notes when to bump `EMULATORS_RECIPE_REV`.
- [ ] The 1.8.0 line: the emulator is downloaded and checked, and it's compiled on the Pi only if that doesn't work. Fresh installs skip the compiler tools.
- [ ] Commit.

### Task 5: Verification on the test Pi, then the PR

- [ ] Compare the CI `config.h` with the one in `~/b2bench` (Basilisk II, perf 0): the only differences should be paths.
- [ ] Download path: set the Pi's Basilisk II record to the old commit, so an update is due. Run the branch's `setup.sh` detached with `TERM` set. Then check:
  - the log shows the download step, and no compile
  - `/usr/local/bin/BasiliskII` matches the perf=1 asset (gunzipped)
  - the record reads `"<commit> perf=1"`
  - after the reboot, the Finder shows over VNC and a page loads
- [ ] Fallback: the same, with a copy of `setup.sh` whose `EMULATORS_URL` is broken. Then again with one wrong checksum. Each time, check that the log says why, that the compile ran, and that the Mac comes back.
- [ ] SheepShaver: download its asset on the Pi and run `check_emulator` on it.
- [ ] Open a PR against `ww/emulator-rebuild-stamps` (draft until the Pi checks pass). Bind it with ccd_pr.
