import itertools
import unittest

from build123d import Axis, Vector

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
        self.assertAlmostEqual(p.USBC_Y, -56.045, places=3)
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

    def test_thumb_tab_is_floor_out_past_the_left_wall(self):
        left_wall = p.HOLE_X - p.POCKET_W / 2 - p.WALL_W
        x = left_wall - p.THUMB_W / 2
        for y in (p.THUMB_Y0 + 2, p.THUMB_Y1 - 2):
            with self.subTest(y=y):
                self.assertTrue(solid_at(self.j, x, y, p.FLOOR_T - EPS))
                self.assertFalse(solid_at(self.j, x, y, p.FLOOR_T + EPS))
        # Stops 15 or more below the top: the vents and markings are above.
        self.assertFalse(solid_at(self.j, x, -15, 1))
        bb = self.j.bounding_box()
        self.assertAlmostEqual(bb.min.X, left_wall - p.THUMB_W, places=6)
        self.assertAlmostEqual(bb.min.Y, p.THUMB_Y0, places=6)

    def test_thumb_tab_is_twice_the_first_prints(self):
        # That one was 18 x 44.5; near enough twice is fine.
        self.assertGreater(p.THUMB_W * (p.THUMB_Y1 - p.THUMB_Y0), 1.75 * 18 * 44.5)

    def test_thumb_tab_stays_on_the_back(self):
        # Inside the back's left edge and above its lower screw holes.
        self.assertGreaterEqual(self.j.bounding_box().min.X, -p.BACK_W + 2)
        self.assertGreaterEqual(p.THUMB_Y0, p.BACK_SCREWS_Y + 3)

    def test_reaches_past_the_bottom_of_the_usbc_slot(self):
        slot_bottom = p.USBC_Y - p.USBC_H / 2
        self.assertLess(p.JIG_Y0, slot_bottom - 3)
        self.assertTrue(solid_at(self.j, p.HOLE_X, p.JIG_Y0 + 1, 1))
        self.assertFalse(solid_at(self.j, p.HOLE_X, p.JIG_Y0 - 1, 1))

    def test_key_pocket_under_the_jig_over_the_slot(self):
        w, l = p.KEY_RECESS_W / 2 - EPS, p.KEY_RECESS_L / 2 - EPS
        pocket = jig.box(p.HOLE_X - w + 1.5, p.HOLE_X + w - 1.5,  # straight part
                         p.USBC_Y - l + 1.6, p.USBC_Y + l - 1.6, 0, p.KEY_SEAT - EPS)
        self.assertAlmostEqual(overlap(self.j, pocket), 0.0, places=6)
        for y in (p.USBC_Y - l, p.USBC_Y + l):  # both rounded ends open
            self.assertFalse(solid_at(self.j, p.HOLE_X, y, 1))
        self.assertTrue(solid_at(self.j, p.HOLE_X, p.USBC_Y, p.KEY_SEAT + EPS))
        self.assertTrue(solid_at(self.j, p.HOLE_X + p.KEY_RECESS_W / 2 + EPS, p.USBC_Y, 1))

    def test_floor_over_the_key_is_at_least_1(self):
        # The slot's top end runs under the router's floor, not the wall.
        slot_top = p.USBC_Y + p.USBC_H / 2
        wall_inside = p.HOLE_Y - p.POCKET_H / 2
        self.assertGreater(slot_top, wall_inside)
        self.assertGreaterEqual(p.FLOOR_T - p.KEY_SEAT, 1.0)


def screws():
    """(x, y) of every stop screw, in the clock's coordinates."""
    return [(p.SCREW_IN, y) for y in p.SIDE_STOP_SCREW_Y]


class TestScrews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jig.jig()
        cls.stop = jig.side_stop()

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

    def test_router_floor_has_two_windows_and_two_screw_holes(self):
        at_floor = [f for f in self.j.faces() if abs(f.center().Z - p.FLOOR_T) < 1e-6]
        router_floor = max(at_floor, key=lambda f: f.area)
        self.assertEqual(len(router_floor.inner_wires()), 4)

    def test_screw_taps_into_the_stop_and_ends_inside_it(self):
        r = p.SCREW_TAP_D / 2
        loose = p.SCREW_LOOSE_D / 2
        for x, y in screws():
            with self.subTest(x=x, y=y):
                self.assertFalse(solid_at(self.stop, x + r - EPS, y, -1))
                self.assertTrue(solid_at(self.stop, x + r + EPS, y, -1))
                self.assertFalse(solid_at(self.stop, x + loose - EPS, y, -p.SCREW_HOLE_L + 1))
                self.assertTrue(solid_at(self.stop, x + loose + EPS, y, -p.SCREW_HOLE_L + 1))
        tip = p.FLOOR_T - p.SCREW_L
        self.assertGreater(tip, -p.SCREW_HOLE_L)

    def test_holes_stop_short_of_the_bottom_so_it_only_goes_on_one_way_up(self):
        for x, y in screws():
            with self.subTest(x=x, y=y):
                self.assertTrue(solid_at(self.stop, x, y, -p.STOP_H + EPS))


class TestSideStop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = jig.jig()
        cls.side = jig.side_stop()
        cls.band_top = -(p.STOP_H - p.EDGE_RELIEF - p.CONTACT_H)
        cls.band_z = cls.band_top - p.CONTACT_H / 2

    def test_valid_single_solid(self):
        self.assertTrue(self.side.is_valid)
        self.assertEqual(len(self.side.solids()), 1)

    def test_hangs_below_the_back(self):
        bb = self.side.bounding_box()
        self.assertAlmostEqual(bb.max.Z, 0.0, places=6)
        self.assertAlmostEqual(bb.min.Z, -p.STOP_H, places=6)

    def test_touches_the_flat_side_only_in_a_band_low_down(self):
        # Low down is how the first print sat steadiest.
        y = (p.SIDE_STOP_Y0 + p.SIDE_STOP_Y1) / 2
        self.assertAlmostEqual(self.side.bounding_box().min.X, 0.0, places=6)
        self.assertLess(self.band_top, -15)
        self.assertTrue(solid_at(self.side, EPS, y, self.band_z))
        for z in (-EPS, -10, self.band_top + p.FACE_RELIEF + EPS):  # stands back above
            with self.subTest(z=z):
                self.assertFalse(solid_at(self.side, EPS, y, z))
        self.assertFalse(solid_at(self.side, EPS, y, -p.STOP_H + EPS))  # chamfered below

    def test_steps_back_on_a_45_degree_ramp_so_it_prints_without_a_ledge(self):
        y = (p.SIDE_STOP_Y0 + p.SIDE_STOP_Y1) / 2
        z = self.band_top + p.FACE_RELIEF / 2
        self.assertTrue(solid_at(self.side, p.FACE_RELIEF / 2 + 0.1, y, z))
        self.assertFalse(solid_at(self.side, p.FACE_RELIEF / 2 - 0.1, y, z))

    def test_sits_at_the_top_far_from_the_key(self):
        self.assertGreater(p.SIDE_STOP_Y0 - p.USBC_Y, 30)

    def test_is_under_solid_floor(self):
        bb = self.side.bounding_box()
        for x, y in itertools.product((bb.min.X + 0.5, bb.max.X - 0.5),
                                      (bb.min.Y + 0.5, bb.max.Y - 0.5)):
            with self.subTest(x=x, y=y):
                self.assertTrue(solid_at(self.j, x, y, EPS))


class TestKey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = jig.key()

    def test_valid_single_solid(self):
        self.assertTrue(self.key.is_valid)
        self.assertEqual(len(self.key.solids()), 1)

    def test_fits_the_slot_with_a_tenth_all_round(self):
        bb = self.key.bounding_box()
        self.assertAlmostEqual(bb.size.X, p.USBC_W - 0.2, places=3)
        self.assertAlmostEqual(bb.size.Y, p.USBC_H - 0.19, places=3)
        self.assertAlmostEqual(bb.center().X, p.HOLE_X, places=6)
        self.assertAlmostEqual(bb.center().Y, p.USBC_Y, places=6)

    def test_drops_into_the_slot_and_presses_into_the_jig(self):
        bb = self.key.bounding_box()
        self.assertAlmostEqual(bb.min.Z, -p.KEY_PROUD, places=6)
        self.assertAlmostEqual(bb.max.Z, p.KEY_SEAT, places=6)

    def test_is_twice_the_first_prints_height_and_reaches_through_the_shell(self):
        # The 4 mm first print jumped out of the slot. At 8 it goes right
        # through the shell, so the jig has to lift well clear to lose it.
        self.assertAlmostEqual(self.key.bounding_box().size.Z, 8.0, places=6)
        self.assertGreater(p.KEY_PROUD, p.SHELL_T + 2)

    def test_fits_its_pocket_in_the_jig(self):
        self.assertAlmostEqual(overlap(jig.jig(), self.key), 0.0, places=6)

    def test_slot_end_is_chamfered_to_find_the_slot(self):
        # At least 0.3: a probe 0.15 in from the edge, 0.05 up, is clear.
        x = p.HOLE_X + p.KEY_W / 2 - 0.15
        self.assertFalse(solid_at(self.key, x, p.USBC_Y, -p.KEY_PROUD + 0.05))
        self.assertTrue(solid_at(self.key, x, p.USBC_Y, 0))


class TestPost(unittest.TestCase):
    """A post in the inside corner where the hand-hold's end meets the
    clock's top, at Wells's mark on the printed jig."""

    @classmethod
    def setUpClass(cls):
        cls.j = jig.jig()
        cls.post = jig.post()
        cls.bb = cls.post.bounding_box()

    def test_mark_is_22_3_in_and_20_65_down_on_the_printed_jig(self):
        left = p.HOLE_X - p.POCKET_W / 2 - p.WALL_W
        top = p.HOLE_Y + p.POCKET_H / 2 + p.WALL_W
        self.assertAlmostEqual(p.HANDHOLD_CORNER_X, left + 22.3, places=6)
        self.assertAlmostEqual(p.HANDHOLD_CORNER_Y, top - 20.65, places=6)
        # At that height the jig's left edge is its main body, not the thumb
        # tab, so the mark is the same on every print.
        self.assertLess(p.THUMB_Y1, p.HANDHOLD_CORNER_Y)

    def test_valid_single_solid(self):
        self.assertTrue(self.post.is_valid)
        self.assertEqual(len(self.post.solids()), 1)

    def test_touches_the_hand_holds_end_and_the_top_with_a_little_clearance(self):
        c = p.POST_CLEAR
        self.assertLessEqual(c, 0.25)
        self.assertAlmostEqual(self.bb.max.X, p.HANDHOLD_CORNER_X - c, places=6)
        self.assertAlmostEqual(self.bb.min.Y, p.HANDHOLD_CORNER_Y + c, places=6)

    def test_hangs_below_the_back_and_presses_into_the_jig(self):
        self.assertAlmostEqual(self.bb.min.Z, -p.POST_PROUD, places=6)
        self.assertAlmostEqual(self.bb.max.Z, p.POST_SEAT, places=6)
        self.assertGreaterEqual(p.POST_PROUD, 4)

    def test_fits_its_pocket_under_the_router_floor(self):
        x, y = self.bb.center().X, self.bb.center().Y
        self.assertAlmostEqual(overlap(self.j, self.post), 0.0, places=6)
        self.assertFalse(solid_at(self.j, x, y, 1))
        self.assertTrue(solid_at(self.j, x, y, p.POST_SEAT + EPS))
        self.assertGreaterEqual(p.FLOOR_T - p.POST_SEAT, 1.0)

    def test_corner_into_the_clocks_corner_is_chamfered(self):
        # So a fillet where the hand-hold's end meets the top can't hold the
        # post off either face.
        self.assertFalse(solid_at(self.post, self.bb.max.X - 0.15, self.bb.min.Y + 0.15, -1))
        self.assertTrue(solid_at(self.post, self.bb.max.X - 0.15, self.bb.min.Y + 1.0, -1))


class TestPlate(unittest.TestCase):
    def test_parts_lie_on_the_bed_apart(self):
        placed = jig.plate_parts()
        self.assertEqual(set(placed), {"jig", "side stop", "key", "post"})
        boxes = [part.bounding_box() for part in placed.values()]
        for bb in boxes:
            self.assertAlmostEqual(bb.min.Z, 0.0, places=6)
        for a, b in itertools.combinations(boxes, 2):
            apart = (a.max.X <= b.min.X or b.max.X <= a.min.X or
                     a.max.Y <= b.min.Y or b.max.Y <= a.min.Y)
            self.assertTrue(apart)

    def test_printed_parts_keep_their_volume(self):
        placed = jig.plate_parts()
        self.assertAlmostEqual(placed["side stop"].volume, jig.side_stop().volume, places=3)
        self.assertAlmostEqual(placed["key"].volume, jig.key().volume, places=3)
        self.assertAlmostEqual(placed["post"].volume, jig.post().volume, places=3)

    def test_stop_and_key_print_with_the_jig_end_on_the_bed(self):
        # Flipped, so the stop's holes open on the bed with the blind end up,
        # and the key's chamfered end is up.
        placed = jig.plate_parts()
        faces = placed["side stop"].faces().sort_by(Axis.Z)
        self.assertEqual(len(faces[0].inner_wires()), 2)
        self.assertEqual(len(faces[-1].inner_wires()), 0)
        faces = placed["key"].faces().sort_by(Axis.Z)
        self.assertGreater(faces[0].area, faces[-1].area)


if __name__ == "__main__":
    unittest.main()
