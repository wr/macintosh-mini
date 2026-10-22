"""Every dimension of the USB-A cutting jig, in mm.

Coordinates are the clock's, seen from behind with the back shell lying face
down: X to the right, Y up, Z out of the back. X = 0 is the plane of the
clock's flat right side and Y = 0 the plane of its flat top, so the clock is
at X < 0, Y < 0. Z = 0 is the back face the jig sits on, and the print bed.
"""

# --- the clock, measured by Wells on 2026-10-21 -----------------------------

USBC_W = 3.3
"""The USB-C slot's opening, across the clock."""
USBC_H = 9.09
"""The USB-C slot's opening, up the clock. It runs upright."""
USBC_EDGE_TO_SIDE = 8.5
"""From the flat side to the slot's nearer long edge."""
USBC_EDGE_TO_TOP = 51.5
"""From the flat top, at the hand-hold, to the slot's top end."""
HOLE_ABOVE_USBC = 38.0
"""USB-A hole's centre to the USB-C slot's centre, straight up."""

HANDHOLD_IN = 24.0
"""The hand-hold in the top starts this far in from the flat side."""
HANDHOLD_W = 32.0
"""Elsewhere the top slopes down into vents, so the top stop goes here."""

SWITCH_W = 4.0
SWITCH_H = 7.0
SWITCH_PROUD = 1.6
"""The fake switch below the hole, the only thing standing proud of the back.
Its position is an estimate (about 10 below the hole), so the floor clears it
with a wide window instead of locating on it."""

SHELL_T = 2.3
"""The back shell's wall: "just about 2mm, maybe a tad thicker"."""

# --- the hole -----------------------------------------------------------------

HOLE_W = 7.0
HOLE_H = 14.0
"""Room for the cable's USB-A socket, which is glued in from inside."""
HOLE_X = -(USBC_EDGE_TO_SIDE + USBC_W / 2)
"""-10.15: in line with the USB-C slot."""
HOLE_Y = -(USBC_EDGE_TO_TOP + USBC_H / 2) + HOLE_ABOVE_USBC
"""-18.045."""

# --- the Dremel ---------------------------------------------------------------

FOOT_D = 60.0
"""The router base's round foot."""
FOOT_EDGE_H = 6.0
"""How tall the foot's rim is before it slopes in."""
BIT_D = 3.0
"""Flat-ended cutter on a 3.2 shank."""
BIT_CUT_L = 6.5
"""Length of the cutting head; the floor and the shell must fit inside it."""

# --- the jig --------------------------------------------------------------------

FLOOR_T = 3.0
"""The router foot glides on the floor's top."""
WALL_H = 4.0
"""Above the floor. Under FOOT_EDGE_H, so the walls meet the foot's rim, not
its slope."""
WALL_W = 4.0

POCKET_W = HOLE_W + FOOT_D - BIT_D
"""64. The foot touching a wall puts the bit's edge on the hole's edge."""
POCKET_H = HOLE_H + FOOT_D - BIT_D
"""71."""

BIT_WINDOW_MARGIN = 3.0
"""The window under the bit is this much bigger than the hole all round, so the
bit can be tipped in to start the cut."""

SWITCH_WINDOW_W = 8.0
SWITCH_WINDOW_Y0 = -48.0
SWITCH_WINDOW_Y1 = -30.0
"""Clears the switch wherever it sits between the bit window and the USB-C
slot."""

# --- stops: printed blocks screwed up under the overhang ------------------------

STOP_T = 10.0
"""Each block's thickness out from the clock face it touches."""
STOP_H = 28.0
"""How far the blocks hang below the back; the screws end 1 inside."""
EDGE_RELIEF = 4.0
"""45-degree cut along each block's top inside edge, clear of the clock's
rounded edge."""
CONTACT_H = 6.0
"""Each block touches its clock face over this band, just below the relief.
Below it the face steps back by FACE_RELIEF, so a drafted side can't push the
jig off."""
FACE_RELIEF = 1.5

SIDE_STOP_Y0 = -52.0
SIDE_STOP_Y1 = -6.0
"""Along the flat side."""
SIDE_STOP_SCREW_Y = (-46.0, -12.0)

TOP_STOP_X0 = -42.0
TOP_STOP_X1 = -28.0
"""Along the flat top, inside the hand-hold."""
TOP_STOP_SCREW_X = (-38.5, -31.5)

SCREW_IN = 6.5
"""Screw centres in from the clock face each block touches."""

# --- M3 x 30 countersunk screws (DIN 7991) --------------------------------------

SCREW_L = 30.0
"""Overall, head included."""
SCREW_HEAD_D = 6.0
SCREW_CLEAR_D = 3.2
"""Through the floor."""
SINK_D = 6.4
"""Countersink at the floor's top, 90 degrees: the head sits 0.2 below the
surface, so the foot glides over it."""
SCREW_TAP_D = 2.6
"""The screw cuts its own thread in the block, for TAP_L ..."""
TAP_L = 12.0
SCREW_LOOSE_D = 3.4
"""... and runs loose below that, so it's not hard to drive."""

PLATE_GAP = 6.0
"""Between parts on the print plate."""
