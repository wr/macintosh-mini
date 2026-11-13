#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# mac_setup_screen.py
#
# The setup screen on the Mac's own display, shown on tty1 in place of Mac OS
# while Wi-Fi setup or the ROM step is under way. It draws whatever
# mac_setup.py puts in status.json (a title, a few lines, maybe a QR code)
# straight to the framebuffer, big enough to read on the 2.8-inch panel, and
# exits once setup is over so the launcher can start the Mac.
# ####################################

import glob
import gzip
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

FONT_DIR = '/usr/share/consolefonts'
FONTS = ('Uni2-TerminusBold24x12.psf.gz', 'Lat15-TerminusBold24x12.psf.gz',
         'Uni2-Terminus24x12.psf.gz', 'Lat15-Terminus24x12.psf.gz')
HEAD_FONTS = ('Uni2-TerminusBold32x16.psf.gz', 'Lat15-TerminusBold32x16.psf.gz',
              'Uni2-Terminus32x16.psf.gz', 'Lat15-Terminus32x16.psf.gz')
FB_DIR = '/sys/class/graphics/fb0'
FB_DEV = '/dev/fb0'
FBCON_ROTATE = '/sys/class/graphics/fbcon/rotate'
DONE_S = 2           # setup must read as over this long before the screen exits
STARTING = {'title': 'Wi-Fi setup', 'step': None, 'icon': 'wifi', 'lines': ['Starting setup…'],
            'qr': None, 'note': None}

# Layout of the 640x480 screen: a classic-Mac window on a dotted desktop.
WINDOW = (28, 22, 612, 458)   # x0, y0, x1, y1 (x1, y1 exclusive)
TITLE_BAR = 26                # height of the striped title bar
BAR_TITLE = 'Macintosh Mini Setup'
LEFT_COL = 250                # QR code or icon, from the window's left edge
PAD = 18                      # inside the window
QR_MAX = 220                  # largest the QR code is drawn, in pixels
ICON_SCALE = 6                # 16-pixel icons drawn 96 pixels wide

# Icons, 16x16, drawn for this project.
ICONS = {
    'wifi': (
        '................',
        '................',
        '.....######.....',
        '...##......##...',
        '.##..........##.',
        '#..............#',
        '......####......',
        '....##....##....',
        '..##........##..',
        '................',
        '......####......',
        '.....#....#.....',
        '................',
        '.......##.......',
        '.......##.......',
        '................'),
    'check': (
        '.....######.....',
        '...##......##...',
        '..#..........#..',
        '.#...........##.',
        '.#..........#.#.',
        '#..........#...#',
        '#.........#....#',
        '#..#.....#.....#',
        '#...#...#......#',
        '#....#.#.......#',
        '.#....#.......#.',
        '.#............#.',
        '..#..........#..',
        '...##......##...',
        '.....######.....',
        '................'),
}


# --- QR code -------------------------------------------------------------------
def qr_matrix(text, run=subprocess.run):
    out = run(['qrencode', '-t', 'ASCII', '-m', '0', '-l', 'M', '-o', '-', text],
              capture_output=True, text=True, check=True).stdout
    return [[line[i] == '#' for i in range(0, len(line) - 1, 2)]
            for line in out.splitlines() if line]


# --- fonts ---------------------------------------------------------------------
class Font:
    def __init__(self, width, height, glyphs):
        self.width = width
        self.height = height
        self.glyphs = glyphs    # char -> list of row ints, leftmost pixel = top bit

    def glyph(self, ch):
        return self.glyphs.get(ch) or [0] * self.height


def load_psf(path):
    raw = Path(path).read_bytes()
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    if raw[:2] == b'\x36\x04':                      # PSF1: 8 px wide
        mode, height = raw[2], raw[3]
        count = 512 if mode & 0x01 else 256
        width, rowbytes, charsize, offset = 8, 1, height, 4
        table = _psf1_table(raw[4 + count * height:], count) if mode & 0x02 else None
    elif raw[:4] == b'\x72\xb5\x4a\x86':            # PSF2
        _, headersize, flags, count, charsize, height, width = struct.unpack('<7I', raw[4:32])
        rowbytes, offset = (width + 7) // 8, headersize
        table = _psf2_table(raw[headersize + count * charsize:], count) if flags & 1 else None
    else:
        raise ValueError(f'not a PSF font: {path}')
    shift = rowbytes * 8 - width
    glyphs = {}
    for i in range(count):
        g = raw[offset + i * charsize: offset + (i + 1) * charsize]
        rows = [int.from_bytes(g[r * rowbytes:(r + 1) * rowbytes], 'big') >> shift
                for r in range(height)]
        chars = table[i] if table else ([chr(i)] if i < 256 else [])
        for ch in chars:
            glyphs.setdefault(ch, rows)
    return Font(width, height, glyphs)


def _psf1_table(data, count):
    table, i = [], 0
    for _ in range(count):
        chars, in_seq = [], False
        while i + 1 < len(data):
            v = data[i] | data[i + 1] << 8
            i += 2
            if v == 0xFFFF:
                break
            if v == 0xFFFE:
                in_seq = True
            elif not in_seq:
                chars.append(chr(v))
        table.append(chars)
    return table


def _psf2_table(data, count):
    table, i = [], 0
    for _ in range(count):
        end = data.find(b'\xff', i)
        if end < 0:
            end = len(data)
        entry = data[i:end].split(b'\xfe')[0]   # sequences after 0xFE are ignored
        table.append(list(entry.decode('utf-8', 'ignore')))
        i = end + 1
    return table


def find_font(font_dir=FONT_DIR, names=FONTS):
    for name in names:
        p = os.path.join(font_dir, name)
        if os.path.exists(p):
            return p
    found = sorted(glob.glob(os.path.join(font_dir, '*Terminus*24x12*')))
    if found:
        return found[0]
    found = sorted(glob.glob(os.path.join(font_dir, '*.psf*')), key=os.path.getsize)
    return found[-1] if found else None


# --- drawing -------------------------------------------------------------------
class Canvas:
    """1 bit per pixel, white unless set."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.data = bytearray(width * height)

    def set(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.data[y * self.width + x] = 1

    def get(self, x, y):
        return self.data[y * self.width + x] == 1

    def fill(self, x, y, w, h, ink=1):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0:
            return
        run = bytes([ink]) * (x1 - x0)
        for yy in range(y0, y1):
            self.data[yy * self.width + x0: yy * self.width + x1] = run


def draw_text(canvas, font, x, y, text, scale=1, ink=1):
    for ch in text:
        for r, row in enumerate(font.glyph(ch)):
            if not row:
                continue
            for b in range(font.width):
                if row & (1 << (font.width - 1 - b)):
                    canvas.fill(x + b * scale, y + r * scale, scale, scale, ink)
        x += font.width * scale


def fit_note(text, chars):
    """Shorten to at most `chars`, never cutting a word."""
    if len(text) <= chars:
        return text
    cut = text[:chars + 1].rsplit(' ', 1)[0]
    return cut if len(cut) <= chars else text[:chars]


def draw_icon(canvas, name, x, y, scale):
    for row_y, row in enumerate(ICONS[name]):
        for col_x, px in enumerate(row):
            if px == '#':
                canvas.fill(x + col_x * scale, y + row_y * scale, scale, scale)


def wrap(text, chars):
    if chars < 1:
        return [text]
    out, cur = [], ''
    for word in text.split(' '):
        while len(word) > chars:          # a word longer than the line
            if cur:
                out.append(cur)
                cur = ''
            out.append(word[:chars])
            word = word[chars:]
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= chars:
            cur += ' ' + word
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    return out


def render(screen, font, width=640, height=480, qr_matrix=qr_matrix, head=None):
    """Draw a setup screen. screen: title, step (1, 2 or None), icon, lines
    (a line starting ** is drawn white on black), qr (text to encode) and note."""
    head = head or font
    c = Canvas(width, height)
    # Dotted desktop: every other pixel, offset on alternate rows.
    even, odd = bytes([1, 0]) * (width // 2), bytes([0, 1]) * (width // 2)
    for y in range(height):
        c.data[y * width:(y + 1) * width] = even if y % 2 == 0 else odd

    x0, y0, x1, y1 = WINDOW
    c.fill(x0 + 4, y0 + 4, x1 - x0, y1 - y0)            # drop shadow
    c.fill(x0, y0, x1 - x0, y1 - y0, 0)                  # window
    for x, y, w, h in ((x0, y0, x1 - x0, 2), (x0, y1 - 2, x1 - x0, 2),
                       (x0, y0, 2, y1 - y0), (x1 - 2, y0, 2, y1 - y0)):
        c.fill(x, y, w, h)

    # Title bar: stripes, a close box, and the title on a white gap.
    for y in range(y0 + 6, y0 + TITLE_BAR - 4, 2):
        c.fill(x0 + 6, y, x1 - x0 - 12, 1)
    c.fill(x0 + 18, y0 + 6, 15, 15, 0)
    for x, y, w, h in ((x0 + 20, y0 + 7, 11, 1), (x0 + 20, y0 + 19, 11, 1),
                       (x0 + 20, y0 + 7, 1, 13), (x0 + 30, y0 + 7, 1, 13)):
        c.fill(x, y, w, h)
    tw = len(BAR_TITLE) * font.width
    tx = (x0 + x1 - tw) // 2
    c.fill(tx - 10, y0 + 2, tw + 20, TITLE_BAR - 2, 0)
    draw_text(c, font, tx, y0 + 2 + (TITLE_BAR - 2 - font.height) // 2, BAR_TITLE)
    c.fill(x0, y0 + TITLE_BAR, x1 - x0, 2)

    body_top, body_bottom = y0 + TITLE_BAR + 2 + PAD, y1 - PAD - font.height - 8
    col_x = x0 + PAD
    col_w = LEFT_COL - PAD

    # Left column: the QR code, or else an icon.
    if screen.get('qr'):
        try:
            m = qr_matrix(screen['qr'])
        except (OSError, subprocess.CalledProcessError):
            m = None
        if m:
            total = len(m) + 4                       # 2-module quiet zone each side
            module = max(1, min(QR_MAX, col_w, body_bottom - body_top) // total)
            size = module * total
            qx = col_x + (col_w - size) // 2
            qy = body_top + (body_bottom - body_top - size) // 2
            for y, row in enumerate(m):
                for x, dark in enumerate(row):
                    if dark:
                        c.fill(qx + (x + 2) * module, qy + (y + 2) * module, module, module)
    elif screen.get('icon') in ICONS:
        size = 16 * ICON_SCALE
        draw_icon(c, screen['icon'], col_x + (col_w - size) // 2,
                  body_top + (body_bottom - body_top - size) // 2, ICON_SCALE)

    # Right column: the headline, then the lines.
    tx0 = x0 + LEFT_COL + 10
    avail = x1 - PAD - 6 - tx0
    # A line starting ** is white on black; one starting ++ gets a tick.
    tick = 32 + 8                                   # check icon at 2x, and a gap
    blocks = [(t, head, '') for t in wrap(screen.get('title') or '', avail // head.width)]
    blocks.append(('', font, ''))
    for line in screen.get('lines') or []:
        kind = line[:2] if line[:2] in ('**', '++') else ''
        text = line[len(kind):]
        width = avail - (12 if kind == '**' else tick if kind == '++' else 0)
        parts = wrap(text, width // font.width)
        blocks += [(t, font, 'indent' if kind == '++' and i else kind) for i, t in enumerate(parts)]
    gap = font.height // 4
    extra = {'**': 6, '++': 32 - font.height}
    total_h = sum(f.height + gap + max(0, extra.get(kind, 0)) for _, f, kind in blocks)
    y = max(body_top, body_top + (body_bottom - body_top - total_h) // 2)
    for text, f, kind in blocks:
        if kind == '**':
            c.fill(tx0, y, len(text) * f.width + 12, f.height + 6)
            draw_text(c, f, tx0 + 6, y + 3, text, ink=0)
            y += 6
        elif kind == '++':
            draw_icon(c, 'check', tx0, y, 2)
            draw_text(c, f, tx0 + tick, y + (32 - f.height) // 2, text)
            y += max(0, 32 - f.height)
        elif kind == 'indent':
            draw_text(c, f, tx0 + tick, y, text)
        else:
            draw_text(c, f, tx0, y, text)
        y += f.height + gap

    # Bottom row: a note on the left, the step on the right.
    by = y1 - PAD - font.height
    step = screen.get('step')
    label = f'Step {step} of 2' if step else ''
    dots_x = x1 - PAD - 6 - 2 * 14
    if screen.get('note'):
        right = dots_x - 10 - len(label) * font.width - 16 if step else x1 - PAD - 6
        draw_text(c, font, x0 + PAD, by, fit_note(screen['note'], (right - x0 - PAD) // font.width))
    if step:
        for i in range(2):
            dx, dy = dots_x + i * 16, by + font.height // 2 - 5
            c.fill(dx, dy, 10, 10)
            if i + 1 != step:
                c.fill(dx + 2, dy + 2, 6, 6, 0)
        draw_text(c, font, dots_x - 10 - len(label) * font.width, by, label)
    return c


# --- framebuffer -----------------------------------------------------------------
def _read(path, default=None):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def fb_geometry(fb_dir=FB_DIR, rotate_path=FBCON_ROTATE):
    fw, fh = (int(v) for v in _read(os.path.join(fb_dir, 'virtual_size')).split(','))
    rot = int(_read(rotate_path, '0') or 0) % 4
    return fw, fh, rot


def blit(canvas, fb_dir=FB_DIR, dev=FB_DEV, rotate_path=FBCON_ROTATE):
    # The console is turned by fbcon to match the panel; a picture written to
    # the framebuffer isn't, so turn it the same way here. Only black and
    # white are drawn, so the colour channel order doesn't matter.
    fw, _, rot = fb_geometry(fb_dir, rotate_path)
    stride = int(_read(os.path.join(fb_dir, 'stride')))
    bpp = int(_read(os.path.join(fb_dir, 'bits_per_pixel')))
    bpx = bpp // 8
    vh = canvas.width if rot in (1, 3) else canvas.height
    black = (0xFF000000).to_bytes(4, 'little') if bpx == 4 else b'\x00' * bpx
    buf = bytearray(b'\xff' * (stride * vh))
    w, h = canvas.width, canvas.height
    data = canvas.data
    i = data.find(1)
    while i >= 0:
        x, y = i % w, i // w
        if rot == 1:
            fx, fy = fw - 1 - y, x
        elif rot == 2:
            fx, fy = fw - 1 - x, vh - 1 - y
        elif rot == 3:
            fx, fy = y, vh - 1 - x
        else:
            fx, fy = x, y
        if 0 <= fx < fw and 0 <= fy < vh:
            off = fy * stride + fx * bpx
            buf[off:off + bpx] = black
        i = data.find(1, i + 1)
    with open(dev, 'r+b') as f:
        f.seek(0)
        f.write(buf)


def show_text(screen):
    # No framebuffer or font: plain console text, so setup is never blind.
    sys.stdout.write('\033[2J\033[H\n  ' + (screen.get('title') or '') + '\n\n')
    for line in screen.get('lines') or []:
        sys.stdout.write('  ' + line + '\n')
    sys.stdout.flush()


def main(status_path, requested_path, poll=0.5):
    status_path, requested_path = Path(status_path), Path(requested_path)
    sys.stdout.write('\033[?25l\033[2J\033[9;0]')   # hide cursor, clear, never blank
    sys.stdout.flush()
    try:
        font = load_psf(find_font())
        head_path = find_font(names=HEAD_FONTS)
        head = load_psf(head_path) if head_path and os.path.exists(head_path) else font
        fw, fh, rot = fb_geometry()
        width, height = (fh, fw) if rot in (1, 3) else (fw, fh)
    except (OSError, ValueError, TypeError, AttributeError):
        font = None
    last, last_draw, done_since = None, 0.0, None
    while True:
        try:
            status = json.loads(status_path.read_text())
        except (OSError, ValueError):
            status = None
        screen = status.get('screen') if status else STARTING
        phase = status.get('phase') if status else None
        done = phase == 'starting' or (phase == 'off' and not requested_path.exists())
        now = time.monotonic()
        if done:
            done_since = done_since or now
            if now - done_since >= DONE_S:
                sys.stdout.write('\033[2J\033[?25h')
                sys.stdout.flush()
                return 0
        else:
            done_since = None
            # Redraw on change, and now and then in case the console drew over it.
            if screen != last or now - last_draw > 60:
                try:
                    if font is None:
                        raise OSError('no font')
                    blit(render(screen, font, width, height, head=head))
                except (OSError, ValueError):
                    show_text(screen)
                last, last_draw = screen, now
        time.sleep(poll)
