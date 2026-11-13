# Prebuilt emulators: download Basilisk II and SheepShaver instead of compiling them on every Pi

Status: draft, for Wells's approval (decisions 1 to 5 agreed in chat)
Date: 2026-10-20
Builds on: PR #43 (pinned `MACEMU_COMMIT`) and PR #45 (build records `"<commit> perf=0|1"`)

## Why

`setup.sh` compiles Basilisk II (and SheepShaver, for the PowerPC option) from kanjitalk755/macemu at the pinned commit on every Pi. That happens on a fresh install, and again on every update that moves the pin or flips the performance option. Measured on the test Pi (Pi Zero 2 W, Raspberry Pi OS 13, 2026-10-20), using `setup.sh`'s exact flags with the Mac running alongside it, as during an update:

- **Time:** configure 106 s, `make -j4` 382 s, so about 8 minutes, plus a ~20 MB clone on a fresh install.
- **Memory:** the compilers peaked at 220 MB together. Available RAM fell to 53 MB, and the 415 MB zram swap was briefly 100% full. There was no OOM kill, but there was no margin either.
- **Build tools:** a fresh install also installs 166 packages that only the compile needs (build-essential, autotools, the `-dev` libraries). That's about 50 MB to download and 235 MB on the card.

The pin only moves on purpose, as a tested installer release, so each pin needs building exactly once. GitHub's free arm64 runners can do that once, and every Pi can download the result in seconds.

## Goals

- When a prebuilt binary matches the Pi, an install or update downloads it instead of compiling, for either emulator, with the performance option on or off.
- A fresh install doesn't install the compiler tools unless it has to compile.
- The Pi only installs a download it can prove is the file CI built from the pinned commit with the installer's flags. Anything else falls back to compiling, exactly as today.
- Moving the pin stays a one-PR job. CI builds the binaries and writes their checksums into that PR.

## Non-goals

- Other OS releases or architectures: Raspberry Pi OS 12 (bookworm), 32-bit (armhf), or anything that isn't Debian 13 arm64. Those Pis compile, as today. A later OS gets its own build when the guide moves to it.
- Removing the compiler tools from existing installs. They stay; nothing is uninstalled.
- An option to force a compile. The fallback is tested by breaking the download, not through a user-facing switch.
- Byte-for-byte reproducible builds. They'd be nice, but they aren't needed, because the checksums are pinned in `setup.sh`.

## Anti-goals (it fails if it does these, even if it works)

- Installs a binary whose checksum doesn't match the one pinned in `setup.sh`, or one that can't load its libraries or start.
- Leaves a Pi with no working emulator because a download failed. A failed or unusable download must end the same as today: compiled on the Pi.
- Lets the downloaded and the compiled binaries drift apart, by building with different flags or from a different commit.
- Makes moving the pin harder: more manual steps, or a PR that can be merged half-done without anyone noticing.
- Shows emulator builds as the repo's "Latest" release in place of the installer versions.

## Decisions Wells made (2026-10-20)

1. **Go ahead**, and fresh installs skip the compiler tools unless the download fails.
2. **Two variants of each emulator**: plain, and tuned (`-mcpu=cortex-a53 -mtune=cortex-a53`). The installer downloads the one matching `PERF`, so the build record (`"<commit> perf=N"`) means the same thing whether the binary was downloaded or compiled.
3. **CI writes the checksums into `setup.sh` itself**, as a commit on the same branch.
4. **Releases link to the source but don't attach it**: the exact upstream commit, plus the build script and `setup.sh` at the commit that built them. There's no source snapshot.
5. **Ships in 1.8.0**, stacked on PR #45, so the Macs that rebuild for 1.8.0's pin move download instead. PRs #43 and #45 wait for this to be built and tested on the Pi. The 1.8.0 changelog line about the rebuild says the emulator is now downloaded, and compiled only if the download doesn't work.

## How it works

### One definition of how the emulators are built

The flags and package lists move into one marked block near the top of `setup.sh`. Both the on-Pi compile and CI read this block, so they can't drift:

```bash
# >>> emulator build settings >>>
MACEMU_BUILD_PKGS=(build-essential autoconf automake libtool pkg-config
  libsdl2-dev libgl1-mesa-dev libxkbcommon-dev libmpfr-dev)
MACEMU_RUNTIME_PKGS=(libsdl2-2.0-0 libmpfr6 ...)   # final list settled by testing, see below
BASILISK_CFLAGS="-g -O3"
BASILISK_CONFIGURE=(--enable-sdl-video --enable-sdl-audio --disable-jit-compiler --enable-vosf --with-gtk=no)
SHEEPSHAVER_CFLAGS="-DMEM_BULK -g -O3"
SHEEPSHAVER_CONFIGURE=(--with-gtk=no)
PERF_CFLAGS="-mcpu=cortex-a53 -mtune=cortex-a53"
EMULATORS_IMAGE="debian:trixie"   # what CI builds in
EMULATORS_RECIPE_REV=1            # bump when the CI build steps change in a way that matters
# The recipe key: a hash of everything above plus the pin. The Pi and CI both
# compute it, so a download is only used if it was built from exactly this.
emulators_recipe() {
  printf '%s\n' "$MACEMU_REPO" "$MACEMU_COMMIT" "${MACEMU_BUILD_PKGS[*]}" \
    "$BASILISK_CFLAGS" "${BASILISK_CONFIGURE[*]}" "$SHEEPSHAVER_CFLAGS" \
    "${SHEEPSHAVER_CONFIGURE[*]}" "$PERF_CFLAGS" "$EMULATORS_IMAGE" "$EMULATORS_RECIPE_REV" |
    sha256sum | cut -c1-8
}
emulators_tag() { echo "emulators-${MACEMU_COMMIT:0:7}-$(emulators_recipe)"; }
# <<< emulator build settings <<<
```

`MACEMU_REPO` and `MACEMU_COMMIT` stay where they are. `prepare_build` and `prepare_basilisk_build` use these variables instead of literals, so the compile itself doesn't change. CI extracts the block with `sed` between the markers and `eval`s it, together with the `MACEMU_REPO`/`MACEMU_COMMIT` lines. It's our own file, and the workflow only runs on pushes to this repo.

The key is computed from the variables' values, not the file's text, because a Pi running `curl … | bash` has no copy of the file to hash. The runtime package list is left out of the key: it changes what gets installed next to the binary, not the binary.

The build steps themselves (`make links`, `autogen.sh`, `make -j`) are short, so they live in two places: `setup.sh` and the CI build script. Each has a comment pointing at the other.

### The pins in setup.sh (written by CI)

A second marked block holds what CI produced. People don't edit it by hand:

```bash
# >>> prebuilt emulators (written by CI: .github/workflows/emulators.yml) >>>
EMULATORS_RELEASE="emulators-b9a71d7-1a2b3c4d"
EMULATORS_SHA256=(
  "BasiliskII-perf0.gz <64 hex>"
  "BasiliskII-perf1.gz <64 hex>"
  "SheepShaver-perf0.gz <64 hex>"
  "SheepShaver-perf1.gz <64 hex>"
)
# <<< prebuilt emulators <<<
```

The block is **stale** when `EMULATORS_RELEASE` isn't `$(emulators_tag)`. That happens when the pin, the flags or the recipe revision moved but CI hasn't re-pinned yet, for example when a branch was merged before the bot's commit landed. A stale or empty block means no download, and the Pi compiles. So a binary built from an old commit or old flags is never installed under a new build record.

### On the Pi

**Eligibility** is checked before the step count, with no network. All four must hold:

- `dpkg --print-architecture` is `arm64`
- `/etc/os-release` has `VERSION_CODENAME=trixie`
- `EMULATORS_RELEASE` equals `$(emulators_tag)`
- `EMULATORS_SHA256` has an entry for `<Emulator>-perf<PERF>.gz`

If any of those fails, the Pi goes straight to the compile path, with today's step count.

**The download step** (one gauge step, `[basilisk] Downloading Basilisk II (built by GitHub)`, and the same for SheepShaver) runs only when `needs_build` says a build is due:

1. Download `https://github.com/wr/macintosh-mini/releases/download/$EMULATORS_RELEASE/<asset>` into a fresh `mktemp -d` (`curl -fL --retry 3`).
2. `sha256sum` it against the pinned value.
3. `gunzip`, `chmod 755`.
4. Check `ldd` for any `not found`.
5. Check that it starts: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 30 <bin> --help` exits 0 and prints `Build Date`. Both emulators print usage and exit there. SheepShaver initialises SDL first, which is why the dummy drivers are needed.
6. `sudo install -m755` to `/usr/local/bin/<Emulator>`, then `record_build` with the same stamp line as a compile (`"<commit> perf=N"`).

Any failure at steps 1 to 5 returns non-zero, and the reason goes to the log. This step uses a new `try_run` helper, which is like `run` except that a failure is logged and returned instead of ending the install. Then the existing compile path runs, preceded by a new step that installs `MACEMU_BUILD_PKGS` (quick when they're already there). On fallback, `TOTAL_STEPS` grows by the compile path's steps, so the gauge stays honest (it steps back a little).

The sysctls (`mmap_min_addr`, `overcommit`) are still written before either path, because the emulators need them at runtime too.

**apt:** the main install gets `MACEMU_RUNTIME_PKGS` instead of the build packages. Build packages are installed only by the fallback. The binaries need `libSDL2-2.0.so.0`, `libmpfr.so.6`, `libgmp.so.10` (Basilisk II), `libstdc++`, `libgcc_s` and `libc`. The rest of the runtime list (whether SDL needs `libgl1` or anything else that the `-dev` packages used to pull in as a side effect) is settled by testing on a clean Debian 13 arm64 system with labwc installed, and confirmed on the test Pi.

### In CI

**Files:**

- `.github/workflows/emulators.yml` ("Prebuilt emulators")
- `.github/scripts/build-emulator.sh`: builds one emulator in one variant inside the container
- `.github/scripts/pin-emulators.sh`: plans the release, and rewrites the pin block

**Triggers:** `push` to any branch touching `setup.sh`, the two scripts or the workflow, plus `workflow_dispatch`. `permissions: contents: write`. Runs on the same ref are queued (`concurrency`, `cancel-in-progress: false`), so a release is never left half-made.

**Release tag:** `$(emulators_tag)`, i.e. `emulators-<commit7>-<recipe8>`, computed by sourcing the extracted block, exactly as the Pi does. Change the pin, the flags, the image or `EMULATORS_RECIPE_REV`, and you get a new release. Change anything else in `setup.sh`, and the plan job finishes in seconds with nothing to build. Edits to `build-emulator.sh` don't change the tag by themselves. Whoever makes one that changes the binaries bumps `EMULATORS_RECIPE_REV`, and a comment at the top of the script says so.

**Jobs:**

1. **plan** works out the key and tag.
   - The release exists and the pins in `setup.sh` match its `SHA256SUMS`: done.
   - The release exists but the pins don't match: re-pin (no build).
   - Otherwise: build.
2. **build** runs on `ubuntu-24.04-arm` as a matrix (Basilisk II, SheepShaver) × (perf 0, perf 1): four jobs in parallel. On the host it runs `sudo sysctl -w vm.mmap_min_addr=0` (configure probes low memory, as on the Pi), then `docker run debian:trixie` with the repo mounted, running `build-emulator.sh <emulator> <perf>`. Inside the container, that script installs git and `MACEMU_BUILD_PKGS`, clones `MACEMU_REPO` at `MACEMU_COMMIT`, configures and builds with the flags from the block, then runs the same `ldd` and `--help` checks the Pi runs, then `gzip -n`. The `.gz` is uploaded as an artifact.
3. **publish** collects the four `.gz` files and writes `SHA256SUMS`. It creates the release as a draft, uploads everything, then publishes it, so a release is never visible half-uploaded (and this works if immutable releases are ever turned on). The release is a pre-release and never marked latest. It targets the commit that built it, and it never overwrites an existing asset. The release notes give:
   - the upstream commit link
   - the build script and `setup.sh` links at the building commit
   - the workflow run link
   - the flags
   - the licence (GPL-2.0, upstream's), with a pointer to the upstream source at that commit
4. **re-pin** rewrites the pin block from the release's `SHA256SUMS`.
   - On a branch other than `main`, it commits as `github-actions[bot]` ("Installer: pin the prebuilt emulators for macemu b9a71d7") and pushes, after rebasing onto the branch tip. If the tip's `emulators_tag` no longer matches the release it just built (someone pushed another pin or flag change meanwhile), it commits nothing. The run that push started will build and pin the newer one.
   - On `main`, it never commits. It fails, naming the lines that need to change, so a stale pin on main can't go unnoticed. Pis on main still compile, which is safe.

   Pushes made with `GITHUB_TOKEN` don't start workflows, so the bot commit doesn't loop. It also means the bot's commit itself has no check run, which is fine because nothing requires checks.

### Moving the pin, from the maintainer's side

The checklist in `emulators/README.md` (from PR #45) gets one step: after pushing the pin move, wait for "Prebuilt emulators" to finish, pull its commit, then test on a Pi. The test now also covers the download (the log says "Downloading"). The release appears under Releases as a pre-release, "Emulators b9a71d7 (Debian 13, arm64)".

## Testing (before the PR is called ready)

- CI on this branch builds all four binaries, publishes a release, and commits the pins. Pushing again with no build change rebuilds nothing.
- The CI-built Basilisk II and SheepShaver `config.h` files (uploaded as build artifacts, not release assets) match the ones from a Pi build. Basilisk II's is in `~/b2bench` on the test Pi. This checks that configure's probes came out the same.
- The builder has SSH to the test Pi (`wells@10.0.1.111`) and drives the Mac over wayvnc. Evidence that the Mac works is a VNC screenshot of the Finder and a page loaded in its browser. The chime can't be heard remotely, so that's the one check left for Wells.
- On the test Pi (Basilisk II, perf=1), an update that has to rebuild downloads instead:
  - the step finishes in seconds
  - the record says `"<commit> perf=1"`
  - the Mac boots with its chime and gets online
- Fallback: a copy of the branch's `setup.sh` with a broken release URL (and, separately, a wrong checksum) logs why, then installs the build tools if needed, compiles, and ends with a working Mac.
- Runtime packages: a clean `debian:trixie` arm64 container with `labwc` and `MACEMU_RUNTIME_PKGS`, but no build packages, runs both binaries' `ldd` and `--help` checks.
- SheepShaver: CI builds it. On the Pi, check at least that its download, checksum, `ldd` and `--help` steps pass. A full boot needs the 4 MB ROM and a disk, and is only done if they're at hand.

## Builder's calls (not asked; change them if they're wrong)

- Prebuilts only for Debian 13 (trixie) arm64. Everything else compiles.
- Binaries keep their debug info (`-g`), same as today's compile, and are gzip-compressed (gzip is always there, xz might not be). About 3 MB each.
- The checksum pinned is the `.gz` file's, checked before anything is decompressed.
- Asset names don't repeat the commit, since the tag carries it.
- `debian:trixie` isn't pinned by digest. Point releases keep the same library versions within Debian 13, and the Pi-side checks would catch a mismatch.
- `.github/workflows/**` and `.github/scripts/**` are GPL-3.0-or-later in `REUSE.toml`, the same line PR #46 adds. The scripts also carry SPDX headers, as #46's do.
