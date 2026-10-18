# First-run setup: Wi-Fi from a phone, and a ROM without a terminal

Status: approved and built (PR #41); see "Changes after testing" at the end
Date: 2026-10-17

## Why

Once a Macintosh Mini is assembled, its SD card and the Pi's ports are inside a case held shut by stiff plastic clips. Today the only way onto Wi-Fi is to enter it in Raspberry Pi Imager before the card goes in. That's fine for someone building their own, but it rules out two things:

1. **Setting up a Mac for someone else** (selling one prebuilt, or giving one as a gift). Whoever prepares it can't know the new owner's Wi-Fi, and can't include a ROM (Apple's copyright). The new owner needs to get the Mac onto their Wi-Fi and add a ROM with no keyboard and no terminal.
2. **Moving house.** A finished Mac has no way to learn a new network without the optional back USB port, or opening the case.

## Who it's for

- **New owners of a Mac someone else prepared.** Comfortable with phones and computers, not necessarily with a terminal. They should never need one.
- **DIYers.** They flash their own card and normally enter Wi-Fi in Imager, as today. For them the button-triggered hotspot is how they change networks later.

## Goals

- A new owner goes from "turned it on for the first time" to "Mac OS with the startup chime" using only their phone and, for the ROM, a phone or computer on their home Wi-Fi.
- Any Mac can be moved to a new network without opening the case: hold the left button for about 10 seconds and it offers its own setup network.
- Anyone can prepare a Mac for phone setup with one option on the normal install command, leaving none of their own Wi-Fi details, passwords or keys on the card.

## Non-goals

- Changing the disk image or other settings from the web page. Owners who want to swap the disk image use the existing methods (SSH/scp, or the installer).
- SheepShaver as the default for prepared Macs. They get Basilisk II unless told otherwise. The hotspot works whichever emulator is installed.
- Cloning one master card to many. Each Mac is prepared separately.
- Ethernet, Bluetooth or USB-based setup.
- Guessing when to offer the hotspot on a Mac that already has saved networks (say, after a few minutes without a connection). The button does that job.

## Anti-goals (it fails if it does these, even if it works)

- Leaves anything of the person who prepared the card on it: their Wi-Fi name or password, their login password, their SSH key.
- Leaves a shared default password on prepared Macs, or any window where a stranger could log in.
- Starts the hotspot by itself on a Mac that has a saved network. A router restart must never leave a working Mac stuck as a hotspot.
- Hosts, bundles or automatically downloads a ROM.
- Adds prompts or steps to the normal install.

## What the new owner does

1. **Turn it on.** The Mac has no saved network and no ROM, so instead of Mac OS its screen shows a setup screen: "On your phone, join the Wi-Fi network **Macintosh Mini 4E2A**", with a QR code that joins that network in one scan. (The four characters come from the Mac's network hardware address, so two Macs set up side by side don't get mixed up.)
2. **The setup page pops up** on the phone by itself, the way hotel Wi-Fi does. It asks for:
   - their home Wi-Fi network (picked from a list of nearby networks, or typed in for a hidden one) and its password
   - a new password for the Mac, typed twice
3. **Tap Connect.** The page says "Connecting… look at your Mac's screen", then the Mac drops its own network and joins theirs. The phone goes back to their home Wi-Fi on its own.
   - If it joins: the screen changes to "Almost done: on a phone or computer on your Wi-Fi, open **macintosh-mini-4e2a.local**", with the Mac's IP address underneath as a fallback.
   - If it can't (wrong password, network out of range): it forgets that network, brings its own network back within about a minute, and the screen says "Couldn't join *Network*. Join **Macintosh Mini 4E2A** again to try once more." The page then shows the same error.
4. **Add a ROM** on the second page, at `macintosh-mini-4e2a.local`. The page explains that a ROM is needed and links to a guide, in this wording (agreed):

   > Need a ROM? [Redundant Robot's emulator guide](https://www.redundantrobot.com/sheepshaver) explains which one to use and where to find it. The Performa ROM works best.

   The owner either uploads the file they downloaded, or pastes its download link and the Mac fetches it. Either way the page takes the file as downloaded: a `.zip` is opened and the ROM pulled out of it.
5. **The Mac checks the ROM** (right size, a known-good ROM for the installed emulator) and, if it's good, saves it and restarts into Mac OS with the chime. If not, the page says what's wrong in plain words ("That's a PowerPC ROM; this Mac needs a 68k one like the Performa ROM").

## Changing networks later (everyone)

1. **Hold the left button for about 10 seconds.** A sound plays when the hold registers, Mac OS quits, and the setup screen appears with the QR code and the **Macintosh Mini 4E2A** network name.
2. **Join it from a phone.** The same setup page pops up, asking only for the Wi-Fi (no password step, because the owner already has one).
3. **The Mac joins the new network** and goes straight back into Mac OS. The new network is added to the saved ones; the old ones stay, so the Mac still works back at the old place.
4. **Changed your mind?** Press the left button again, or leave it for about 5 minutes with nobody joining. The setup screen closes, the Mac rejoins whatever saved network it can find, and Mac OS starts again.

The left button's tap (restart Mac OS) and double-tap (quit to the command line) work as before. The right button (shut down) is untouched: holding a power button is everyone's instinct for forcing a computer off, so it must keep doing that.

This goes in the build guide as one line under the buttons, and in its troubleshooting section for a Mac that has moved.

A DIY Mac with no ROM also shows the "open *its-name*.local to add a ROM" screen, in place of today's console message, once it's on a network.

## Preparing a Mac for phone setup (`--hotspot-setup`)

An option on the normal install command:

```bash
curl -fsSL https://raw.githubusercontent.com/wr/macintosh-mini/main/setup.sh | bash -s -- --hotspot-setup
```

It's for anyone handing a Mac to someone else: a card set up for Wi-Fi from a phone instead of a network name and password saved on the card. It's listed in the installer's usage text with a plain one-line description, and in the CHANGELOG, but not in the build guide or README (agreed). Whoever prepares the Mac flashes it with Imager in the usual way, runs this over SSH on their own Wi-Fi with the disk image they want to include in the home folder and no ROM.

It runs the normal install with these differences:

- **Basilisk II and the Maclock hardware by default.** With no emulator option given, it means `--all-basilisk`. Prepared Macs use the installer's default model (Quadra, `modelid 14`), which the Performa ROM boots.
- **No ROM needed.** The usual check that stops the installer without a ROM is skipped. A disk image is still required.
- **A unique name.** The hostname becomes `macintosh-mini-` plus the last four characters of the Wi-Fi hardware address (for example `macintosh-mini-4e2a`), unless `--hostname` says otherwise. The hotspot uses the same four characters.
- **SSH stays on, with password login allowed,** so the password the new owner sets is useful for SSH and copying files (the way to swap the disk image). The preparer's key is removed below, so the new owner's password is the only way in.
- **Then it clears everything of the preparer's off the card:**
  - every saved Wi-Fi network, wherever Pi OS keeps it (NetworkManager's files, and netplan's if Imager's Wi-Fi landed there; the builder checks on the Pi)
  - the Imager/cloud-init files on the boot partition that hold their Wi-Fi password and login (`network-config`, `user-data`), so cloud-init can't put them back. Whatever Wi-Fi country those files set must survive (see time zone and country below).
  - their SSH key (`~/.ssh/authorized_keys`), shell history and the install log
- **It locks the login password,** so nobody can log in until the new owner sets one in the setup page.
- **It marks the Mac as needing first-run setup,** which is what makes the setup page ask for a password.
- **It shuts the Pi down** instead of restarting, so it's ready to box. The SSH session drops at this point, which is expected.

The username can't easily be changed after the fact, so the usage text suggests flashing with a generic one (`mac`), and `--hotspot-setup` warns, and asks before carrying on, if the username is anything else.

## How it fits into what's there

Today, at boot, tty1 logs in automatically, `~/.profile` runs the emulator launcher (`basilisk.sh` or `sheepshaver.sh`), and the launcher runs `mac-preflight`. If the ROM or disk is missing, `mac-preflight` prints a message on the console and the launcher drops to a shell. The new pieces hook in there:

1. **A setup service** (`mac-setup`, Python standard library only, a systemd unit like the existing button and brightness helpers). It owns the state: is there a saved network, is a ROM installed, does the Mac need a password, has setup been asked for by the button. It runs the hotspot, serves both web pages, and writes a small status file the setup screen reads.
2. **The hotspot and pop-up page.**
   - The hotspot is a NetworkManager access-point connection named **Macintosh Mini XXXX**, open (no password), using NetworkManager's built-in shared mode for addresses.
   - Every web address a phone asks for points back to the Mac, and the page answers the iPhone and Android "is there internet?" checks so the phone shows the pop-up by itself.
   - Nearby networks are scanned before the hotspot starts, because the Pi Zero 2 W's radio can't reliably scan while it's running its own network. The page also offers "type a network name" for hidden networks.
3. **When the hotspot appears.** Only two ways:
   - **At boot, when there are no saved networks at all** (a prepared Mac's first boot, or after a failed attempt from the setup page, which forgets the network it couldn't join). It stays up until setup succeeds.
   - **When the left button is held for about 10 seconds.** It stays up while a phone is connected, and gives up after about 5 minutes with nobody joining, or when the left button is pressed again.
4. **The button.** `button_handler.py` learns a long hold on the left button. Today its single press fires 500 ms after the press whether or not the button has been let go; it changes so a press still held at the end of that window waits for the release: let go before ~10 seconds and it's a normal restart, hold to ~10 seconds and it plays a sound and asks the setup service to start setup. The right button and the double-press are unchanged.
5. **The setup screen.** Whenever setup is running (no ROM, no saved network, or the button), the launcher shows the setup screen in place of Mac OS and keeps it updated as the status file changes ("join Macintosh Mini XXXX" → "connecting" → "open *name*.local" → "couldn't join"). When setup finishes, the setup service restarts tty1 (what `macintosh` does), and the normal boot runs: chime, Mac OS.
6. **The ROM page** runs on the home network only while no working ROM is installed. There's no permanent settings page (non-goal).
   - The check depends on what's installed: a 68k ROM from the known-good list for Basilisk II (only ROMs that boot with the installed model), the 4 MB PowerPC ROM for SheepShaver.
   - "Working" means Mac OS actually started: the page stays available until the emulator has run for about a minute. If the emulator quits in that first minute, the launcher moves the ROM aside and goes back to the setup screen with "That ROM didn't start the Mac. Try another." A new owner with no keyboard is never stuck with a bad ROM.
7. **Time zone and Wi-Fi country.** A prepared Mac carries its preparer's time zone and Wi-Fi country. When the new owner submits the pop-up page, it also sends the phone's time zone (the browser knows it). The Mac sets its own time zone from it (for the clock and night dimming) and its Wi-Fi country from that zone, before joining the new network. Edge case, acceptable: a router on a channel the old country doesn't allow won't appear in the list scanned before the change, but typing its name still works once the country is set.
8. **Installer changes** (`setup.sh`):
   - Install the setup service and its unit on every install. It does nothing unless there are no saved networks or the button asks, so there's no option to leave it out.
   - Keep `avahi-daemon` running, because it answers the `.local` names. Today the performance option masks it; drop it from that list and unmask it on updates.
   - Add the `--hotspot-setup` option above, with its line in the usage text.
   - Add any packages it needs to `APT_PKGS` (likely `qrencode` for the QR code; the builder confirms NetworkManager's shared mode works with what Pi OS ships).
   - Bump `VERSION` and add a CHANGELOG entry.

## Constraints

- **Pi Zero 2 W radio:** one job at a time. It's either the hotspot or joined to a network, never both. Every step of the flow assumes the phone loses the pop-up when the Mac switches networks.
- **No internet on the hotspot.** The pop-up page and everything it loads (styles, fonts, images, scripts) are served by the Mac. Nothing comes from the web.
- **Phone pop-up browsers are limited.** iOS's pop-up sheet can't download files and closes when the network goes away. The pop-up page never asks for a file, and shows its last message before the Mac switches over.
- **The screen** is 640×480 landscape on a 2.8-inch panel, rotated by the panel orientation (see the display notes in `setup.sh`). The console honours that rotation; anything drawn straight to the framebuffer doesn't, and has to be rotated by whoever draws it. The text and QR code have to be readable at arm's length.
- **Low memory and CPU:** the service must stay small while Mac OS is running, since it sits idle alongside the emulator on every Mac.
- **Must not disturb** the emulator, the brightness dial, or the tty1 autologin chain, and the left button's tap and double-tap must feel the same as today. Restarting NetworkManager drops Wi-Fi, so the service never does that.
- **The installer stays re-runnable:** a second run changes nothing, and an update keeps the owner's saved networks and password.

## Security

- **No default password, ever.** Prepared Macs have the login locked until the new owner sets one. The setup page refuses to continue without it.
- **The hotspot is open, everywhere (Wells's call: simplest).** Accepted risk: anyone in radio range during the minute or two of setup could capture the home Wi-Fi password and the new Mac password as they're typed, since a pop-up page can't use HTTPS. Someone nearby could also join and change which network the Mac uses. The hotspot only exists during setup, which keeps that window short. A locked hotspot (password on the setup screen and in the QR code) was considered and set aside.
- **The ROM page** is unauthenticated, but only accepts a ROM-sized file, only while no ROM is installed, and only from the home network. It never runs anything it's given.
- **Password changes** go through `chpasswd`; nothing is logged with secrets in it. Wi-Fi passwords are stored only by NetworkManager.

## Decided by Wells

- Two kinds of owner: DIYers (Wi-Fi in Imager) and new owners of a Mac someone else prepared (no keyboard).
- The whole new-owner setup should happen without a terminal, using the phone's setup pop-up.
- Prepared Macs come with a disk image the owner can swap later, and no ROM.
- The page points to a ROM using the softer wording above, linking Redundant Robot's guide page (not the file). The ROM is added on a second page after the Mac joins the new Wi-Fi.
- Preparing a card is a plainly described install option for anyone, not a hidden seller-only one. It's in the usage text, not in the guides.
- Changing networks is triggered by holding a button, not by guessing from lost connections.
- Each prepared Mac gets a unique name from its hardware address, like `macintosh-mini-4e2a`.
- The setup hotspot is open (no password) on every Mac.

## Our calls (Claude), for Wells to check

- The left button holds for setup, not the right: the right button shuts down the moment it's pressed, and holding it is the force-off instinct.
- About 10 seconds to trigger, a sound when it registers, about 5 minutes before giving up.
- The hotspot name carries the same four characters as the hostname (**Macintosh Mini 4E2A**), on every Mac, prepared or not.
- The Mac password is required on prepared Macs, and skipped on Macs that already have one.
- `--hotspot-setup` keeps SSH on with password login, defaults to Basilisk II + Maclock, and warns about a non-generic username.
- The setup page sets the Mac's time zone and Wi-Fi country from the phone's time zone.
- A ROM only counts once Mac OS has run for a minute; one that fails sends the Mac back to the setup screen.
- The setup service is on every install with no opt-out, since it's idle unless asked; `avahi-daemon` stays on even with the performance option.
- The link to Redundant Robot's guide lives in the page in the public repo, as one constant, since it points to a guide and not a file.
- The button hold gets one line in the build guide; `--hotspot-setup` doesn't.
- Python standard library for the service, matching the existing helpers, with unit tests in the same style as `test_brightness_control.py`.

## Left to the builder

- How the setup screen is drawn: console text with a larger font and a `qrencode` QR code, or an image. Whatever is readable and doesn't flash.
- The look of the two pages. Large tap targets, work in iOS and Android pop-up browsers, no outside resources. A classic-Mac feel is welcome if it costs little.
- The sound for the button hold (an existing system sound or a short new one).
- The exact captive-portal answers for iOS, Android and macOS checks, and the DNS setup that sends every name to the Mac.
- The known-good ROM list and how it's checked (size plus the checksum in the ROM's first four bytes is enough).
- File names, the status file format, exact timeouts within the ranges above.

## Testing

- **Unit tests** for the parts that don't need hardware: ROM checking (sizes, checksums, PowerPC ROM rejected, zip with the ROM inside, zip with junk), form handling, the button's tap / double-tap / hold timing, the hotspot start and give-up decisions.
- **On the real Pi** (wells@10.0.1.111). The builder covers what it can from a laptop: joining the hotspot, requesting the captive-portal check addresses, submitting the forms. The iPhone and Android pop-up checks are Wells's to do by hand. Steps that leave the Pi unreachable if they fail (forgetting networks, `--hotspot-setup`) run last, in the order below, each only once the step before it has worked.
  - Hold the left button. The sound plays, the setup screen appears, the hotspot is up; pressing the button again cancels and the Mac is back on its old network. Tap and double-tap still restart and quit as before.
  - Use the button-triggered hotspot to add a network. The Mac joins it and Mac OS comes back.
  - Remove the ROM. The setup screen shows each stage; uploading a zip and pasting a link both work; the Mac restarts into Mac OS with the chime. A ROM that passes the check but fails to boot sends it back to the setup screen.
  - Restart the router while the Mac is running. It does not become a hotspot.
  - Run `--hotspot-setup`. Afterwards the card has no saved networks, no `network-config` or `user-data` on the boot partition, no SSH key, a locked password, the new hostname, and the Pi is shut down. Boot it and run through the new-owner flow end to end, including a wrong Wi-Fi password first.
  - Re-run the normal installer on a set-up Mac. Saved networks, password and ROM are untouched.

## Changes after testing (Wells, 2026-10-17)

Tried on a Pi Zero 2 W with an iPhone. These replace the matching parts above:

- **The web server only runs during setup**: while the hotspot is up, while joining, and while the ROM step is open, until the new ROM has run for a minute. Outside setup nothing listens on port 80.
- **Sounds**: a beep when the button hold registers, a "ready" ping when the setup network is up, a rising "connected" chime, two dings when there's a step 2 (the ROM), and a low "didn't work" tone. All are tones made for this project, not Apple's sounds.
- **The Mac's setup screen** is a small classic-Mac window on a dotted desktop, titled "Macintosh Mini Setup", with "Step 1 of 2" (Wi-Fi) and "Step 2 of 2" (ROM). The network name and address are shown white on black, and step 2 starts with a ticked "Wi-Fi connected." so it can't be mistaken for step 1.
- **The ROM step's screen** shows a QR code that opens the ROM page, plus its address. It uses the IP address rather than the `.local` name, which doesn't resolve on every network (Wells's router filters it).
- **The phone page**: the network-name box only appears after picking "Other…" (straight away if nothing was found). The connecting page just says it's joining and that the setup network goes away once connected. Buttons have explicit black text, and pages ask to stay in light mode.
- **The ROM page** puts "Performa ROM" in bold.
- **Power**: on a weak supply, starting the hotspot can reset the Pi (seen twice with a poor charger, none with a good one). That's the board's existing ~4 V supply limit, not something setup can fix.
