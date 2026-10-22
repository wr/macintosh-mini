"""The USB-A cutting jig: a fence for the Dremel's router base, a key that
anchors it in the USB-C slot, and a stop against the clock's side that squares
it up. Every number comes from params.py.

jig(), side_stop() and key() are where they sit on the clock; plate_parts()
lays them out on the print bed."""
from build123d import Axis, Box, Compound, Cone, Cylinder, Pos, Rot, SlotOverall, chamfer, extrude

import params as p

AIR = 1.0
"""Cuts overshoot outside faces by this much; a boolean whose faces all
coincide returns nothing in OCCT."""


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def rod(x, y, d, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, z1 - z0)


def slot(w, l, z0, z1):
    """An upright stadium w across and l tall, centred on the USB-C slot."""
    return Pos(p.HOLE_X, p.USBC_Y, z0) * extrude(SlotOverall(l, w, rotation=90), z1 - z0)


def screws():
    """(x, y) of the side stop's two screws."""
    return [(p.SCREW_IN, y) for y in p.SIDE_STOP_SCREW_Y]


def countersunk(x, y):
    """Clearance hole through the floor with a 90-degree countersink at the
    top, overshooting both faces by AIR."""
    top_r = p.SINK_D / 2 + AIR
    depth = top_r - p.SCREW_CLEAR_D / 2
    sink = Pos(x, y, p.FLOOR_T + AIR - depth / 2) * Cone(p.SCREW_CLEAR_D / 2, top_r, depth)
    return sink + rod(x, y, p.SCREW_CLEAR_D, -AIR, p.FLOOR_T + AIR)


def jig():
    w, h = p.POCKET_W / 2, p.POCKET_H / 2
    x0, x1 = p.HOLE_X - w, p.HOLE_X + w
    y0, y1 = p.HOLE_Y - h, p.HOLE_Y + h
    t = p.WALL_W
    top = p.FLOOR_T + p.WALL_H
    part = box(x0 - t, x1 + t, p.JIG_Y0, y1 + t, 0, top)
    part -= box(x0, x1, y0, y1, p.FLOOR_T, top + AIR)
    # Thumb tab, overlapping the left wall by AIR so the union fuses.
    part += box(x0 - t - p.THUMB_W, x0 - t + AIR, p.THUMB_Y0, p.THUMB_Y1, 0, p.FLOOR_T)

    m = p.BIT_WINDOW_MARGIN
    part -= box(p.HOLE_X - p.HOLE_W / 2 - m, p.HOLE_X + p.HOLE_W / 2 + m,
                p.HOLE_Y - p.HOLE_H / 2 - m, p.HOLE_Y + p.HOLE_H / 2 + m, -AIR, top)
    sw = p.SWITCH_WINDOW_W / 2
    part -= box(p.HOLE_X - sw, p.HOLE_X + sw, p.SWITCH_WINDOW_Y0, p.SWITCH_WINDOW_Y1, -AIR, top)
    part -= slot(p.KEY_RECESS_W, p.KEY_RECESS_L, -AIR, p.KEY_SEAT)
    for x, y in screws():
        part -= countersunk(x, y)
    return part


def side_stop():
    """A block whose face on the plane X = 0 touches the clock's flat side,
    hanging from Z = 0 down to -STOP_H."""
    y0, y1 = p.SIDE_STOP_Y0, p.SIDE_STOP_Y1
    part = box(0, p.STOP_T, y0, y1, -p.STOP_H, 0)
    # 45-degree cut along the top inside edge, for the clock's rounded edge.
    s = p.EDGE_RELIEF * 2 ** 0.5
    part -= Pos(0, (y0 + y1) / 2, 0) * Rot(0, 45, 0) * Box(s, y1 - y0 + 2 * AIR, s)
    band_bottom = -(p.EDGE_RELIEF + p.CONTACT_H)
    part -= box(-AIR, p.FACE_RELIEF, y0 - AIR, y1 + AIR, -p.STOP_H - AIR, band_bottom)
    for y in p.SIDE_STOP_SCREW_Y:
        part -= rod(p.SCREW_IN, y, p.SCREW_TAP_D, -p.TAP_L, AIR)
        part -= rod(p.SCREW_IN, y, p.SCREW_LOOSE_D, -p.SCREW_HOLE_L, -p.TAP_L)
    return part


def key():
    """Presses KEY_SEAT up into the jig and drops KEY_PROUD into the slot."""
    part = slot(p.KEY_W, p.KEY_L, -p.KEY_PROUD, p.KEY_SEAT)
    return chamfer(part.edges().group_by(Axis.Z)[0], p.KEY_CHAMFER)


def place(part, x0, y0):
    """Move a part so its bounding box starts at (x0, y0, 0)."""
    bb = part.bounding_box()
    return Pos(x0 - bb.min.X, y0 - bb.min.Y, -bb.min.Z) * part


def plate_parts():
    """The jig as it sits on the clock, and the stop and key beside it upside
    down, so each prints with the end that meets the jig on the bed and no
    supports."""
    j = jig()
    bb = j.bounding_box()
    side = place(Rot(180, 0, 0) * side_stop(), bb.max.X + p.PLATE_GAP, bb.min.Y)
    k = place(Rot(180, 0, 0) * key(), side.bounding_box().max.X + p.PLATE_GAP, bb.min.Y)
    return {"jig": j, "side stop": side, "key": k}


def plate():
    """All three parts where they sit on the print bed."""
    return Compound(children=list(plate_parts().values()))
