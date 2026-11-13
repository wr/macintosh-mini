#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# render_screens.py
#
# Draws the setup screens shown in the guide with the Mac's own code
# (maclock-build/mac_setup_screen.py), at 3x so they print sharp. Their QR
# codes are look-alikes that don't scan, so nobody joins a network from paper.
#
# Usage: render_screens.py FONT_DIR
#   FONT_DIR holds the Terminus console fonts (a Pi's /usr/share/consolefonts).
#   Needs Pillow.
# ####################################

import os
import random
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'maclock-build'))
import mac_setup_screen as screen  # noqa: E402

SCREENS = {
    'screen-wifi': (7, {'title': 'Set up Wi-Fi', 'step': 1, 'icon': None, 'note': None, 'qr': 'x',
                        'lines': ['Join this Wi-Fi network', 'on your phone:', '**Macintosh Mini 4E2A', '',
                                  'or scan the code.']}),
    'screen-rom': (11, {'title': 'Add a ROM', 'step': 2, 'icon': None, 'note': None, 'qr': 'x',
                        'lines': ['++Wi-Fi connected.', '', 'Scan the code, or open', '**http://192.168.1.42',
                                  'on a computer.']}),
}


def fake_qr(seed, n=29):
    """Random modules with the three corner squares: looks like a QR code, doesn't scan."""
    rnd = random.Random(seed)
    grid = [[rnd.random() < .5 for _ in range(n)] for _ in range(n)]
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        for r in range(-1, 8):
            for c in range(-1, 8):
                if 0 <= r0 + r < n and 0 <= c0 + c < n:
                    ring = max(abs(r - 3), abs(c - 3))
                    grid[r0 + r][c0 + c] = 0 <= r < 7 and 0 <= c < 7 and ring != 2
    return grid


def main(font_dir):
    font = screen.load_psf(os.path.join(font_dir, 'Uni2-TerminusBold24x12.psf.gz'))
    head = screen.load_psf(os.path.join(font_dir, 'Uni2-TerminusBold32x16.psf.gz'))
    for name, (seed, s) in SCREENS.items():
        c = screen.render(s, font, 640, 480, qr_matrix=lambda _text, seed=seed: fake_qr(seed), head=head)
        img = Image.new('1', (c.width, c.height))
        img.putdata([0 if v else 1 for v in c.data])
        img.resize((c.width * 3, c.height * 3), Image.NEAREST).save(os.path.join(HERE, f'{name}.png'), optimize=True)


if __name__ == '__main__':
    main(sys.argv[1])
