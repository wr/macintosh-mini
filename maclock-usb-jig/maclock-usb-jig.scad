// Macintosh Mini USB port jig
// A printed guide for cutting a USB port into the Maclock's back shell with a
// Dremel in its router base. Set your hole, your Dremel and your printer
// below, then render and export an STL.
//
// https://github.com/wr/macintosh-mini/tree/main/maclock-usb-jig
// SPDX-FileCopyrightText: 2026 Wells Riley
// SPDX-License-Identifier: CERN-OHL-S-2.0
//
// params.py and jig.py build the same parts from the same numbers; the
// tests check the two agree.

/* [Print] */

// Which part to make. All four fit on one plate, and print without supports.
part = "all"; // [all:All parts on one plate, jig:Jig only, key:Key only, stop:Side stop only, post:Post only]

/* [The hole] */

// Across the clock, in mm. 7 fits a USB-A socket. If your first hole comes out tight, add a few tenths.
hole_width = 7; // [4:0.1:12]

// Up the clock, in mm. 14 fits a USB-A socket standing upright.
hole_height = 14; // [4:0.1:16]

/* [Your Dremel] */

// Across the router base's round foot, in mm.
foot_diameter = 60; // [40:0.5:80]

// Across the flat-ended cutting bit, in mm. No wider than the hole.
bit_diameter = 3; // [1.5:0.05:4]

/* [Your printer] */

// Gap each side of the pockets the key and the post press into, in mm. Bigger is looser.
press_fit = 0.05; // [0:0.01:0.3]

/* [Hidden] */

// Everything below is the clock, measured, and the jig's fixed parts. The
// names match params.py, which explains each one.
//
// Coordinates are the clock's, seen from behind with the back shell lying
// face down: X to the right, Y up, Z out of the back. X = 0 is the clock's
// flat right side and Y = 0 its flat top. Z = 0 is the back face the jig
// sits on.

$fn = 96;
AIR = 1;

HOLE_W = hole_width;
HOLE_H = hole_height;
FOOT_D = foot_diameter;
BIT_D = bit_diameter;
PRESS_FIT = press_fit;

// The clock
USBC_W = 3.3;
USBC_H = 9.09;
USBC_EDGE_TO_SIDE = 8.5;
USBC_EDGE_TO_TOP = 51.5;
HOLE_ABOVE_USBC = 38;
SWITCH_PROUD = 1.6;
SHELL_T = 2.3;
BACK_W = 73;

// The hole
HOLE_X = -(USBC_EDGE_TO_SIDE + USBC_W / 2);
USBC_Y = -(USBC_EDGE_TO_TOP + USBC_H / 2);
HOLE_Y = USBC_Y + HOLE_ABOVE_USBC;

// The jig
FLOOR_T = 3;
WALL_H = 4;
WALL_W = 4;
POCKET_W = HOLE_W + FOOT_D - BIT_D;
POCKET_H = HOLE_H + FOOT_D - BIT_D;
BIT_WINDOW_MARGIN = 3;
SWITCH_WINDOW_W = 8;
SWITCH_WINDOW_Y0 = -48;
SWITCH_WINDOW_Y1 = -30;
THUMB_W = 24.5;
THUMB_Y0 = -76;
THUMB_Y1 = -18;
THUMB_X_MIN = -71;

// USB-C key
KEY_W = 3.1;
KEY_L = 8.9;
KEY_PROUD = 6;
KEY_SEAT = 2;
KEY_CHAMFER = 0.4;
KEY_RECESS_W = KEY_W + 2 * PRESS_FIT;
KEY_RECESS_L = KEY_L + 2 * PRESS_FIT;
KEY_SURROUND = 4;
JIG_Y0 = min(USBC_Y - KEY_RECESS_L / 2 - KEY_SURROUND,
             HOLE_Y - POCKET_H / 2 - WALL_W);

// Post
PRINTED_JIG_LEFT = -46.15;
PRINTED_JIG_TOP = 21.455;
HANDHOLD_CORNER_X = PRINTED_JIG_LEFT + 22.3;
HANDHOLD_CORNER_Y = PRINTED_JIG_TOP - 20.65;
POST_W = 4;
POST_CLEAR = 0.2;
POST_CHAMFER = 0.5;
POST_SEAT = 2;
POST_PROUD = 5;
POST_RECESS_CLEAR = PRESS_FIT;

// Side stop
STOP_T = 10;
STOP_H = 29;
EDGE_RELIEF = 4;
CONTACT_H = 6;
FACE_RELIEF = 1.5;
SIDE_STOP_Y0 = -24;
SIDE_STOP_Y1 = -6;
SIDE_STOP_SCREW_Y = [-20, -10];
SCREW_IN = 6.5;

// M3 x 30 countersunk screws
SCREW_CLEAR_D = 3.2;
SINK_D = 6.4;
SCREW_TAP_D = 2.6;
TAP_L = 12;
SCREW_LOOSE_D = 3.4;
SCREW_HOLE_L = 28;

PLATE_GAP = 6;

assert(HOLE_W >= BIT_D, "The bit can't be wider than the hole.");
assert(HOLE_H >= BIT_D, "The bit can't be taller than the hole.");

// --- where things are --------------------------------------------------------

// The pocket the router base's foot slides in.
PX0 = HOLE_X - POCKET_W / 2;
PX1 = HOLE_X + POCKET_W / 2;
PY0 = HOLE_Y - POCKET_H / 2;
PY1 = HOLE_Y + POCKET_H / 2;
TOP = FLOOR_T + WALL_H;
LEFT = PX0 - WALL_W;
TAB_X0 = max(LEFT - THUMB_W, THUMB_X_MIN);
HAS_TAB = TAB_X0 < LEFT;

// The post: in the hand-hold, against its end and above the top.
POST_X1 = HANDHOLD_CORNER_X - POST_CLEAR;
POST_X0 = POST_X1 - POST_W;
POST_Y0 = HANDHOLD_CORNER_Y + POST_CLEAR;
POST_Y1 = POST_Y0 + POST_W;

// The jig's outline, to lay the other parts out beside it.
JIG_MIN_X = HAS_TAB ? TAB_X0 : LEFT;
JIG_MAX_X = PX1 + WALL_W;
JIG_MIN_Y = HAS_TAB ? min(JIG_Y0, THUMB_Y0) : JIG_Y0;

// --- shapes ------------------------------------------------------------------

module box(x0, x1, y0, y1, z0, z1) {
    translate([x0, y0, z0]) cube([x1 - x0, y1 - y0, z1 - z0]);
}

module rod(x, y, d, z0, z1) {
    translate([x, y, z0]) cylinder(d = d, h = z1 - z0);
}

// An upright stadium w across and l tall, centred on the USB-C slot, with
// its bottom edge chamfered by c.
module slot(w, l, z0, z1, c = 0) {
    r = w / 2;
    translate([HOLE_X, USBC_Y, 0]) hull() for (s = [-1, 1]) translate([0, s * (l / 2 - r), 0]) {
        if (c > 0) translate([0, 0, z0]) cylinder(h = c, r1 = r - c, r2 = r);
        translate([0, 0, z0 + c]) cylinder(h = z1 - z0 - c, r = r);
    }
}

module countersunk(x, y) {
    top_r = SINK_D / 2 + AIR;
    depth = top_r - SCREW_CLEAR_D / 2;
    translate([x, y, FLOOR_T + AIR - depth]) cylinder(h = depth, r1 = SCREW_CLEAR_D / 2, r2 = top_r);
    rod(x, y, SCREW_CLEAR_D, -AIR, FLOOR_T + AIR);
}

// --- the parts, where they sit on the clock ----------------------------------

module jig() {
    m = BIT_WINDOW_MARGIN;
    sw = SWITCH_WINDOW_W / 2;
    c = POST_RECESS_CLEAR;
    difference() {
        union() {
            box(LEFT, JIG_MAX_X, JIG_Y0, PY1 + WALL_W, 0, TOP);
            // Thumb tab, overlapping the left wall by AIR so the union fuses.
            if (HAS_TAB) box(TAB_X0, LEFT + AIR, THUMB_Y0, THUMB_Y1, 0, FLOOR_T);
        }
        box(PX0, PX1, PY0, PY1, FLOOR_T, TOP + AIR);
        // Window under the bit, to tip it in and start the cut.
        box(HOLE_X - HOLE_W / 2 - m, HOLE_X + HOLE_W / 2 + m,
            HOLE_Y - HOLE_H / 2 - m, HOLE_Y + HOLE_H / 2 + m, -AIR, TOP + AIR);
        // Clears the fake switch below the hole. Only floor deep, so a small
        // foot's bottom wall stays standing over it.
        box(HOLE_X - sw, HOLE_X + sw, SWITCH_WINDOW_Y0, SWITCH_WINDOW_Y1, -AIR, FLOOR_T);
        slot(KEY_RECESS_W, KEY_RECESS_L, -AIR, KEY_SEAT);
        box(POST_X0 - c, POST_X1 + c, POST_Y0 - c, POST_Y1 + c, -AIR, POST_SEAT);
        for (y = SIDE_STOP_SCREW_Y) countersunk(SCREW_IN, y);
    }
}

// Hangs under the jig's right edge, its face on the plane X = 0 against the
// clock's flat side.
module side_stop() {
    y0 = SIDE_STOP_Y0;
    y1 = SIDE_STOP_Y1;
    yc = (y0 + y1) / 2;
    yl = y1 - y0 + 2 * AIR;
    band_top = -(STOP_H - EDGE_RELIEF - CONTACT_H);
    ramp_top = band_top + FACE_RELIEF;
    difference() {
        box(0, STOP_T, y0, y1, -STOP_H, 0);
        // 45-degree cuts along the inside face: one at the bottom edge, and
        // one ramping the face back from the contact band to FACE_RELIEF.
        translate([0, yc, -STOP_H]) rotate([0, 45, 0])
            cube([EDGE_RELIEF * sqrt(2), yl, EDGE_RELIEF * sqrt(2)], center = true);
        translate([0, yc, ramp_top]) rotate([0, 45, 0])
            cube([FACE_RELIEF * sqrt(2), yl, FACE_RELIEF * sqrt(2)], center = true);
        box(-AIR, FACE_RELIEF, y0 - AIR, y1 + AIR, ramp_top, AIR);
        for (y = SIDE_STOP_SCREW_Y) {
            rod(SCREW_IN, y, SCREW_TAP_D, -TAP_L, AIR);
            rod(SCREW_IN, y, SCREW_LOOSE_D, -SCREW_HOLE_L, -TAP_L);
        }
    }
}

// Presses KEY_SEAT up into the jig and drops KEY_PROUD into the USB-C slot.
module key() {
    slot(KEY_W, KEY_L, -KEY_PROUD, KEY_SEAT, KEY_CHAMFER);
}

// Presses POST_SEAT up into the jig and hangs POST_PROUD into the corner of
// the hand-hold, with the corner that goes into the clock's corner cut off.
module post() {
    c = POST_CHAMFER;
    translate([0, 0, -POST_PROUD]) linear_extrude(POST_SEAT + POST_PROUD)
        polygon([[POST_X0, POST_Y0], [POST_X1 - c, POST_Y0], [POST_X1, POST_Y0 + c],
                 [POST_X1, POST_Y1], [POST_X0, POST_Y1]]);
}

// --- the print plate ---------------------------------------------------------

// Turn a part over (180 degrees about X), so the end that meets the jig is on
// the bed, and move its outline's corner from (x0, y0, z0) to (x, y, 0).
module flipped(x0, y0, z0, x, y) {
    translate([x - x0, y - y0, -z0]) rotate([180, 0, 0]) children();
}

STOP_X = JIG_MAX_X + PLATE_GAP;
KEY_X = STOP_X + STOP_T + PLATE_GAP;
POST_X = KEY_X + KEY_W + PLATE_GAP;

// Each flipped part's outline corner, after the turn: y and z change sign.
module plate_stop(x, y) flipped(0, -SIDE_STOP_Y1, 0, x, y) side_stop();
module plate_key(x, y) flipped(HOLE_X - KEY_W / 2, -(USBC_Y + KEY_L / 2), -KEY_SEAT, x, y) key();
module plate_post(x, y) flipped(POST_X0, -POST_Y1, -POST_SEAT, x, y) post();

if (part == "all") {
    jig();
    plate_stop(STOP_X, JIG_MIN_Y);
    plate_key(KEY_X, JIG_MIN_Y);
    plate_post(POST_X, JIG_MIN_Y);
} else if (part == "jig") {
    translate([-JIG_MIN_X, -JIG_MIN_Y, 0]) jig();
} else if (part == "stop") {
    plate_stop(0, 0);
} else if (part == "key") {
    plate_key(0, 0);
} else if (part == "post") {
    plate_post(0, 0);
}
