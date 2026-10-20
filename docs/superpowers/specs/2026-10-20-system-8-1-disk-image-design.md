# A clean Mac OS 8.1 disk image for Basilisk II: design

Written 2026-10-20 from a conversation with Wells. Calls made without him are listed at the end.

## Intent

Today, Macintosh Mini owners bring their own disk image (the README points at the BlueSCSI
library). Wells wants a ready-made Mac OS 8.1 image anyone can download. In his words, it's about:

1. a basic, known-working, clean install;
2. supporting AirWriter (`~/Projects/airwriter`), his other project: printing to a real
   ImageWriter II over AppleTalk;
3. a simple path to an After Dark desk toy;
4. a known-working configuration for Basilisk II on the Pi.

The image itself is AirWriter-, Pi- and Macintosh Mini-agnostic: nothing in it names or depends on
them, so it works in any Basilisk II. The Mini's setup script offers it. (Reframed by Wells on
2026-10-20, after the first draft leaned on the Mini.)

It is a public download. Mac OS 8.1, After Dark and the other software are abandonware, not
freely licensed; Wells has accepted that, as is common practice.

## Goals

- An HFS disk image that boots Mac OS 8.1 on the Mini's default setup: Basilisk II as a Quadra
  (`modelid 14`), 640×480, 64 or 128 MB RAM, `ether slirp`, at the colour depths `setup.sh`
  offers (see Settings).
- On first boot, with no setup dialogs and no configuration: the browser reaches the web, the
  Chooser finds any AppleTalk ImageWriter on the network (AirWriter included), and After Dark
  starts after 5 minutes idle.
- Two ways to get it: a download link in the docs, and `setup.sh` offering to download it when
  the Pi has no disk image.
- Printing works out of the box on a Mini: `setup.sh` builds Basilisk II with the AppleTalk-only
  tunnel and turns it on (see Emulator).

## What's on the disk

| Item | Version | Notes |
|---|---|---|
| Mac OS 8.1 | retail CD | archive.org item `mac-os-8.1`, `MacOS-8.1.iso`, MD5 `c1fdf24a0aa911aa3110c9c0d34ac4d1` (downloaded and checked 2026-10-20). Installed for a 68040 Quadra. |
| AppleTalk ImageWriter | from the ImageWriter II/LQ LocalTalk Option disk | `https://old.mac.gdn/apps/iw_0.sit` (Wells's source; a StuffIt archive holding an 800K floppy image). Proven on the test Pi: Chooser listed AirWriter's "ImageWriter II" and a page printed. |
| After Dark | 4.0.3 | Earlier 4.0.x doesn't work on Mac OS 8. Randomizer module active, 5-minute delay, only modules that pass testing on the Pi (see Testing). |
| Web browser | iCab 2.9.9 (68k build) | Desktop alias. If iCab nags at launch or misbehaves in testing, use Internet Explorer 4.01 instead. Not Netscape: the copy on the test disk failed on some pages and once froze the Mac. |
| SimpleText | ships with 8.1 | Desktop alias. |
| MR Browser | latest 68K build (not the sys6 build) | Macintosh Repository's own client. Desktop alias. It asks for a sign-in PIN when opened (not at startup); kept at Wells's request. |
| FrogFind | — | Desktop item that opens the site in the browser. |
| StuffIt Expander | 5.5 | So downloads open. |
| Disk Copy | 6.3.3 | So downloaded disk images open. |

Sources for everything after the first two rows aren't pinned yet: the builder finds each one
(Macintosh Garden, Macintosh Repository, archive.org) and pins it. Where a site gives no stable
direct URL, the file goes in a local sources folder kept outside git, and a checksum manifest in
the repo lists every file; the build checks them. All rows are wanted. If an item can't be found
in a version without a serial-number or registration prompt, swap it for an equivalent (as with
iCab and Internet Explorer) rather than ship the prompt. The test disk on the Pi already has
After Dark (version unknown); check it, it may be a usable source.

## Settings in the image

- TCP/IP: Ethernet, using DHCP (slirp hands out 10.0.2.x). The test disk had a hand-set LAN
  address, which is why its web was broken under slirp.
- AppleTalk: active, on Ethernet. The Chooser has no printer selected: each AirWriter has its own
  name, so the user picks it once.
- The browser's home page is a small, unbranded local start page on the disk with links to
  FrogFind, 68k.news and Macintosh Repository, so a first launch never lands on an error.
  FrogFind was down for hours on 2026-10-20.
- The Mac is named "Macintosh". File Sharing is off. Virtual memory is off.
- Extensions that do nothing in the emulator are turned off for a faster boot.
- No first-boot assistants, registration or "Welcome" dialogs.
- Colour depth: `setup.sh` offers Color (16-bit), Grayscale (8-bit, the Basilisk II default)
  and Black & White (1-bit). The image must look right and pass testing at 16-bit and 8-bit,
  and the After Dark module list keeps only modules that pass at both. 1-bit is best effort.
  Grays versus colours at 8-bit come from the Monitors setting, which lives in the emulator's
  PRAM file, not on the disk.

## Delivery

- **Host:** an Internet Archive item, `macos-8.1-basilisk-ii`, titled "Mac OS 8.1 for Basilisk II
  (clean install)", holding a zip of the raw image (`.hda`, which `setup.sh`
  already discovers) and its SHA-256. Not GitHub releases: a takedown there can hit the whole
  repo. The image is versioned by date (e.g. 2026.10); a new version is a new file, so a pinned
  checksum never goes stale.
- **Upload:** Wells signs the Internet Archive's `ia` command-line tool (installed with Homebrew)
  in to his account on his Mac once, with `ia configure`. After that the builder uploads each
  version with `ia` and verifies a real download before pinning it. The builder never handles
  his password.
- **Docs:** the README stays a landing page. Its Step 2 gains a short "or download ours" link.
  Details (what's on it, how to use it) go in `BUILD.md` or a page linked from it.
- **`setup.sh`:** on an install that finds no disk image in `$HOME`, it offers to download this one
  (showing the size), checks the SHA-256, unzips it and carries on. It never touches an existing
  disk image. URL and checksum are pinned in `setup.sh` per image version. The offer only makes
  sense for Basilisk II as a Quadra; SheepShaver installs don't get it.
- **Order:** the emulator change (below) is independent and can merge first. The download offer
  merges only once the Internet Archive item is live and a real download has passed the test.
  Until then it's tested against a local copy.

## Emulator (`setup.sh`)

Printing needs two changes to Basilisk II, both written and tested end to end on 2026-10-20 and
posted upstream:

- `kanjitalk755/macemu#321`: the tunnel took 127.0.1.1 as the Pi's address (Raspberry Pi OS maps
  the host name there), so nothing on the network could reply to the Mac.
- `kanjitalk755/macemu#322`: new pref `udpappletalkonly`. AppleTalk goes through the UDP tunnel
  (which AirWriter listens to on port 6066) and everything else through `ether slirp`, so the Mac
  prints and browses at the same time.

Until both merge, `setup.sh` builds from `wr/macemu` at a pinned commit of the
`udptunnel-appletalk-only` branch instead of kanjitalk755 HEAD. Once merged, it pins kanjitalk755
at the merge. Existing installs rebuild once to pick it up.

New Basilisk II installs get `udptunnel true`, `udpport 6066` and `udpappletalkonly true` with
`ether slirp`. Existing installs keep their prefs: Edit settings has an "AppleTalk" row (On:
"AppleTalk printers and file sharing on your network, plus the internet"; Off: "The internet
only"), and nothing changes silently. SheepShaver has no tunnel and is unchanged.

## Non-goals

- Infinite HD as an optional second disk. Wanted later (see Later), not now.
- MacWrite, MacPaint and games. Dropped from the image in favour of Infinite HD later.
- SheepShaver. Not tested and not promised: a disk installed for a 68k Quadra may not boot there.
- HTTPS sites. The browsers can't do modern TLS.
- ROMs. The user still supplies their own.
- Real BlueSCSI hardware as a target.

## Anti-goals

- Anything on the disk that can crash or hang the Mac on the Pi, above all an After Dark module
  that takes the Mac down while nobody's watching.
- `setup.sh` replacing, rewriting or silently reconfiguring someone's existing disk or prefs.
- Nag screens, registration prompts or setup assistants at startup.
- The image, or any third-party file from it, committed to the repo.
- Anything in the image that names or depends on the Macintosh Mini, the Pi or AirWriter.

## Constraints

- 68k Macs can't start up from HFS+ (Mac OS Extended), so the volume is HFS (Mac OS Standard).
  1 GB: room for downloads, and 16 KB allocation blocks.
- Pi Zero 2 W: 416 MB usable RAM. Heavy After Dark modules or QuickTime can crawl.
- Repo conventions: build steps are scripted and repeatable from pinned sources (like the
  AirWriter enclosure and the KiCad scripts here). Every downloaded source is pinned by URL and
  checksum. Build scripts are GPL-3.0-or-later and docs CC BY-SA, with `REUSE.toml` entries for
  any third-party file. The image's contents are third-party and not covered.
- Copy that users see (the start page, `setup.sh` prompts) is shown to Wells before it's committed.

## Testing: what has to pass

On the test Pi (`wells@10.0.1.111`, `macintosh-mini-c915`) after a fresh `setup.sh` run, with
AirWriter board 1 on the network (10.0.1.115):

- With no disk in `$HOME`, `setup.sh` offers the download, the checksum passes, and the Mac boots
  to the Finder with no dialogs. Repeated in both colour modes.
- The browser opens the start page and loads 68k.news and FrogFind (when FrogFind is up).
- MR Browser connects and downloads a file, and StuffIt Expander opens it. Disk Copy mounts an
  `.img`.
- The Chooser shows AirWriter's "ImageWriter II" under AppleTalk ImageWriter, and a page prints
  while the browser is in use.
- After Dark starts after 5 minutes idle, cycles modules, and survives an hour's soak without a
  hang; moving the mouse wakes it.
- Re-running `setup.sh` on an existing install keeps its disk and prefs.

The test Pi can be driven remotely (wayvnc and vncdotool; notes in Claude's project memory).

**Build environment.** The scripted parts (fetching sources, packing them onto a transfer disk,
checking and zipping the result) run on Wells's Mac. The one-time install and configuration run
inside Basilisk II on the test Pi, driven over VNC: that is the exact target, it uses the Pi's own
ROM (`~/68K.ROM`), and it doesn't take over Wells's screen the way driving the emulator on his Mac
would. Only that ROM is tested. The Mac OS 8.1 CD image was downloaded on 2026-10-20 to the
session scratchpad; re-fetch it from archive.org and check the MD5 if it's gone.

## Left to the builder

- How to make the base install (a one-time Mac OS 8.1 install in Basilisk II on the Mac is the
  likely route) and how to add the rest: host-side tools such as `machfs` or `hfsutils`, steps
  inside the emulator, or both. It must be repeatable from the scripts and written steps.
- The final After Dark module list, from testing on the Pi.
- How the FrogFind and 68k.news desktop items work (Internet location file, AppleScript applet,
  or an HTML page), as long as a double-click opens the site in the browser.
- The start page's contents, for Wells to approve.
- Zip and file naming, Internet Archive metadata, and the versioning scheme.
- The `setup.sh` prompt flow and any new flags.

## Calls made without Wells (his to overturn)

- A 1 GB HFS volume.
- A local start page as the browser's home page, rather than FrogFind.
- iCab first, Internet Explorer 4.01 as the fallback.
- Only the AppleTalk ImageWriter driver, not the LQ one.
- Disk Copy 6.3.3.
- File Sharing and virtual memory off; idle extensions off.
- The AppleTalk-only tunnel on by default for new Basilisk II installs, offered (not forced) on
  existing ones.
- Testing at 16-bit and 8-bit, with 1-bit best effort.
- Installing and configuring the image on the test Pi over VNC, with its ROM; scripts on the Mac.
- The emulator change merging before the download offer.

## Later

- Infinite HD as an optional second disk: built with Infinite Mac's open-source script (its Mac OS
  7–8 variant is a 2 GB volume with MacWrite, MacPaint, Bolo, Glider and about 250 more titles),
  hosted beside this image, offered by `setup.sh`, attached as a second drive, and pre-indexed so
  the first mount is quick. Give Mihai Parparita a heads-up before it goes public.
- A proxy on the Pi so the browser can reach HTTPS sites.
- SheepShaver.
