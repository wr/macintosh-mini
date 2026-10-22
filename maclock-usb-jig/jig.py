"""The USB-A cutting jig: a fence for the Dremel's router base, and two stops
that line it up on the clock. Every number comes from params.py.

jig(), side_stop() and top_stop() are where they sit on the clock;
plate_parts() lays them out on the print bed."""
from build123d import Box, Compound, Cone, Cylinder, Pos, Rot

import params as p

AIR = 1.0
"""Cuts overshoot outside faces by this much; a boolean whose faces all
coincide returns nothing in OCCT."""


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def rod(x, y, d, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, z1 - z0)


def screws():
    """(x, y) of every stop screw: two up the side stop, two along the top."""
    side = [(p.SCREW_IN, y) for y in p.SIDE_STOP_SCREW_Y]
    top = [(x, p.SCREW_IN) for x in p.TOP_STOP_SCREW_X]
    return side + top


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
    part = box(x0 - t, x1 + t, y0 - t, y1 + t, 0, top)
    part -= box(x0, x1, y0, y1, p.FLOOR_T, top + AIR)

    m = p.BIT_WINDOW_MARGIN
    part -= box(p.HOLE_X - p.HOLE_W / 2 - m, p.HOLE_X + p.HOLE_W / 2 + m,
                p.HOLE_Y - p.HOLE_H / 2 - m, p.HOLE_Y + p.HOLE_H / 2 + m, -AIR, top)
    sw = p.SWITCH_WINDOW_W / 2
    part -= box(p.HOLE_X - sw, p.HOLE_X + sw, p.SWITCH_WINDOW_Y0, p.SWITCH_WINDOW_Y1, -AIR, top)
    for x, y in screws():
        part -= countersunk(x, y)
    return part


def stop(y0, y1, screw_ys):
    """A side-style stop: a block whose face on the plane X = 0 touches the
    clock's flat side, hanging from Z = 0 down to -STOP_H."""
    part = box(0, p.STOP_T, y0, y1, -p.STOP_H, 0)
    # 45-degree cut along the top inside edge, for the clock's rounded edge.
    s = p.EDGE_RELIEF * 2 ** 0.5
    part -= Pos(0, (y0 + y1) / 2, 0) * Rot(0, 45, 0) * Box(s, y1 - y0 + 2 * AIR, s)
    band_bottom = -(p.EDGE_RELIEF + p.CONTACT_H)
    part -= box(-AIR, p.FACE_RELIEF, y0 - AIR, y1 + AIR, -p.STOP_H - AIR, band_bottom)
    for y in screw_ys:
        part -= rod(p.SCREW_IN, y, p.SCREW_TAP_D, -p.TAP_L, AIR)
        part -= rod(p.SCREW_IN, y, p.SCREW_LOOSE_D, -p.STOP_H - AIR, -p.TAP_L)
    return part


def side_stop():
    return stop(p.SIDE_STOP_Y0, p.SIDE_STOP_Y1, p.SIDE_STOP_SCREW_Y)


def top_stop():
    # A side-style stop turned a quarter, so its face is on the plane Y = 0:
    # (x, y) -> (-y, x).
    block = stop(-p.TOP_STOP_X1, -p.TOP_STOP_X0, [-x for x in p.TOP_STOP_SCREW_X])
    return Rot(0, 0, 90) * block


def place(part, x0, y0):
    """Move a part so its bounding box starts at (x0, y0, 0)."""
    bb = part.bounding_box()
    return Pos(x0 - bb.min.X, y0 - bb.min.Y, -bb.min.Z) * part


def plate_parts():
    """The jig as it sits on the clock, and the stops beside it upside down,
    so each prints with its screw face on the bed and no supports."""
    j = jig()
    bb = j.bounding_box()
    side = place(Rot(180, 0, 0) * side_stop(), bb.max.X + p.PLATE_GAP, bb.min.Y)
    top = place(Rot(180, 0, 0) * top_stop(), side.bounding_box().max.X + p.PLATE_GAP, bb.min.Y)
    return {"jig": j, "side stop": side, "top stop": top}


def plate():
    """All three parts where they sit on the print bed."""
    return Compound(children=list(plate_parts().values()))
