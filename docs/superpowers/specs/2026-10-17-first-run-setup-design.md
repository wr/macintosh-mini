# First-run setup: Wi-Fi from a phone, and a ROM without a terminal

Status: design, awaiting approval
Date: 2026-10-17

## Why

Once a Macintosh Mini is assembled, its SD card and the Pi's ports are inside a case held shut by stiff plastic clips. Today the only way onto Wi-Fi is to enter it in Raspberry Pi Imager before the card goes in. That's fine for someone building their own, but it rules out two things:

1. **Selling prebuilt Macs.** Wells can't know a buyer's Wi-Fi, and can't ship a ROM (Apple's copyright). A buyer needs to get the Mac onto their Wi-Fi and add a ROM with no keyboard and no terminal.
2. **Moving house.** A finished Mac that can't find a known network has no way to learn a new one without the optional back USB port, or opening the case.

## Who it's for

- **Buyers of a prebuilt Mac.** Comfortable with phones and computers, not necessarily with a terminal. They should never need one.
- **DIYers.** They flash their own card and normally enter Wi-Fi in Imager, as today. For them the hotspot is a fallback for when they move or change routers.

## Goals

- A buyer goes from "turned it on for the first time" to "Mac OS with the startup chime" using only their phone and, for the ROM, a phone or computer on their home Wi-Fi.
- Any Mac that can't find a known network at boot offers its own setup network, so a closed Mac can always be moved to a new network.
- Wells can prepare a unit for shipping with one hidden option on the normal install command, leaving none of his Wi-Fi details, passwords or keys on the card.

## Non-goals

- Changing the disk image or other settings from the web page. Owners who want to swap the disk image use the existing methods (SSH/scp, or the installer).
- SheepShaver on prebuilt units. Prebuilt Macs run Basilisk II. The hotspot works whichever emulator is installed.
- Cloning one master card to many. Wells builds and prepares each unit separately.
- Ethernet, Bluetooth or USB-based setup.

## Anti-goals (it fails if it does these, even if it works)

- Ships anything of Wells's on the card: his Wi-Fi name or password, his login password, his SSH key.
- Leaves a shared default password on shipped units, or any window where a stranger could log in.
- Takes a working Mac off a network it was happily on. A brief Wi-Fi outage (router restart) must not leave the Mac stuck as a hotspot.
- Hosts, bundles or automatically downloads a ROM.
- Confuses DIYers running the normal install command (no new prompts or visible flags for the ship option).

## What the buyer does

1. **Turn it on.** The Mac can't find a known network and has no ROM, so instead of Mac OS its screen shows a setup screen: "On your phone, join the Wi-Fi network **Macintosh Mini**", with a QR code that joins that network in one scan.
2. **The setup page pops up** on the phone by itself, the way hotel Wi-Fi does. It asks for:
   - their home Wi-Fi network (picked from a list of nearby networks, or typed in for a hidden one) and its password
   - a new password for the Mac, typed twice
3. **Tap Connect.** The page says "Connecting… look at your Mac's screen", then the Mac drops its own network and joins theirs. The phone goes back to their home Wi-Fi on its own.
   - If it joins: the screen changes to "Almost done: on a phone or computer on your Wi-Fi, open **macintosh-mini.local**", with the Mac's IP address underneath as a fallback. (The screen always shows the Mac's real name; on shipped units that's `macintosh-mini`.)
   - If it can't (wrong password, network out of range): it brings its own network back within about a minute and the screen says "Couldn't join *Network*. Join **Macintosh Mini** again to try once more." The page then shows the same error.
4. **Add a ROM** on the second page, at `macintosh-mini.local`. The page explains that a ROM is needed and links to a guide, in this wording (agreed):

   > Need a ROM? [Redundant Robot's emulator guide](https://www.redundantrobot.com/sheepshaver) explains which one to use and where to find it. The Performa ROM works best.

   The buyer either uploads the file they downloaded, or pastes its download link and the Mac fetches it. Either way the page takes the file as downloaded: a `.zip` is opened and the ROM pulled out of it.
5. **The Mac checks the ROM** (right size, a known-good 68k ROM for Basilisk II) and, if it's good, saves it and restarts into Mac OS with the chime. If not, the page says what's wrong in plain words ("That's a PowerPC ROM; this Mac needs a 68k one like the Performa ROM").

## What a DIYer sees

Nothing new, until a boot where no known network turns up. Then, with Mac OS running as usual on the screen, the Mac quietly offers the **Macintosh Mini** network. Joining it from a phone opens the same setup page, asking only for the Wi-Fi (no password step, because the owner already has one). The build guide's troubleshooting section tells them this exists.

A DIY Mac with no ROM also shows the "open *its-name*.local to add a ROM" screen, in place of today's console message, once it's on a network.

## Prepare to ship

A hidden option on the normal install command, for Wells only:

```bash
curl -fsSL https://raw.githubusercontent.com/wr/macintosh-mini/main/setup.sh | bash -s -- --ship
```

It isn't listed in the installer's usage text or the build guide (agreed), so normal users never see it. Wells runs it over SSH on his own Wi-Fi, on a unit flashed with Imager in the usual way, with the disk image he ships in the home folder and no ROM.

It runs the normal install with these differences:

- **Basilisk II and the Maclock hardware by default.** With no emulator option given, `--ship` means `--all-basilisk`. Shipped units use the installer's default model (Quadra, `modelid 14`), which the Performa ROM boots.
- **No ROM needed.** The usual check that stops the installer without a ROM is skipped. A disk image is still required.
- **SSH stays on, with password login allowed,** so the password the buyer sets is useful for SSH and copying files (the way to swap the disk image). Wells's key is removed below, so the buyer's password is the only way in.
- **Then it clears everything of Wells's off the card:**
  - every saved Wi-Fi network, wherever Pi OS keeps it (NetworkManager's files, and netplan's if Imager's Wi-Fi landed there; the builder checks on the Pi)
  - the Imager/cloud-init files on the boot partition that hold his Wi-Fi password and login (`network-config`, `user-data`), so cloud-init can't put them back. Whatever Wi-Fi country those files set must survive (see time zone and country below).
  - his SSH key (`~/.ssh/authorized_keys`), shell history and the install log
- **It locks the login password,** so nobody can log in until the buyer sets one in the setup page.
- **It marks the unit as needing first-run setup,** which is what makes the setup page ask for a password.
- **It shuts the Pi down** instead of restarting, so it's ready to box. Wells's SSH session drops at this point, which is expected.

Our call (Claude): `--ship` sets the hostname to `macintosh-mini` (unless `--hostname` says otherwise), so every buyer's address is `macintosh-mini.local`. The username can't easily be changed after the fact, so units meant for sale are flashed with a generic one (`mac`), and `--ship` warns, and asks before carrying on, if the username is anything else.

## How it fits into what's there

Today, at boot, tty1 logs in automatically, `~/.profile` runs the emulator launcher (`basilisk.sh` or `sheepshaver.sh`), and the launcher runs `mac-preflight`. If the ROM or disk is missing, `mac-preflight` prints a message on the console and the launcher drops to a shell. The new pieces hook in there:

1. **A setup service** (`mac-setup`, Python standard library only, a systemd unit like the existing button and brightness helpers). It owns the state: is there a known network, is a ROM installed, does the unit need a password. It runs the hotspot, serves both web pages, and writes a small status file the setup screen reads.
2. **The hotspot and pop-up page.**
   - The hotspot is a NetworkManager access-point connection named **Macintosh Mini**, open (no password), using NetworkManager's built-in shared mode for addresses.
   - Every web address a phone asks for points back to the Mac, and the page answers the iPhone and Android "is there internet?" checks so the phone shows the pop-up by itself.
   - Nearby networks are scanned before the hotspot starts, because the Pi Zero 2 W's radio can't reliably scan while it's running its own network. The page also offers "type a network name" for hidden networks.
3. **When the hotspot appears.** About 90 seconds after boot, if no saved network has connected, the hotspot starts. It stays up while a phone is connected to it, so nobody is cut off mid-setup. Once it has sat with nobody connected for a few minutes, it stops, tries the saved networks again, and repeats. So a Mac that booted during a router restart rejoins within a few minutes of the router coming back. Once the Mac is on a network, the hotspot never starts by itself until the next boot.
4. **The setup screen.** When the unit has no ROM, the launcher shows the setup screen in place of today's `mac-preflight` message and keeps it updated as the status file changes ("join Macintosh Mini" → "connecting" → "open macintosh-mini.local" → "couldn't join"). When the ROM arrives, the setup service restarts tty1 (what `macintosh` does), and the normal boot runs: chime, Mac OS.
5. **The ROM page** runs on the home network only while no working ROM is installed. There's no permanent settings page (non-goal).
   - The check depends on what's installed: a 68k ROM from the known-good list for Basilisk II (only ROMs that boot with the installed model), the 4 MB PowerPC ROM for SheepShaver.
   - "Working" means Mac OS actually started: the page stays available until the emulator has run for about a minute. If the emulator quits in that first minute, the launcher moves the ROM aside and goes back to the setup screen with "That ROM didn't start the Mac. Try another." A buyer with no keyboard is never stuck with a bad ROM.
6. **Time zone and Wi-Fi country.** A shipped unit carries Wells's time zone and Wi-Fi country (US). When the buyer submits the pop-up page, it also sends the phone's time zone (the browser knows it). The Mac sets its own time zone from it (for the clock and night dimming) and its Wi-Fi country from that zone, before joining the buyer's network. Edge case, acceptable: a router on a channel the US doesn't allow (12 or 13) won't appear in the list scanned under US rules, but typing its name still works once the country is set.
7. **Installer changes** (`setup.sh`):
   - Install the setup service and its unit for every install, with a `--no-setup-hotspot` option to leave it out (listed in the usage text, like the other options; default on). Idempotent, like every other step.
   - Keep `avahi-daemon` running when the setup service is installed, because it answers the `.local` names. Today the performance option masks it; drop it from that list (and unmask it on updates) when the setup service is on.
   - Add the hidden `--ship` option above.
   - Add any packages it needs to `APT_PKGS` (likely `qrencode` for the QR code; the builder confirms NetworkManager's shared mode works with what Pi OS ships).
   - Bump `VERSION` and add a CHANGELOG entry.

## Constraints

- **Pi Zero 2 W radio:** one job at a time. It's either the hotspot or joined to a network, never both. Every step of the flow assumes the phone loses the pop-up when the Mac switches networks.
- **No internet on the hotspot.** The pop-up page and everything it loads (styles, fonts, images, scripts) are served by the Mac. Nothing comes from the web.
- **Phone pop-up browsers are limited.** iOS's pop-up sheet can't download files and closes when the network goes away. The pop-up page never asks for a file, and shows its last message before the Mac switches over.
- **The screen** is 640×480 landscape on a 2.8-inch panel, rotated by the panel orientation (see the display notes in `setup.sh`). The console honours that rotation; anything drawn straight to the framebuffer doesn't, and has to be rotated by whoever draws it. The text and QR code have to be readable at arm's length.
- **Low memory and CPU:** the service must stay small while Mac OS is running, since on DIY units it sits idle alongside the emulator.
- **Must not disturb** the emulator, the button and dial services, or the tty1 autologin chain. Restarting NetworkManager drops Wi-Fi, so the service never does that.
- **The installer stays re-runnable:** a second run changes nothing, and an update keeps the owner's saved networks and password.

## Security

- **No default password, ever.** Shipped units have the login locked until the buyer sets one. The setup page refuses to continue without it.
- **The hotspot is open, everywhere (Wells's call: simplest).** Accepted risk: anyone in radio range during the minute or two of setup could capture the home Wi-Fi password and the new Mac password as they're typed, since a pop-up page can't use HTTPS. Someone nearby could also join and change which network the Mac uses. The hotspot only exists while the Mac has no network, which keeps that window short. A locked hotspot (password on the setup screen and in the QR code) was considered and set aside; it would only have covered units showing the setup screen.
- **The ROM page** is unauthenticated, but only accepts a ROM-sized file, only while no ROM is installed, and only from the home network. It never runs anything it's given.
- **Password changes** go through `chpasswd`; nothing is logged with secrets in it. Wi-Fi passwords are stored only by NetworkManager.

## Decided by Wells

- Two kinds of owner: DIYers (Wi-Fi in Imager, hotspot as fallback) and buyers of prebuilt units (no keyboard).
- The whole buyer setup should happen without a terminal, using the phone's setup pop-up.
- Prebuilt units ship with a disk image the buyer can swap later, and no ROM.
- The page points buyers to a ROM using the softer wording above, linking Redundant Robot's guide page (not the file). The ROM is added on a second page after the Mac joins their Wi-Fi.
- Prepare-to-ship is a hidden option on the normal install command.
- The setup hotspot is open (no password) on every unit.

## Our calls (Claude), for Wells to check

- The Mac password is required on shipped units, and skipped on units that already have one.
- `--ship` keeps SSH on with password login, defaults to Basilisk II + Maclock, and sets the hostname to `macintosh-mini`.
- The setup page sets the Mac's time zone and Wi-Fi country from the phone's time zone.
- A ROM only counts once Mac OS has run for a minute; one that fails sends the Mac back to the setup screen.
- `avahi-daemon` stays on whenever the setup service is installed, even with the performance option.
- Hotspot name **Macintosh Mini**, appearing about 90 seconds after boot with no known network, held while a phone is connected, retrying saved networks after a few idle minutes.
- The setup service is installed by default for everyone, with `--no-setup-hotspot` to leave it out.
- The ROM page stops once a ROM is installed; no permanent settings page.
- The link to Redundant Robot's guide lives in the page in the public repo, as one constant, since it points to a guide and not a file.
- Generic username `mac` and hostname `macintosh-mini` for units meant for sale.
- Python standard library for the service, matching the existing helpers, with unit tests in the same style as `test_brightness_control.py`.

## Left to the builder

- How the setup screen is drawn: console text with a larger font and a `qrencode` QR code, or an image. Whatever is readable and doesn't flash.
- The look of the two pages. Large tap targets, work in iOS and Android pop-up browsers, no outside resources. A classic-Mac feel is welcome if it costs little.
- The exact captive-portal answers for iOS, Android and macOS checks, and the DNS setup that sends every name to the Mac.
- The known-good ROM list and how it's checked (size plus the checksum in the ROM's first four bytes is enough).
- File names, the status file format, timeouts within the ranges above.

## Testing

- **Unit tests** for the parts that don't need hardware: ROM checking (sizes, checksums, PowerPC ROM rejected, zip with the ROM inside, zip with junk), form handling, the hotspot timing decisions.
- **On the real Pi** (wells@10.0.1.111). The builder covers what it can from a laptop: joining the hotspot, requesting the captive-portal check addresses, submitting the forms. The iPhone and Android pop-up checks are Wells's to do by hand. Steps that leave the Pi unreachable if they fail (forgetting networks, `--ship`) run last, in the order below, each only once the step before it has worked.
  - Forget all networks and reboot. The hotspot appears, an iPhone and an Android phone both get the pop-up, joining the home Wi-Fi works, and a wrong password brings the hotspot back with the error.
  - Remove the ROM. The setup screen shows each stage; uploading a zip and pasting a link both work; the Mac restarts into Mac OS with the chime.
  - Restart the router while the Mac is running. It does not become a hotspot.
  - Run `--ship`. Afterwards the card has no saved networks, no `network-config` or `user-data` on the boot partition, no SSH key, a locked password, and the Pi is shut down. Boot it and run through the buyer flow end to end.
  - Re-run the normal installer on a set-up Mac. Saved networks, password and ROM are untouched.
