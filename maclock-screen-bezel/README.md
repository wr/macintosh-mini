# Macintosh Mini screen bezel

3D-printable bezel that frames the Waveshare 2.8" DPI LCD inside the Maclock's shell, hiding the gap between the panel and the original screen cutout. Fitting it is [step 4 of the build guide](../BUILD.md#4-fit-the-screen).

## Files

| File | Purpose |
| --- | --- |
| `maclock-screen-bezel.stl` | Print at 0.2mm layers, no supports. |
| `maclock-screen-bezel.step` | The same parts as solids, to open and edit in any CAD tool (Fusion, Onshape, FreeCAD, KiCad's 3D viewer). |
| `params.py`, `bezel.py` | The source: every dimension, and how the parts are built from them ([build123d](https://github.com/gumyr/build123d)). |

The plate has four parts: the frame, the bar that sits below it, and two Z clips. I recommend using black PLA or PETG for a seamless look.

## Changing it

Change a number in `params.py`, then rebuild. `build.sh` runs the tests and writes the STL and STEP:

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    ./build.sh

The dimensions were read off the original Tinkercad model to 0.001 mm. The rebuild is the same part: every vertex of the Tinkercad STL lies on its surface, and its four screw holes are now true circles.

> [!WARNING]
> The fit should be snug, but not tight. Scale up the print size slightly or sand down the inner edges if the fit is too tight, otherwise you risk cracking the LCD.

## License

CERN-OHL-S-2.0, same as the [breakout PCB](../maclock-pcb/README.md#license) — see [`LICENSE`](./LICENSE).
