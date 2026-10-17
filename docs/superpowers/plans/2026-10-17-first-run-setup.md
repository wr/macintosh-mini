# First-run Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Macintosh Mini that can be put on Wi-Fi and given a ROM from a phone, via an open "Macintosh Mini XXXX" hotspot with a captive-portal page, started automatically when no network is saved or by holding the left button for 10 s; plus an installer option that prepares a card for that.

**Architecture:** One root Python service (`mac-setup`, stdlib only) owns the state, drives NetworkManager through `nmcli`, serves both web pages on port 80, and writes `/run/mac-setup/status.json`. The tty1 launcher asks `mac-setup needed` and, when setup is due, runs `mac-setup screen` (a framebuffer renderer that draws whatever the status file says) instead of the emulator. The button handler gains a long-press on the left button. `setup.sh` installs it all and grows `--hotspot-setup`.

**Tech Stack:** Python 3 standard library (Pi OS Trixie ships 3.13: no `cgi` module), NetworkManager (`nmcli`, shared mode with its dnsmasq), `qrencode` (CLI), `iw`, systemd, bash.

**Spec:** `docs/superpowers/specs/2026-10-17-first-run-setup-design.md`

## Global Constraints

- Hotspot SSID: `Macintosh Mini XXXX`; hostname from `--hotspot-setup`: `macintosh-mini-xxxx`. `xxxx` = last 4 hex digits of the Pi serial (`/sys/firmware/devicetree/base/serial-number`, NUL-stripped, lowercased). The serial, not the Wi-Fi MAC, because NetworkManager randomises the MAC while scanning.
- Hotspot: open, NetworkManager connection named `mac-setup-hotspot`, `ipv4.method shared`, address `10.42.0.1/24`, band `bg`.
- Button hold: left button (`BTN2_PIN = 26`), 10 s. Button-triggered hotspot gives up after 300 s with no phone connected.
- ROM trial: a new ROM counts once the emulator has run 60 s.
- ROM sizes: Basilisk II 524288 or 1048576 bytes; SheepShaver 4194304. Downloads capped at 16 MiB.
- Guide link copy, verbatim: `Need a ROM? <a href="https://www.redundantrobot.com/sheepshaver">Redundant Robot's emulator guide</a> explains which one to use and where to find it. The Performa ROM works best.`
- Never restart NetworkManager. Never add prompts to the normal install. No outside resources in either web page.
- Python files carry the repo's SPDX header (`GPL-3.0-or-later`) like `button_handler.py`; tests run with `cd maclock-build && python3 -m unittest`.

## Review Focus

- Wrong Wi-Fi password typed on the phone: the failed profile must be deleted, otherwise "no saved networks" is false and the hotspot never comes back. (Task 3 test `test_failed_join_forgets_network_and_reopens_hotspot`.)
- A Mac with a ROM and saved networks booting during a router outage must stay `off`, never start the hotspot. (Task 3 `test_saved_network_offline_never_starts_hotspot`.)
- Tap and double-tap on the left button must feel the same as today; a hold must not also fire a restart. (Task 2 `test_hold_fires_once_and_no_tap`, `test_quick_tap_still_restarts`.)
- A pasted link that isn't a ROM (an HTML page, a 404, a huge file) must give a plain error, not a traceback or a full disk. (Task 1 `test_html_is_not_a_rom`, Task 4 `test_rom_url_too_big`.)
- A ROM that passes the check but makes the emulator quit at once must send the Mac back to the setup screen with "That ROM didn't start the Mac. Try another." (Task 3 `test_rom_trial_failure_returns_to_rom_page`; launcher half in Task 6.)

---

### Task 1: ROM extraction and checking

**Files:**
- Create: `maclock-build/mac_setup_rom.py`
- Test: `maclock-build/test_mac_setup_rom.py`

**Interfaces:**
- Produces: `class RomError(Exception)` (message is user-facing copy); `rom_checksum_ok(data: bytes) -> bool`; `check_rom(data: bytes, emulator: str) -> None` (raises `RomError`); `extract_rom(data: bytes, emulator: str) -> bytes` (raw or `.zip`, returns the ROM bytes, raises `RomError`). `emulator` is `"basilisk"` or `"sheepshaver"`.

The Apple ROM checksum: the first 4 bytes (big-endian) equal the sum of the big-endian 16-bit words from offset 4 to the end, modulo 2³². Verify this against the real ROM on the test Pi in Task 7; if a real ROM fails it, drop the checksum test and keep size only.

- [ ] **Step 1: Write the failing tests** — build synthetic ROMs with a helper `make_rom(size)` that fills bytes and writes a correct checksum. Tests:
  - `test_good_68k_rom_passes` (512 KB and 1 MB, basilisk)
  - `test_bad_checksum_rejected` → message contains "damaged"
  - `test_ppc_rom_rejected_for_basilisk` → "That's a PowerPC ROM; this Mac needs a 68k one like the Performa ROM."
  - `test_68k_rom_rejected_for_sheepshaver` → message contains "4 MB PowerPC ROM"
  - `test_wrong_size_rejected` → "That file isn't a Mac ROM."
  - `test_html_is_not_a_rom` (`b"<!DOCTYPE html>..."`) → "That file isn't a Mac ROM."
  - `test_zip_with_rom_inside` (zip holding `1mbMacrom.rom` plus a `readme.txt`) → returns the ROM bytes
  - `test_zip_without_rom` → "That zip doesn't have a Mac ROM in it."
  - `test_corrupt_zip` (`b"PK\x03\x04garbage"`) → `RomError`, not `zipfile.BadZipFile`
- [ ] **Step 2: Run, expect import failure**: `cd maclock-build && python3 -m unittest test_mac_setup_rom -v`
- [ ] **Step 3: Implement** the four names above. In `extract_rom`, zip members are tried largest-first among those of an accepted size; the first that passes `check_rom` wins; ignore member paths entirely (never extract to disk).
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `git commit -m "mac-setup: ROM extraction and checks"`

### Task 2: Left-button long press

**Files:**
- Modify: `maclock-build/button_handler.py`
- Test: `maclock-build/test_button_handler.py` (stub `lgpio` like `test_brightness_control.py`)

**Interfaces:**
- Produces: `class ButtonLogic` with `press(gpio: int, now: float) -> list[str]`, `release(gpio: int, now: float) -> list[str]`, `tick(now: float) -> list[str]`; each returns action names: `"single"`, `"double"`, `"hold"` qualified by gpio as `(gpio, action)` tuples. Constants `HOLD_S = 10.0`, existing `DEBOUNCE_MS`, `DOUBLE_PRESS_MS`. `HOLD_COMMANDS = {BTN2_PIN: ['/usr/local/bin/mac-setup', 'request']}`.
- Consumes: `mac-setup request` / `mac-setup cancel` (Task 3 CLI).

Behaviour: BTN1 fires `single` on press, as today. BTN2: a second press within 500 ms → `double`. After 500 ms with no second press: if already released → `single`; if still held → wait; released before 10 s → `single` at release; still held at 10 s → `hold` (once), and the release after a hold fires nothing. When `/run/mac-setup/requested` exists, BTN2's `single` runs `mac-setup cancel` instead of the restart wrapper.

- [ ] **Step 1: Write the failing tests**: `test_btn1_fires_on_press`, `test_quick_tap_still_restarts` (press 0, release 0.1, tick 0.6 → single), `test_double_tap` (press 0, release 0.1, press 0.3 → double; tick 0.9 → nothing), `test_held_past_window_then_released_is_single` (press 0, tick 0.6 → nothing, release 3.0 → single), `test_hold_fires_once_and_no_tap` (press 0, tick 10.0 → hold, tick 11 → nothing, release 12 → nothing), `test_bounce_ignored` (press 0, press 0.02 → nothing extra).
- [ ] **Step 2: Run, expect failure**: `python3 -m unittest test_button_handler -v`
- [ ] **Step 3: Implement `ButtonLogic`** and rewire `main()`: claim both pins with `lgpio.BOTH_EDGES`, call `press`/`release` from the callback by level, and run a 50 ms ticker thread calling `tick(time.monotonic())`; dispatch actions to `COMMANDS` / `DOUBLE_COMMANDS` / `HOLD_COMMANDS` (with the cancel substitution above). Keep the file's comments style and the editable dicts at the top.
- [ ] **Step 4: Run, expect PASS** (and `test_brightness_control` still passes)
- [ ] **Step 5: Commit** `git commit -m "Buttons: hold the left button for 10 s to start Wi-Fi setup"`

### Task 3: The setup service (state, NetworkManager, CLI)

**Files:**
- Create: `maclock-build/mac_setup.py`, `maclock-build/mac-setup.service`
- Test: `maclock-build/test_mac_setup.py`

**Interfaces:**
- Consumes: `extract_rom`, `RomError` (Task 1); `make_server(controller, port) -> ThreadingHTTPServer` (Task 4); `mac_setup_screen.main(status_path)` (Task 5).
- Produces:
  - Paths: `RUN_DIR=/run/mac-setup` (`status.json`, `requested`, `cancel`, `rom-trial`), `STATE_DIR=/var/lib/mac-setup` (`needs-password`), `CONF=/etc/mac-setup.conf`.
  - `load_config(path) -> Config(user, home, emulator, prefs)` (KEY=VALUE file written by setup.sh: `USER`, `HOME`, `EMULATOR`, `PREFS`).
  - `serial_suffix(path=...) -> str`, `hotspot_ssid(suffix) -> str`.
  - `country_for_timezone(tz: str, zone_tab_text: str) -> str | None` (from `/usr/share/zoneinfo/zone.tab`).
  - `class NM` (all via `nmcli`/`iw`): `saved_wifi() -> list[str]` (excludes `mac-setup-hotspot`), `connected_ssid() -> str | None`, `scan() -> list[str]` (unique, strongest first, hidden/empty dropped), `start_hotspot(ssid)`, `stop_hotspot()`, `join(ssid, password, hidden, timeout=45) -> bool` (deletes the profile it made on failure), `client_count() -> int`, `ip() -> str | None`.
  - `class System`: `set_password(user, pw)` (`chpasswd`, then `passwd -u`), `set_timezone(tz)`, `set_country(cc)` (`iw reg set` + `raspi-config nonint do_wifi_country` when present), `restart_tty1()`, `emulator_running() -> bool`, `beep()`.
  - `class Controller(config, nm, system, clock)`: `tick()`, `state() -> dict` (phase, reason, ssid, networks, needs_password, error, network, url, ip), `submit_wifi(req) -> None`, `submit_rom(data: bytes) -> str | None` (error copy or None), `screen_for(state) -> dict(title, lines, qr)`.
  - CLI `mac_setup.py serve|needed|request|cancel|screen`.

Phases: `off`, `waiting` (no ROM, saved networks, not connected), `hotspot`, `connecting`, `rom`, `starting`. Reasons: `first-run` (no saved networks: no timeout, no cancel), `button`. Screen copy is fixed in `screen_for` per the spec's "What the new owner does" and "Changing networks later" sections, with QR payload `WIFI:T:nopass;S:<ssid>;;` in `hotspot` phase only. `submit_wifi` responds immediately; a worker thread waits 3 s (so the phone gets the "Connecting…" page), stops the hotspot and joins. When the phase is `off`, `tick()` only looks at the flag files (no `nmcli`).

- [ ] **Step 1: Write the failing tests** with `FakeNM`, `FakeSystem`, a settable clock and a temp `RUN_DIR`/`STATE_DIR`/home:
  - `test_no_saved_networks_starts_first_run_hotspot` (scan happens before `start_hotspot`)
  - `test_saved_network_offline_never_starts_hotspot` (ROM present, saved networks, not connected → `off` after many ticks, `start_hotspot` never called)
  - `test_no_rom_connected_goes_to_rom_phase` (url `http://<hostname>.local/`, ip from `nm.ip()`)
  - `test_button_request_starts_hotspot_and_cancel_restores`
  - `test_button_hotspot_gives_up_after_300s_idle` (client seen at 100 → still up at 350, down at 401)
  - `test_first_run_ignores_cancel`
  - `test_submit_wifi_sets_password_tz_country_and_clears_marker`
  - `test_failed_join_forgets_network_and_reopens_hotspot` (error "Couldn't join Home. Check the password and try again.")
  - `test_successful_join_with_rom_returns_to_mac_os` (phase `off`, `restart_tty1` called, `requested` removed)
  - `test_submit_rom_writes_file_and_starts_trial` (file at the prefs `rom` path, `rom-trial` written)
  - `test_rom_trial_failure_returns_to_rom_page` (ROM moved aside within 60 s → `rom` phase with "That ROM didn't start the Mac. Try another.")
  - `test_rom_trial_success_after_60s` (emulator running at 61 s → `off`, `rom-trial` removed)
  - `test_country_for_timezone` (`America/New_York` → `US`, `Europe/Berlin` → `DE`, unknown → None)
  - `test_serial_suffix` (`b"00000000c3b74e2a\x00"` → `"4e2a"`)
  - `test_screen_for_each_phase` (titles and that only `hotspot` has a QR payload)
- [ ] **Step 2: Run, expect failure**: `python3 -m unittest test_mac_setup -v`
- [ ] **Step 3: Implement** `mac_setup.py`. The service unit: `After=NetworkManager.service`, `Wants=NetworkManager.service`, `ExecStart=/usr/bin/python3 /usr/local/lib/mac-setup/mac_setup.py serve`, `Restart=on-failure`, `RuntimeDirectory=mac-setup`, `RuntimeDirectoryMode=0755`, `RuntimeDirectoryPreserve=yes`, `WantedBy=multi-user.target`. `needed` (run as the normal user) exits 0 if `requested` exists or `saved_wifi()` is empty, else 1.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `git commit -m "mac-setup: setup service, hotspot control and CLI"`

### Task 4: The web pages

**Files:**
- Create: `maclock-build/mac_setup_web.py`
- Test: `maclock-build/test_mac_setup_web.py`

**Interfaces:**
- Consumes: `Controller.state()`, `submit_wifi`, `submit_rom` (Task 3, duck-typed so tests use a fake).
- Produces: `HOTSPOT_IP = "10.42.0.1"`; `class FormError(Exception)`; `ConnectRequest(ssid, wifi_password, hidden, mac_password, timezone)`; `parse_connect_form(body: bytes, needs_password: bool) -> ConnectRequest`; `make_server(controller, port=80) -> ThreadingHTTPServer`; `fetch_url(url: str, limit: int) -> bytes` (raises `FormError` with copy).

Routes, gated by phase: `hotspot` → `GET /` portal page, `POST /connect`, every other path or foreign `Host` → `302` to `http://10.42.0.1/`. `rom` → `GET /` ROM page, `POST /rom` (raw body, `Content-Length` ≤ 16 MiB), `POST /rom-url` (form `url`). Any other phase → `404`. Form rules: SSID 1–32 bytes; Wi-Fi password empty or 8–63 characters; Mac password required when `needs_password`, at least 4 characters, both fields match, no newline. The portal page sends the phone's time zone from `Intl.DateTimeFormat().resolvedOptions().timeZone` in a hidden field. Pages are self-contained HTML (inline CSS, a little inline JS for the time zone and the file upload), big tap targets, a light classic-Mac look (striped title bar, square corners).

- [ ] **Step 1: Write the failing tests** against a real server on `127.0.0.1:0` with a fake controller: `test_portal_lists_networks`, `test_portal_hides_password_fields_when_not_needed`, `test_captive_probe_redirects` (Host `captive.apple.com`, path `/hotspot-detect.html` → 302 to `http://10.42.0.1/`), `test_connect_bad_wifi_password_length` (page re-rendered with error), `test_connect_passwords_must_match`, `test_connect_ok_calls_controller_and_shows_connecting`, `test_rom_page_has_guide_link_copy` (exact copy from Global Constraints), `test_rom_upload_error_shown`, `test_rom_url_rejects_non_http` (`file:///etc/passwd`), `test_rom_url_too_big` (local test server sends 17 MiB → error copy "That file is too big to be a ROM."), `test_off_phase_404`.
- [ ] **Step 2: Run, expect failure**: `python3 -m unittest test_mac_setup_web -v`
- [ ] **Step 3: Implement** the module.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `git commit -m "mac-setup: phone setup page and ROM page"`

### Task 5: The setup screen

**Files:**
- Create: `maclock-build/mac_setup_screen.py`
- Test: `maclock-build/test_mac_setup_screen.py`

**Interfaces:**
- Consumes: `status.json` content `{"phase", "screen": {"title", "lines", "qr"}}` (Task 3).
- Produces: `qr_matrix(text: str) -> list[list[bool]]` (parses `qrencode -t ASCII -m 0 -l M`); `load_psf(path) -> Font`; `render(screen: dict, font, width=640, height=480) -> Canvas` (1 bit per pixel, black on white); `blit(canvas, fb_dir="/sys/class/graphics/fb0", dev="/dev/fb0")` (honours `bits_per_pixel`, `stride`, and the console rotation in `/sys/class/graphics/fbcon/rotate`); `main(status_path)`.

Rendering: QR on the left with whole-pixel modules as large as fit in 300 px plus a 2-module quiet zone; title at 2× scale and lines at 1× from the PSF font on the right; with no QR, text is centred. Font: first found of `Uni2-TerminusBold24x12.psf.gz`, `Lat15-TerminusBold24x12.psf.gz`, any `*Terminus*24x12*`, else the smallest available `.psf.gz`. `main` hides the cursor, redraws only when the status changes (poll 0.5 s), shows "Starting setup…" until a status file exists, and exits after the phase has read `off` for 2 s (the login shell then ends and getty starts the launcher again).

- [ ] **Step 1: Write the failing tests**: `test_qr_matrix_parses_ascii` (fake `qrencode` output fixture), `test_render_size_and_qr_left` (a dark pixel inside the QR box, none in the right margin), `test_render_without_qr_centres_text`, `test_load_psf_v1_and_v2` (tiny synthetic PSF files), `test_blit_rotation` (write to a temp file standing in for `/dev/fb0` at 16 bpp, rotate 1, check a known pixel lands at the rotated spot).
- [ ] **Step 2: Run, expect failure**: `python3 -m unittest test_mac_setup_screen -v`
- [ ] **Step 3: Implement** the module.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `git commit -m "mac-setup: setup screen on the Mac's display"`

### Task 6: Installer integration and `--hotspot-setup`

**Files:**
- Modify: `setup.sh` (usage header, argument parsing, asset checks, apt packages, perf mask list, both launchers, `mac-preflight`, a new install step, the end of the script, `VERSION`)

**Interfaces:**
- Consumes: everything above, fetched from `$REPO_RAW/maclock-build/` like `install_gpio_helpers` does.
- Produces: `/usr/local/lib/mac-setup/*.py`, `/usr/local/bin/mac-setup` (`exec python3 /usr/local/lib/mac-setup/mac_setup.py "$@"`), `/etc/systemd/system/mac-setup.service`, `/etc/mac-setup.conf`, `/etc/NetworkManager/dnsmasq-shared.d/mac-setup.conf` (`address=/#/10.42.0.1` and `dhcp-option=114,"http://10.42.0.1/"`).

Changes:
- `APT_PKGS` gains `qrencode` on every install.
- `mask_services` drops `avahi-daemon.service` and `avahi-daemon.socket`; a new step unmasks and enables them on every install (updates included).
- New step `Installing Wi-Fi setup (hotspot + setup page)` on every install that has an emulator: installs the files above, writes `/etc/mac-setup.conf` from `$USER`, `$HOME`, the installed emulator and its prefs path, `daemon-reload`, `enable` and `restart mac-setup`.
- `mac-preflight` exits `2` when the ROM is the only thing missing (disk present), printing nothing; other failures keep exit `1` and today's message.
- Both launchers: before the preflight, `if /usr/local/bin/mac-setup needed; then exec /usr/local/bin/mac-setup screen; fi`; after it, rc `2` → `exec /usr/local/bin/mac-setup screen`. Record `start=$(date +%s)` before `labwc`; after it exits, if `/run/mac-setup/rom-trial` exists and fewer than 60 s passed, `mv ~/ROM ~/ROM.rejected` (the prefs `rom` path) and fall through to relaunch, before the exit-0/143 branch.
- `--hotspot-setup`: sets `HOTSPOT_SETUP=1`; with no emulator flag implies `--all-basilisk`; skips the ROM check (disk still required); `NEW_HOSTNAME` defaults to `macintosh-mini-<suffix>`; warns via whiptail yes/no if `$USER` isn't `mac`. Usage header gets the plain description from the spec. At the end, instead of rebooting, it writes and launches a detached `systemd-run --unit=mac-setup-handoff` script that: persists the current Wi-Fi country (`iw reg get`), writes `/etc/ssh/sshd_config.d/10-mac-setup.conf` with `PasswordAuthentication yes` and enables `ssh`, `passwd -l "$USER"`, removes `~/.ssh/authorized_keys`, `~/.bash_history` and the install log, creates `/var/lib/mac-setup/needs-password`, deletes every 802-11-wireless NetworkManager profile and any netplan Wi-Fi YAML, touches `/etc/cloud/cloud-init.disabled`, removes `/var/lib/cloud`, `/boot/firmware/user-data` and `/boot/firmware/network-config`, then `poweroff`.
- `VERSION` → `1.7.0`.

- [ ] **Step 1: Make the edits.**
- [ ] **Step 2: Verify syntax**: `bash -n setup.sh` → no output; `shellcheck setup.sh` if installed → no new warnings compared with `main`.
- [ ] **Step 3: Verify the heredocs**: extract the launcher and `mac-preflight` heredocs to temp files and `bash -n` each.
- [ ] **Step 4: Commit** `git commit -m "Installer: Wi-Fi setup service, setup screen hooks and --hotspot-setup"`

### Task 7: Docs, and the test on the real Pi

**Files:**
- Modify: `BUILD.md` ("Using it" button list: one line for the 10-second hold; Troubleshooting: "The Mac moved and can't find Wi-Fi"), `CHANGELOG.md` (1.7.0 entry, mentioning `--hotspot-setup` in one line)

- [ ] **Step 1: Docs and changelog**, commit `git commit -m "Docs: hold the left button to change Wi-Fi"`
- [ ] **Step 2: On the Pi** (needs Wells: Pi powered on and reachable, 1Password SSH agent unlocked, phone checks by hand), installing from this branch with `--branch wells/first-run-setup`, run the spec's Testing list in order. Also confirm on the Pi: the ROM checksum against the real `~/ROM`, where Imager's Wi-Fi and Wi-Fi country live on Trixie, the PSF font found, `/dev/fb0` format and `fbcon/rotate`.
- [ ] **Step 3: Fix what the Pi finds**, each fix with its test, and commit.
- [ ] **Step 4: Push and open the PR.**
