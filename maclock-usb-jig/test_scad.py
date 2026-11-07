"""maclock-usb-jig.scad, the copy for OpenSCAD's customizer, against jig.py:
at the defaults and at the ends of the sliders, each part has to come out the
same size, in the same place on the plate, with the same volume.

Needs OpenSCAD: on the PATH, or named by the OPENSCAD environment variable."""
import math
import os
import pathlib
import shutil
import struct
import subprocess
import tempfile
import unittest

from build123d import CenterOf

import jig
import params
import sliders

OPENSCAD = os.environ.get("OPENSCAD") or shutil.which("openscad")
ARGS = []
"""Extra arguments for OpenSCAD, set once it's found."""

SIZE_TOL = 0.01
"""mm, on outlines and centres of mass."""
VOLUME_TOL = 0.002
"""Of the volume. OpenSCAD makes circles out of 96 straight sides."""


def openscad_args():
    """Manifold renders in a fraction of a second, where older OpenSCADs'
    only renderer takes minutes."""
    help_text = subprocess.run([OPENSCAD, "--help"], capture_output=True, text=True)
    return ["--backend=manifold"] if "--backend" in help_text.stdout + help_text.stderr else []


def render(part, settings):
    """Triangles of the .scad's output: [((x, y, z), (x, y, z), (x, y, z)), ...]."""
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "out.stl"
        cmd = [OPENSCAD, *ARGS, "--export-format", "binstl", "-o", str(out), "-D", f'part="{part}"']
        for name, value in settings.items():
            cmd += ["-D", f"{name}={value}"]
        subprocess.run([*cmd, str(sliders.SCAD)], check=True, capture_output=True)
        data = out.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    tris = []
    for i in range(count):
        v = struct.unpack_from("<12f", data, 84 + 50 * i)
        tris.append((v[3:6], v[6:9], v[9:12]))
    return tris


def mesh_stats(tris):
    """(volume, (min x, y, z), (max x, y, z), centre of mass) of a closed mesh."""
    vol = 0.0
    moment = [0.0, 0.0, 0.0]
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for a, b, c in tris:
        v = (a[0] * (b[1] * c[2] - b[2] * c[1])
             - a[1] * (b[0] * c[2] - b[2] * c[0])
             + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        vol += v
        for i in range(3):
            moment[i] += v * (a[i] + b[i] + c[i]) / 4
            lo[i] = min(lo[i], a[i], b[i], c[i])
            hi[i] = max(hi[i], a[i], b[i], c[i])
    return vol, tuple(lo), tuple(hi), tuple(m / vol for m in moment)


def part_stats(part):
    """The same, for a build123d part."""
    bb = part.bounding_box()
    c = part.center(CenterOf.MASS)
    return part.volume, tuple(bb.min), tuple(bb.max), tuple(c)


@unittest.skipUnless(OPENSCAD, "OpenSCAD isn't installed")
class TestScadMatchesJig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global ARGS
        ARGS = openscad_args()

    def assertSame(self, got, want, offset=(0, 0, 0)):
        """got from the .scad, want from jig.py; offset is how far jig.py's
        part sits from where the .scad puts it."""
        g_vol, g_lo, g_hi, g_c = got
        w_vol, w_lo, w_hi, w_c = want
        self.assertAlmostEqual(g_vol, w_vol, delta=w_vol * VOLUME_TOL)
        for g, w, label in ((g_lo, w_lo, "min"), (g_hi, w_hi, "max"), (g_c, w_c, "centre")):
            for axis in range(3):
                self.assertAlmostEqual(g[axis] + offset[axis], w[axis], delta=SIZE_TOL,
                                       msg=f"{label} {'XYZ'[axis]}")

    def test_defaults_match_params(self):
        for name, (default, lo, hi) in sliders.sliders().items():
            with self.subTest(name):
                self.assertEqual(default, getattr(params, sliders.NAMES[name]))
                self.assertLessEqual(lo, default)
                self.assertLessEqual(default, hi)
        self.assertEqual(set(sliders.sliders()), set(sliders.NAMES))

    def test_every_part_on_the_plate(self):
        # One render per setting; the parts are split out of it by where
        # jig.py puts them, PLATE_GAP apart along X.
        for label, settings in sliders.settings().items():
            with self.subTest(label), sliders.moved(settings):
                want = {name: part_stats(part) for name, part in jig.plate_parts().items()}
                tris = render("all", settings)
                self.assertSame(mesh_stats(tris), part_stats(jig.plate()))
                for name, stats in want.items():
                    lo, hi = stats[1][0], stats[2][0]
                    mine = [t for t in tris if lo - 1 < sum(v[0] for v in t) / 3 < hi + 1]
                    with self.subTest(name):
                        self.assertSame(mesh_stats(mine), stats)

    def test_each_part_on_its_own_starts_at_the_origin(self):
        parts = {"jig": "jig", "stop": "side stop", "key": "key", "post": "post"}
        want = {name: part_stats(part) for name, part in jig.plate_parts().items()}
        for scad_name, name in parts.items():
            with self.subTest(name):
                got = mesh_stats(render(scad_name, {}))
                for axis in range(3):
                    self.assertAlmostEqual(got[1][axis], 0, delta=SIZE_TOL)
                self.assertSame(got, want[name], offset=want[name][1])

    def test_a_bit_wider_than_the_hole_stops_the_render(self):
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            render("jig", dict(hole_width=4, bit_diameter=5))
        self.assertIn("wider than the hole", caught.exception.stderr.decode())


if __name__ == "__main__":
    unittest.main()
