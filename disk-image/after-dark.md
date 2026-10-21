# After Dark on the disk image

The image runs the After Dark 4.03 control panel with the original modules: After Dark 2.0
(1990–92) and the More After Dark add-on (1991–93). Wells preferred them to the After Dark 4.0
set, which isn't installed. The 4.03 panel runs the 2.0 modules as they are, under an
"After Dark 2.0" group, so the 2.0 control panel isn't needed.

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
| FadeAway | ✗ | ✓ | Dims the screen; does nothing at 16-bit. |
| Fish! | ✓ | ✓ | |
| Flying Toasters | ✓ | ✓ | |
| Hard Rain | ✓ | ✓ | |
| Lissajous | ✓ | ✓ | |
| Logo | ✓ | ✓ | Floating Berkeley Systems logo. |
| Messages | ✓ | ✓ | |
| MultiModule | — | — | Not installed: plays one saved combination, and its default needs 256 colours. The 4.03 panel has its own MultiModules. |
| NightLines | ✓ | ✓ | |
| PICS Player | ✓ | ✓ | Plays the bundled rotating cube. |
| Picture Frame | ✓ | ✓ | |
| Puzzle | ✓ | ✓ | |
| Rainstorm | ✓ | ✓ | |
| Randomizer | — | — | Not installed: the 4.03 panel's Randomizer does the job. |
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

## Found along the way

- A `Display Preferences` file in the System Folder makes Mac OS restore the colour depth it was
  saved at on every boot, overriding the depth Basilisk II is set to. It mustn't be on the image;
  `check_image.py` fails if it is.
- At 16-bit, a module that needs 256 colours shows its message over a starry skyline instead of
  drawing. It doesn't hang, and moving the mouse still wakes the Mac.
