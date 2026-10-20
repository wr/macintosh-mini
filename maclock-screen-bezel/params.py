"""Every dimension of the screen bezel, in mm.

The bezel was drawn in Tinkercad, and these numbers were read off its STL
export (maclock-screen-bezel.stl as of 2026-05-13) on 2026-10-15, to 0.001 mm:
each layer of the part was cross-sectioned and its outline taken edge by edge.
The odd thousandths (31.795, 64.005) are Tinkercad's, kept so the rebuild is
the same part. Rounding them is a design change; print one before committing it.

Coordinates are the STL's, so the four parts sit on the print plate where they
always have. Z = 0 is the print bed.
"""

# --- frame: frames the LCD, screws into the clock's screen posts at the top --

FRAME_X0 = -28.100
"""Frame's left outside edge."""
FRAME_Y0 = -27.855
"""Frame's bottom outside edge (the edge with the clips)."""
FRAME_W = 71.100
FRAME_H = 59.650
FRAME_T = 5.000

WINDOW_W = 66.106
"""The LCD opening. Snug on the Waveshare 2.8-inch panel: the build guide says to
sand the inner edges if the panel has to be forced, since a tight bezel can
crack it."""
WINDOW_H = 47.906
WINDOW_X0 = -26.703
"""1.397 in from the frame's left edge; the right wall is 3.597."""
WINDOW_Y0 = -19.158
"""8.697 up from the frame's bottom edge; the top wall is 3.047."""

NOTCH_DEPTH = 0.702
"""Notch in the left outside edge, full height."""
NOTCH_Y0 = -19.161
NOTCH_Y1 = -10.656

STEP_Y = -21.498
"""Line across the bottom bar, 6.357 up from its bottom edge. The pocket stops
at it, and above TRIM_Z the bar is cut back to it."""
TRIM_Z = 4.498

SLOT_W = 4.005
"""Two slots through the bottom bar, from SLOT_Z up, open into the window."""
SLOT_Z = 2.498
SLOT_LEFT_X0 = -26.303
"""0.400 in from the window's left edge."""
SLOT_RIGHT_X0 = 34.498
"""Ends 0.900 in from the window's right edge."""

POCKET_X0 = 14.498
POCKET_X1 = 34.503
"""Pocket in the bottom bar's outside edge, from POCKET_Z up to STEP_Y."""
POCKET_Z = 1.998

LUG_W = 4.000
"""Screw lugs on the frame's top edge, for the clock's original screen posts."""
LUG_L = 3.200
LUG_Z = 3.000
"""Lugs run from here to the top of the frame, 2.000 thick."""
LUG_LEFT_X0 = -25.000
LUG_RIGHT_X0 = 39.000
"""Flush with the frame's right edge. Hole centres are 64.000 apart."""
HOLE_D = 2.000
"""Screw holes, frame and bar. Tinkercad's 48-sided cylinder; a true circle
here."""

# --- bottom bar: a separate part, printed beside the frame ------------------

BAR_X0 = -28.205
BAR_L = 68.005
BAR_Y0 = -40.400
"""Outside edge of the flange."""
FLANGE_W = 6.000
FLANGE_T = 1.198
BAR_WALL_Y0 = -36.448
"""The wall runs from here to the flange's inside edge (2.048 thick)."""
BAR_WALL_T = 3.000
BAR_LUG_Z = 1.800
"""The bar's lugs run from here to the top of its wall, 1.200 thick, flush
with its ends. Hole centres are 64.005 apart."""

# --- Z clips: two separate parts, printed inside the frame's window ---------

CLIP_X0 = -23.600
"""Left edge of the first clip; the second is CLIP_PITCH to its right."""
CLIP_PITCH = 9.100
CLIP_STROKE = 2.000
CLIP_Y0 = -15.300
"""Bottom of the lower leg."""
CLIP_BAR_Y0 = -9.200
"""The cross bar runs from here to CLIP_BAR_Y1."""
CLIP_BAR_Y1 = -6.800
CLIP_JOG = 4.500
"""How far right the upper leg sits from the lower one."""
CLIP_Y1 = -0.300
"""Top of the upper leg."""
CLIP_T = 4.000
