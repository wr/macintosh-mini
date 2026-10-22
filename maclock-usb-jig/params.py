"""Every dimension of the USB-A cutting jig, in mm.

Coordinates are the clock's, seen from behind with the back shell lying face
down: X to the right, Y up, Z out of the back. X = 0 is the plane of the
clock's flat right side and Y = 0 the plane of its flat top, so the clock is
at X < 0, Y < 0. Z = 0 is the back face the jig sits on, and the print bed.
"""

# --- the clock, measured by Wells on 2026-10-21 -----------------------------

USBC_W = 3.3
"""The USB-C slot's opening, across the clock. It's empty with the back shell
off, so the key drops into it."""
USBC_H = 9.09
"""The USB-C slot's opening, up the clock. It runs upright."""
USBC_EDGE_TO_SIDE = 8.5
"""From the flat side to the slot's nearer long edge."""
USBC_EDGE_TO_TOP = 51.5
"""From the flat top to the slot's top end."""
HOLE_ABOVE_USBC = 38.0
"""USB-A hole's centre to the USB-C slot's centre, straight up."""

SWITCH_W = 4.0
SWITCH_H = 7.0
SWITCH_PROUD = 1.6
"""The fake switch below the hole, the only thing standing proud of the back.
The floor clears it with a wide window."""

SHELL_T = 2.3
"""The back shell's wall: "just about 2mm, maybe a tad thicker"."""

# --- the hole -----------------------------------------------------------------

HOLE_W = 7.0
HOLE_H = 14.0
"""Room for the cable's USB-A socket, which is glued in from inside."""
HOLE_X = -(USBC_EDGE_TO_SIDE + USBC_W / 2)
"""-10.15: in line with the USB-C slot."""
USBC_Y = -(USBC_EDGE_TO_TOP + USBC_H / 2)
"""-56.045: the USB-C slot's centre."""
HOLE_Y = USBC_Y + HOLE_ABOVE_USBC
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
"""Clears the switch, which the first print showed sitting inside this."""

THUMB_W = 24.5
"""A tab of floor out past the left wall, to hold the jig down with a thumb
while cutting. Twice the first print's 18 x 44.5, near enough."""
THUMB_Y0 = -76.0
"""Past the jig's bottom edge, short of the back's lower screw holes."""
THUMB_Y1 = -18.0
"""Clear of the vents and markings at the top left of the back."""

BACK_W = 73.0
BACK_SCREWS_Y = -81.0
"""The back's width, and where its two lower screw holes are: both estimated
from a photo, so the tab keeps a few mm off them."""

# --- USB-C key: anchors the jig in the USB-C slot -------------------------------

KEY_W = 3.1
KEY_L = 8.9
"""0.1 inside the slot all round: holds the jig to a tenth either way, and to
about half a degree of turn."""
KEY_PROUD = 6.0
"""How far the key drops into the slot: through the shell and on into the
empty space behind it. At 2 (a 4 tall key) it jumped out of the slot."""
KEY_SEAT = 2.0
"""How far it presses up into the jig. Leaves 1 of floor over it where the
slot's top end runs under the router's floor."""
KEY_CHAMFER = 0.4
"""Round the end that goes in the slot, to find it."""
KEY_RECESS_W = 3.2
KEY_RECESS_L = 9.0
"""The pocket under the jig. 0.1 over the key, which a printer closes up to a
press fit."""
KEY_SURROUND = 4.0
"""Jig beyond the pocket's bottom end, which takes the jig's bottom edge past
the slot."""
JIG_Y0 = USBC_Y - KEY_RECESS_L / 2 - KEY_SURROUND
"""-64.545: the jig's bottom edge."""

# --- side stop: a block screwed up under the overhang, squaring the jig ---------

STOP_T = 10.0
"""The block's thickness out from the clock's side."""
STOP_H = 29.0
"""How far the block hangs below the back."""
EDGE_RELIEF = 4.0
"""45-degree cut along the block's bottom inside edge, to slide it down the
side."""
CONTACT_H = 6.0
"""The block touches the side over this band, just above the bottom cut. The
first print sat steadiest touching low down like this: fitted the other way
up, touching near the back, it rocked."""
FACE_RELIEF = 1.5
"""Above the band the face stands back by this, clear of the clock's rounded
edge, and steps out to the band on a 45-degree ramp so it prints without a
ledge."""

SIDE_STOP_Y0 = -24.0
SIDE_STOP_Y1 = -6.0
"""Near the top, as far from the key as the side allows, so it sets the jig's
angle with the most leverage. The key sets where the jig is."""
SIDE_STOP_SCREW_Y = (-20.0, -10.0)

SCREW_IN = 6.5
"""Screw centres in from the clock's side. Off-centre in the block, so it
can't go on facing the wrong way."""

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
SCREW_HOLE_L = 28.0
"""The block's holes stop 1 short of its bottom, so it only goes on the right
way up; the screw ends 1 short of that."""

PLATE_GAP = 6.0
"""Between parts on the print plate."""
