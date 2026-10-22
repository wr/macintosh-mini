# Macintosh Mini USB port jig

3D-printable guide for cutting the optional USB-A port into the Maclock's back shell with a Dremel in its router base. It puts a 7 × 14mm hole in the top right of the back, 38mm above the USB-C port and in line with it, with straight sides every time. The port is in the [build guide](https://wells.ee/projects/macintosh-mini/).

The router base's round foot slides inside the jig's walls. Pushing it against each wall in turn runs the bit along each side of the hole. Two stops under the jig hold it against the clock's flat side and flat top.

## Files

| File | Purpose |
| --- | --- |
| `maclock-usb-jig.stl` | The jig and its two stops, on one plate. Print at 0.2mm layers, no supports. |
| `maclock-usb-jig.step` | The same parts as solids, to open and edit in any CAD tool (Fusion, Onshape, FreeCAD). |
| `params.py`, `jig.py` | The source: every dimension, and how the parts are built from them ([build123d](https://github.com/gumyr/build123d)). |

## You'll need

- A Dremel with its router base (the one with a 60mm round foot) and a 3mm flat-ended cutting bit
- Four M3 × 30mm countersunk screws

## Cutting the port

1. Screw the long stop under the two holes that run up and down, and the short stop under the two side by side near the top. Each stop goes on with the end that was on the print bed against the jig's underside, and its angled edge facing the middle of the jig, where the clock will be. Its holes sit nearer its outer side, so it only lines up that way round. The screws go in from the top and cut their own thread. Drive them until the heads sit just below the floor, so the router base glides over them.
2. Take the back shell off the clock and lay it face down, with the back facing up.
3. Set the jig on the back. The long stop goes against the clock's side nearest the ports, and the short stop goes into the hand-hold on top. Push the jig into the corner until both stops touch.
4. Set the bit to stick out about 6mm below the router base's foot. That's enough to go through the jig's 3mm floor and the 2mm shell.
5. Hold the jig into the corner. Put the base in the jig with the bit over the opening, switch on, and tip the bit down into the shell to start the cut.
6. Run the foot around the inside of the walls, keeping it pressed against them, until the middle drops out. Keep the Dremel's cord pointing the same way the whole time: if the bit sits a little off-centre in the base, turning the Dremel would make the hole bigger.
7. Clean up the edges, then glue the USB-A socket in from the inside.

## Changing it

Change a number in `params.py`, then rebuild. `build.sh` runs the tests and writes the STL and STEP. build123d doesn't run on Python 3.15 yet, so make the environment with 3.14:

    python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
    ./build.sh

The hole's size is `HOLE_W` and `HOLE_H`. Printers tend to make inside walls a little tight, so if the first hole comes out small, add a few tenths to those. If your router base's foot isn't 60mm across, set `FOOT_D` to match and the walls move to suit.

## License

CERN-OHL-S-2.0, same as the [breakout PCB](../maclock-pcb/README.md#license) — see [`LICENSE`](./LICENSE).
