# Macintosh Mini USB port jig

3D-printable guide for cutting the optional USB-A port into the Maclock's back shell with a Dremel in its router base. It puts a 7 × 14mm hole in the top right of the back, 38mm above the USB-C port and in line with it, with straight sides every time. The port is in the [build guide](https://wells.ee/projects/macintosh-mini/).

The router base's round foot slides inside the jig's walls. Pushing it against each wall in turn runs the bit along each side of the hole. A small key under the jig drops into the USB-C slot to hold it in place. A stop against the clock's side and a post in the corner of the hand-hold keep it from turning, and a tab on the left gives your thumb somewhere to hold it down.

## Files

| File | Purpose |
| --- | --- |
| `maclock-usb-jig.stl` | The jig, its side stop, the USB-C key and the post, on one plate. Print at 0.2mm layers, no supports. |
| `maclock-usb-jig-key.stl` | The key on its own, to reprint it. |
| `maclock-usb-jig.step` | The same parts as solids, to open and edit in any CAD tool (Fusion, Onshape, FreeCAD). |
| `maclock-usb-jig.scad` | The same parts with sliders for your hole, your Dremel and your printer, for OpenSCAD's Customizer. |
| `params.py`, `jig.py` | The source of the STL and STEP: every dimension, and how the parts are built from them ([build123d](https://github.com/gumyr/build123d)). |

## You'll need

- A Dremel with its router base (the one with a 60mm round foot) and a 3mm flat-ended cutting bit. Other sizes work too: see [Making one for your tools](#making-one-for-your-tools).
- Two M3 × 30mm countersunk screws

## Cutting the port

1. Press the key into the slot-shaped pocket under the jig, and the post into the square pocket near the top, each with the end that was on the print bed going in first. The post's cut-off corner points toward the opening under the bit. Both should be a snug push fit: sand them if they won't go in, or add a drop of glue if they fall out.
2. Screw the side stop under the two holes on the right, with its holes up against the jig and the raised strip near its bottom facing the middle of the jig, where the clock will be. That strip is the only part that touches the clock. The holes only open at one end and sit nearer the stop's outer side, so it only fits that way. The screws go in from the top and cut their own thread. Drive them until the heads sit just below the floor, so the router base glides over them.
3. Take the back shell off the clock and lay it face down, with the back facing up.
4. Set the jig on the back with the key in the USB-C slot. The post drops into the hand-hold, against its end and the clock's top, and the side stop rests against the clock's side.
5. Set the bit to stick out about 6mm below the router base's foot. That's enough to go through the jig's 3mm floor and the 2mm shell.
6. Hold the jig down with your thumb on the tab on the left, keeping the side stop against the side. Put the base in the jig with the bit over the opening, switch on, and tip the bit down into the shell to start the cut.
7. Run the foot around the inside of the walls, keeping it pressed against them, until the middle drops out. Keep the Dremel's cord pointing the same way the whole time: if the bit sits a little off-centre in the base, turning the Dremel would make the hole bigger.
8. Clean up the edges, then glue the USB-A socket in from the inside.

## Making one for your tools

Open `maclock-usb-jig.scad` in [OpenSCAD](https://openscad.org) and set the sliders in its Customizer panel, then render and export an STL:

- `hole_width` and `hole_height`: the size of the hole in the shell. Printers tend to make inside walls a little tight, so if your first hole comes out small, add a few tenths to both.
- `foot_diameter` and `bit_diameter`: measure across your router base's round foot and your bit. The jig's walls move so the bit still runs along the edges of the hole.
- `press_fit`: the gap around the key and the post where they press into the jig. Make it bigger if they won't go in, smaller if they fall out.
- `part`: all four parts on one plate, or just one of them, to reprint it.

The key, the post and the side stop stay where they are whatever you set, because they're placed by the clock, not the jig.

## Changing the design

`params.py` and `jig.py` are the source of the STL and STEP. `maclock-usb-jig.scad` builds the same parts again for OpenSCAD, so a change to one goes in the other too. `build.sh` runs the tests, which check both make the same parts at the defaults and with every slider at its ends, then writes the STL and STEP. That check needs OpenSCAD on your `PATH`, and GitHub runs it on every push that changes this folder. build123d doesn't run on Python 3.15 yet, so make the environment with 3.14:

    python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
    ./build.sh

## License

CERN-OHL-S-2.0, same as the [breakout PCB](../maclock-pcb/README.md#license) — see [`LICENSE`](./LICENSE).
