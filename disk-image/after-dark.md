# After Dark on the disk image

The image runs After Dark 2.0w: its own control panel, with the original modules from After Dark
2.0 (1990–92) and the More After Dark add-on (1991–93) together in `After Dark Files`. The
Randomizer plays every module in random order, 5 minutes each, after 5 minutes idle, with the sound
off and no sleep corners.

## Why not After Dark 4.03

The first build used the After Dark 4.03 control panel. Its Demo button, and a sleep while the
panel was open, ran any module, 2.0 or 4.0. But on a real idle start with the panel closed, it only
ever showed its built-in Starry Night: the Randomizer, a single 2.0 module (Flying Toasters) and a
single 4.0 module (Time Flies) all fell back to it. Putting back the 4.0 shared library and
faceplate didn't help. A 68kMLA thread on Mac OS 8.1 reports the same: After Dark 4 doesn't work
under Mac OS 8 or 8.1 on 68k Macs. The 2.0w control panel, on the same disk, runs Flying Toasters
and the Randomizer on a real idle start.

The module results below were measured in the 4.03 control panel, which runs 2.0 modules as
they are. The 2.0 control panel runs the same module files.

Seven modules need 256 colours: FadeAway, Satori, Supernova and Vertigo (2.0) and Globe, Lunatic
Fringe and Ripple (More After Dark). They're kept (Wells, 2026-10-21): at 8-bit, the Basilisk II
default, they work; at 16-bit, when the Randomizer picks one, its turn shows a "needs 256 colours"
note over a starry sky, except FadeAway, which only dims the screen and so leaves the desktop
showing for its turn.

## How they were tested

On the test Pi (Raspberry Pi Zero 2 W, Basilisk II as a Quadra, 128 MB, 640×480), 2026-10-21,
each module ran for about 75 seconds at 16-bit (Thousands) and at 8-bit (256 colours): put to
sleep from a sleep-now corner, looked at after 25 seconds and again 50 seconds later, then woken
with the mouse. A module passes when it draws, keeps moving and wakes back to the desktop.

Every module woke cleanly, at both depths. None hung the Mac.

Basilisk II build: macemu b9a71d7a (the installer's prebuilt-binaries branch).

## After Dark 2.0

| Module | 16-bit | 8-bit | Notes |
|---|---|---|---|
| Bouncing Ball | ✓ | ✓ | |
| Can of Worms | ✓ | ✓ | Worms crawl over the desktop. |
| Clock | ✓ | ✓ | |
| Doodles | ✓ | ✓ | |
| Down the Drain | ✓ | ✓ | |
| FadeAway | ✗ | ✓ | Dims the screen; at 16-bit the desktop stays showing for its turn. |
| Fish! | ✓ | ✓ | |
| Flying Toasters | ✓ | ✓ | |
| Hard Rain | ✓ | ✓ | |
| Lissajous | ✓ | ✓ | |
| Logo | ✓ | ✓ | Floating Berkeley Systems logo. |
| Messages | ✓ | ✓ | |
| MultiModule | — | — | Not installed: plays one saved combination, and its default needs 256 colours. |
| NightLines | ✓ | ✓ | |
| PICS Player | ✓ | ✓ | Plays the bundled rotating cube. |
| Picture Frame | ✓ | ✓ | |
| Puzzle | ✓ | ✓ | |
| Rainstorm | ✓ | ✓ | |
| Randomizer | ✓ | ✓ | Runs the rest; checked on a real idle start with the 2.0 panel. |
| Rose | ✓ | ✓ | |
| Satori | ✗ | ✓ | "Requires a monitor in 256 colors/grays mode." |
| Shapes | ✓ | ✓ | |
| Slide Show | ✓ | ✓ | Shows the bundled After Dark and Berkeley Systems pictures. |
| Spheres | ✓ | ✓ | |
| Spotlight | ✓ | ✓ | |
| Starry Skyline | ✓ | ✓ | |
| String Theory | ✓ | ✓ | |
| Supernova | ✗ | ✓ | "Works only in 256 colors/grays." |
| Vertigo | ✗ | ✓ | "Works only in 256 colors." |
| Warp! | ✓ | ✓ | |
| Zot! | ✓ | ✓ | Lightning bolts between dark pauses. |

## More After Dark

| Module | 16-bit | 8-bit | Notes |
|---|---|---|---|
| Boris | ✓ | ✓ | |
| Confetti Factory | ✓ | ✓ | |
| Dominoes | ✓ | ✓ | |
| GeoBounce | ✓ | ✓ | |
| Globe | ✗ | ✓ | "Requires an 8, 4 or 1-bit monitor." |
| GraphStat | ✓ | ✓ | |
| Gravity | ✓ | ✓ | |
| Life II | ✓ | ✓ | |
| Lunatic Fringe | ✗ | ✓ | "No 8-bit or 1-bit monitor found." A game: shows its attract screen. |
| Mandelbrot | ✓ | ✓ | |
| Meadow | ✓ | ✓ | |
| Modern Art | ✓ | ✓ | |
| Mountains | ✓ | ✓ | |
| Mowin' Man | ✓ | ✓ | |
| Nocturnes | ✓ | ✓ | |
| Punchout | ✓ | ✓ | |
| Rain | ✓ | ✓ | Faint at its default "Drizzle". |
| Ripple | ✗ | ✓ | "Requires a monitor set to 2 or 256 colors." |
| Say What? | ✓ | ✓ | |
| Snake | ✓ | ✓ | |
| Spiral Gyra | ✓ | ✓ | |
| Stained Glass | ✓ | ✓ | |
| String Art | ✓ | ✓ | |
| Terraform | ✓ | ✓ | |
| Tunnel | ✓ | ✓ | |
| Virex-D | ✓ | ✓ | A mock virus scan of the disks (an ad for Virex). |

`MAD Fish!` in the add-on isn't a module: it's extra fish data with no file type, which nothing
loads. It isn't installed.

## Soak

An hour idle at 8-bit with the image's settings (2026-10-21, Randomizer, 5 minutes each): After
Dark started at 5 minutes and changed module every 5 minutes (Nocturnes, Stained Glass, Fish!,
Slide Show, Vertigo, Warp!, Virex-D and more). Half-way through, AirWriter's AppleTalk test peer
found the Mac by name and got 5 of 5 echo replies. After the hour, moving the mouse woke it to the
desktop and the Apple menu opened. Without Clear Screen, some modules (Nocturnes, Stained Glass)
drew on a white screen left by the module before; the image has Clear Screen on.

The same hour at 16-bit (same day): modules changed every 5 minutes, AppleTalk answered 5 of 5
half-way, and the Mac woke to the desktop afterwards. One turn showed the desktop: FadeAway, as
above.

In a Demo (not in real sleep), Lunatic Fringe says it doesn't run in Demo mode, and Down the
Drain can refuse to start from a Randomizer Demo; both run in real sleep.

## Found along the way

- A `Display Preferences` file in the System Folder makes Mac OS restore the colour depth it was
  saved at on every boot, overriding the depth Basilisk II is set to. It mustn't be on the image;
  `check_image.py` fails if it is.
- At 16-bit, a module that needs 256 colours shows its message over a starry skyline instead of
  drawing. It doesn't hang, and moving the mouse still wakes the Mac.
