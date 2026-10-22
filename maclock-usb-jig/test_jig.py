import itertools
import unittest

from build123d import Vector

import jig
import params as p

EPS = 0.02
"""How far either side of a face the probes look."""


def solid_at(part, x, y, z):
    return part.is_inside(Vector(x, y, z))


def overlap(part, probe):
    """Volume a probe shares with a part. Solid & Box, not Compound & Box,
    which returns an empty Compound in build123d 0.11."""
    hit = part.solids()[0] & probe
    return hit.volume if hit else 0.0


class TestHole(unittest.TestCase):
    def test_hole_is_in_line_with_the_usbc_slot_and_38_above_it(self):
        self.assertAlmostEqual(p.HOLE_X, -10.15, places=3)
        self.assertAlmostEqual(p.HOLE_Y, -18.045, places=3)

    def test_floor_and_shell_fit_inside_the_cutting_head(self):
        # With 0.5 to spare, so the smooth shank never rubs the floor.
        self.assertLessEqual(p.FLOOR_T + p.SHELL_T + 0.5, p.BIT_CUT_L)


class TestJig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jig.jig()
        cls.wall_z = p.FLOOR_T + p.WALL_H / 2

    def test_valid_single_solid(self):
        self.assertTrue(self.j.is_valid)
        self.assertEqual(len(self.j.solids()), 1)

    def test_foot_against_each_wall_puts_the_bit_on_that_edge_of_the_hole(self):
        # Foot centre is a radius off the wall; the bit's edge a bit radius
        # further on. Each wall's face is found where the probes flip.
        reach = p.FOOT_D / 2 - p.BIT_D / 2
        x0, x1 = p.HOLE_X - p.HOLE_W / 2, p.HOLE_X + p.HOLE_W / 2
        y0, y1 = p.HOLE_Y - p.HOLE_H / 2, p.HOLE_Y + p.HOLE_H / 2
        z = self.wall_z
        walls = {
            "left": ((x0 - reach - EPS, p.HOLE_Y), (x0 - reach + EPS, p.HOLE_Y)),
            "right": ((x1 + reach + EPS, p.HOLE_Y), (x1 + reach - EPS, p.HOLE_Y)),
            "bottom": ((p.HOLE_X, y0 - reach - EPS), (p.HOLE_X, y0 - reach + EPS)),
            "top": ((p.HOLE_X, y1 + reach + EPS), (p.HOLE_X, y1 + reach - EPS)),
        }
        for name, (in_wall, in_pocket) in walls.items():
            with self.subTest(name):
                self.assertTrue(solid_at(self.j, *in_wall, z))
                self.assertFalse(solid_at(self.j, *in_pocket, z))

    def test_walls_meet_the_foots_straight_rim_not_its_slope(self):
        self.assertAlmostEqual(self.j.bounding_box().max.Z, p.FLOOR_T + p.WALL_H, places=3)
        self.assertLess(p.WALL_H, p.FOOT_EDGE_H)

    def test_floor_is_the_glide_surface(self):
        # Solid just under FLOOR_T and clear just over it, all round the pocket.
        reach = p.POCKET_W / 2 - 2, p.POCKET_H / 2 - 2
        for sx, sy in itertools.product((-1, 1), repeat=2):
            x, y = p.HOLE_X + sx * reach[0], p.HOLE_Y + sy * reach[1]
            with self.subTest(x=x, y=y):
                self.assertTrue(solid_at(self.j, x, y, p.FLOOR_T - EPS))
                self.assertFalse(solid_at(self.j, x, y, p.FLOOR_T + EPS))

    def test_sits_flat_on_the_back(self):
        self.assertAlmostEqual(self.j.bounding_box().min.Z, 0.0, places=6)

    def test_bit_window_leaves_3_all_round_the_hole(self):
        # Room to tip the bit in to start the cut.
        m = 3.0 - EPS
        probe = jig.box(p.HOLE_X - p.HOLE_W / 2 - m, p.HOLE_X + p.HOLE_W / 2 + m,
                        p.HOLE_Y - p.HOLE_H / 2 - m, p.HOLE_Y + p.HOLE_H / 2 + m,
                        0, p.FLOOR_T)
        self.assertAlmostEqual(overlap(self.j, probe), 0.0, places=6)

    def test_switch_window_is_open_and_clear_of_the_bit_window(self):
        w = p.SWITCH_WINDOW_W / 2 - EPS
        probe = jig.box(p.HOLE_X - w, p.HOLE_X + w,
                        p.SWITCH_WINDOW_Y0 + EPS, p.SWITCH_WINDOW_Y1 - EPS, 0, p.FLOOR_T)
        self.assertAlmostEqual(overlap(self.j, probe), 0.0, places=6)
        bit_window_bottom = p.HOLE_Y - p.HOLE_H / 2 - p.BIT_WINDOW_MARGIN
        self.assertTrue(solid_at(self.j, p.HOLE_X, (p.SWITCH_WINDOW_Y1 + bit_window_bottom) / 2, 1))

    def test_switch_is_shorter_than_the_floor(self):
        self.assertLess(p.SWITCH_PROUD, p.FLOOR_T)


def screws():
    """(x, y) of every stop screw, in the clock's coordinates."""
    side = [(p.SCREW_IN, y) for y in p.SIDE_STOP_SCREW_Y]
    top = [(x, p.SCREW_IN) for x in p.TOP_STOP_SCREW_X]
    return side + top


class TestScrews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jig.jig()
        cls.stops = [jig.side_stop(), jig.top_stop()]

    def test_clearance_hole_through_the_floor(self):
        r = p.SCREW_CLEAR_D / 2
        for x, y in screws():
            with self.subTest(x=x, y=y):
                self.assertFalse(solid_at(self.j, x + r - EPS, y, p.FLOOR_T / 2 - 1))
                self.assertTrue(solid_at(self.j, x + r + EPS, y, p.FLOOR_T / 2 - 1))

    def test_head_sinks_below_the_glide_surface(self):
        # The countersink is SINK_D across at the top: wider than the head.
        # At 90 degrees it narrows by EPS a side EPS down.
        self.assertGreater(p.SINK_D, p.SCREW_HEAD_D)
        r = p.SINK_D / 2
        for x, y in screws():
            with self.subTest(x=x, y=y):
                self.assertFalse(solid_at(self.j, x + r - 2 * EPS, y, p.FLOOR_T - EPS))
                self.assertTrue(solid_at(self.j, x + r + EPS, y, p.FLOOR_T - EPS))

    def test_screw_taps_into_a_stop_and_ends_inside_it(self):
        r = p.SCREW_TAP_D / 2
        for (x, y), stop in zip(screws(), [self.stops[0]] * 2 + [self.stops[1]] * 2):
            with self.subTest(x=x, y=y):
                self.assertFalse(solid_at(stop, x + r - EPS, y, -1))
                self.assertTrue(solid_at(stop, x + r + EPS, y, -1))
                self.assertFalse(solid_at(stop, x + p.SCREW_LOOSE_D / 2 - EPS, y, -p.STOP_H + 1))
                self.assertTrue(solid_at(stop, x + p.SCREW_LOOSE_D / 2 + EPS, y, -p.STOP_H + 1))
        tip = p.FLOOR_T - p.SCREW_L
        self.assertGreater(tip, -p.STOP_H)


class TestStops(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jig.jig()
        cls.side = jig.side_stop()
        cls.top = jig.top_stop()
        cls.band_z = -(p.EDGE_RELIEF + p.CONTACT_H / 2)
        cls.low_z = -(p.EDGE_RELIEF + p.CONTACT_H) - 3

    def test_valid_single_solids(self):
        for stop in (self.side, self.top):
            self.assertTrue(stop.is_valid)
            self.assertEqual(len(stop.solids()), 1)

    def test_hang_below_the_back(self):
        for stop in (self.side, self.top):
            bb = stop.bounding_box()
            self.assertAlmostEqual(bb.max.Z, 0.0, places=6)
            self.assertAlmostEqual(bb.min.Z, -p.STOP_H, places=6)

    def test_side_stop_touches_the_flat_side_only_in_its_band(self):
        y = (p.SIDE_STOP_Y0 + p.SIDE_STOP_Y1) / 2
        self.assertAlmostEqual(self.side.bounding_box().min.X, 0.0, places=6)
        self.assertTrue(solid_at(self.side, EPS, y, self.band_z))
        self.assertFalse(solid_at(self.side, EPS, y, -EPS))  # clear of the rounded edge
        self.assertFalse(solid_at(self.side, EPS, y, self.low_z))  # stepped back below

    def test_top_stop_touches_the_flat_top_only_in_its_band(self):
        x = (p.TOP_STOP_X0 + p.TOP_STOP_X1) / 2
        self.assertAlmostEqual(self.top.bounding_box().min.Y, 0.0, places=6)
        self.assertTrue(solid_at(self.top, x, EPS, self.band_z))
        self.assertFalse(solid_at(self.top, x, EPS, -EPS))
        self.assertFalse(solid_at(self.top, x, EPS, self.low_z))

    def test_top_stop_sits_inside_the_hand_hold(self):
        bb = self.top.bounding_box()
        self.assertGreaterEqual(bb.min.X, -(p.HANDHOLD_IN + p.HANDHOLD_W))
        self.assertLessEqual(bb.max.X, -p.HANDHOLD_IN)

    def test_stops_are_under_solid_floor(self):
        # Every corner of each stop's top face has the jig's floor above it.
        for stop in (self.side, self.top):
            bb = stop.bounding_box()
            for x, y in itertools.product((bb.min.X + 0.5, bb.max.X - 0.5),
                                          (bb.min.Y + 0.5, bb.max.Y - 0.5)):
                with self.subTest(x=x, y=y):
                    self.assertTrue(solid_at(self.j, x, y, EPS))


class TestPlate(unittest.TestCase):
    def test_parts_lie_on_the_bed_apart(self):
        placed = jig.plate_parts()
        self.assertEqual(len(placed), 3)
        boxes = [part.bounding_box() for part in placed.values()]
        for bb in boxes:
            self.assertAlmostEqual(bb.min.Z, 0.0, places=6)
        for a, b in itertools.combinations(boxes, 2):
            apart = (a.max.X <= b.min.X or b.max.X <= a.min.X or
                     a.max.Y <= b.min.Y or b.max.Y <= a.min.Y)
            self.assertTrue(apart)

    def test_printed_stops_keep_their_volume(self):
        placed = jig.plate_parts()
        self.assertAlmostEqual(placed["side stop"].volume, jig.side_stop().volume, places=3)
        self.assertAlmostEqual(placed["top stop"].volume, jig.top_stop().volume, places=3)


if __name__ == "__main__":
    unittest.main()
