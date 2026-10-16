"""The screen bezel, as four printed parts on one plate: the frame, the bottom
bar and two Z clips. Every number comes from params.py."""
from build123d import Box, Compound, Cylinder, Pos

import params as p

AIR = 1.0
"""Cuts overshoot outside faces by this much; a boolean whose faces all
coincide returns nothing in OCCT."""


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def hole(cx, cy, z0, z1):
    return Pos(cx, cy, (z0 + z1) / 2) * Cylinder(p.HOLE_D / 2, z1 - z0 + 2 * AIR)


def frame():
    x0, y0 = p.FRAME_X0, p.FRAME_Y0
    x1, y1, top = x0 + p.FRAME_W, y0 + p.FRAME_H, p.FRAME_T
    lo, hi = -AIR, top + AIR
    part = box(x0, x1, y0, y1, 0, top)
    part -= box(p.WINDOW_X0, p.WINDOW_X0 + p.WINDOW_W,
                p.WINDOW_Y0, p.WINDOW_Y0 + p.WINDOW_H, lo, hi)
    part -= box(x0 - AIR, x0 + p.NOTCH_DEPTH, p.NOTCH_Y0, p.NOTCH_Y1, lo, hi)
    for sx in (p.SLOT_LEFT_X0, p.SLOT_RIGHT_X0):
        part -= box(sx, sx + p.SLOT_W, y0 - AIR, p.WINDOW_Y0 + AIR, p.SLOT_Z, hi)
    part -= box(p.POCKET_X0, p.POCKET_X1, y0 - AIR, p.STEP_Y, p.POCKET_Z, hi)
    part -= box(x0 - AIR, x1 + AIR, y0 - AIR, p.STEP_Y, p.TRIM_Z, hi)
    for lx in (p.LUG_LEFT_X0, p.LUG_RIGHT_X0):
        # Overlaps the top wall by AIR so the union fuses instead of touching.
        part += box(lx, lx + p.LUG_W, y1 - AIR, y1 + p.LUG_L, p.LUG_Z, top)
        part -= hole(lx + p.LUG_W / 2, y1 + p.LUG_L / 2, p.LUG_Z, top)
    return part


def bottom_bar():
    x0, x1 = p.BAR_X0, p.BAR_X0 + p.BAR_L
    inner = p.BAR_Y0 + p.FLANGE_W
    part = box(x0, x1, p.BAR_Y0, inner, 0, p.FLANGE_T)
    part += box(x0, x1, p.BAR_WALL_Y0, inner, 0, p.BAR_WALL_T)
    for lx in (x0, x1 - p.LUG_W):
        part += box(lx, lx + p.LUG_W, inner - AIR, inner + p.LUG_L, p.BAR_LUG_Z, p.BAR_WALL_T)
        part -= hole(lx + p.LUG_W / 2, inner + p.LUG_L / 2, p.BAR_LUG_Z, p.BAR_WALL_T)
    return part


def z_clip(x0):
    s, jog = p.CLIP_STROKE, p.CLIP_JOG
    part = box(x0, x0 + s, p.CLIP_Y0, p.CLIP_BAR_Y1, 0, p.CLIP_T)
    part += box(x0, x0 + jog + s, p.CLIP_BAR_Y0, p.CLIP_BAR_Y1, 0, p.CLIP_T)
    part += box(x0 + jog, x0 + jog + s, p.CLIP_BAR_Y0, p.CLIP_Y1, 0, p.CLIP_T)
    return part


def parts():
    return {
        "frame": frame(),
        "bottom bar": bottom_bar(),
        "Z clip, left": z_clip(p.CLIP_X0),
        "Z clip, right": z_clip(p.CLIP_X0 + p.CLIP_PITCH),
    }


def plate():
    """All four parts where they sit on the print bed."""
    return Compound(children=list(parts().values()))
