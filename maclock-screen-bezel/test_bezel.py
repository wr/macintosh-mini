import unittest

from build123d import Box, Cylinder, Pos

import bezel
import params as p


def overlap(part, probe):
    """Volume a probe shares with a part. Solid & Box, not Compound & Box,
    which returns an empty Compound in build123d 0.11."""
    hit = part.solids()[0] & probe
    return hit.volume if hit else 0.0


class TestParts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = bezel.parts()

    def test_four_valid_single_solids(self):
        self.assertEqual(len(self.parts), 4)
        for name, part in self.parts.items():
            with self.subTest(name):
                self.assertTrue(part.is_valid)
                self.assertEqual(len(part.solids()), 1)

    def test_same_place_on_the_plate_as_the_tinkercad_part(self):
        # Bounds read off the Tinkercad STL, but for the frame's left edge,
        # 0.400 in from its -28.100 since the 2026-10-21 fit change.
        expected = {
            "frame": (-27.700, 43.000, -27.855, 34.995, 0, 5.000),
            "bottom bar": (-28.205, 39.800, -40.400, -31.200, 0, 3.000),
            "Z clip, left": (-23.600, -17.100, -15.300, -0.300, 0, 4.000),
            "Z clip, right": (-14.500, -8.000, -15.300, -0.300, 0, 4.000),
        }
        for name, want in expected.items():
            bb = self.parts[name].bounding_box()
            got = (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, places=3, msg=name)

    def test_volume_is_the_tinkercad_part_less_the_fit_change(self):
        # The STL's 5775.826 mm3, plus 0.036 for its four 48-sided screw holes
        # now being true circles, less 101.014 for the frame's narrower left
        # edge and 224.816 for its larger window.
        total = sum(part.volume for part in self.parts.values())
        self.assertAlmostEqual(total, 5450.033, places=2)


class TestFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = bezel.frame()

    def test_window_is_open_full_height(self):
        probe = Pos(p.WINDOW_X0 + p.WINDOW_W / 2, p.WINDOW_Y0 + p.WINDOW_H / 2, p.FRAME_T / 2) * Box(
            p.WINDOW_W - 0.01, p.WINDOW_H - 0.01, p.FRAME_T)
        self.assertAlmostEqual(overlap(self.f, probe), 0.0, places=6)

    def test_wall_between_notch_and_window_is_0_495(self):
        # The frame's thinnest wall. A probe wider than it, over the notch's
        # height, holds just the wall.
        x0 = p.FRAME_X0 - 1
        x1 = p.WINDOW_X0 + 1
        h = p.NOTCH_Y1 - p.NOTCH_Y0
        probe = Pos((x0 + x1) / 2, (p.NOTCH_Y0 + p.NOTCH_Y1) / 2, p.FRAME_T / 2) * Box(x1 - x0, h, p.FRAME_T)
        self.assertAlmostEqual(overlap(self.f, probe), 0.495 * h * p.FRAME_T, places=6)

    def test_screw_holes_are_clear_and_64_apart(self):
        y = p.FRAME_Y0 + p.FRAME_H + p.LUG_L / 2
        xs = [x + p.LUG_W / 2 for x in (p.LUG_LEFT_X0, p.LUG_RIGHT_X0)]
        self.assertAlmostEqual(xs[1] - xs[0], 64.000, places=3)
        for x in xs:
            clear = Pos(x, y, p.FRAME_T / 2) * Cylinder(p.HOLE_D / 2 - 0.01, p.FRAME_T)
            self.assertAlmostEqual(overlap(self.f, clear), 0.0, places=6)
            wall = Pos(x, y, (p.LUG_Z + p.FRAME_T) / 2) * Cylinder(p.HOLE_D / 2 + 0.05, p.FRAME_T - p.LUG_Z)
            self.assertGreater(overlap(self.f, wall), 0.0)


class TestBottomBar(unittest.TestCase):
    def test_screw_holes_are_clear_and_64_005_apart(self):
        b = bezel.bottom_bar()
        y = p.BAR_Y0 + p.FLANGE_W + p.LUG_L / 2
        xs = [p.BAR_X0 + p.LUG_W / 2, p.BAR_X0 + p.BAR_L - p.LUG_W / 2]
        self.assertAlmostEqual(xs[1] - xs[0], 64.005, places=3)
        for x in xs:
            clear = Pos(x, y, p.BAR_WALL_T / 2) * Cylinder(p.HOLE_D / 2 - 0.01, p.BAR_WALL_T)
            self.assertAlmostEqual(overlap(b, clear), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
