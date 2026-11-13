#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later

# ####################################
# extract_icons.py
#
# Copies the Finder icons of the apps the guide lists out of our Mac OS 8.1
# disk image (disk-image/ in this repo) into icons/, at 4x so they print sharp.
# An app with no icon of its own gets the generic application icon, as the
# Finder shows it.
#
# Usage: extract_icons.py IMAGE   (needs machfs and Pillow)
# ####################################

import os
import struct
import sys

import machfs
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC_APP = -3996   # in the System file
APPS = {
    'icab': 'Internet:iCab:iCab',
    'mr-browser': 'Internet:MR Browser 68K v0.39',
    'after-dark': 'System Folder:Control Panels:After Dark',
    'big-maclock': 'Applications:Big Maclock:BigMaclock',
    'stuffit-expander': 'Utilities:StuffIt Expander™',
    'disk-copy': 'Utilities:Disk Copy',
    'imagewriter': 'System Folder:Extensions:AppleTalk ImageWriter',
}


def mac_palette():
    """The standard 8-bit colour table: a 6x6x6 cube without black, then red,
    green, blue and grey ramps, then black."""
    levels = [0xFF, 0xCC, 0x99, 0x66, 0x33, 0x00]
    ramp = [0xEE, 0xDD, 0xBB, 0xAA, 0x88, 0x77, 0x55, 0x44, 0x22, 0x11]
    pal = [(r, g, b) for r in levels for g in levels for b in levels][:-1]
    pal += [(v, 0, 0) for v in ramp] + [(0, v, 0) for v in ramp] + [(0, 0, v) for v in ramp]
    return pal + [(v, v, v) for v in ramp] + [(0, 0, 0)]


def resources(fork):
    """{(type, id): data} for a resource fork."""
    if len(fork) < 16:
        return {}
    data_off, map_off = struct.unpack('>II', fork[:8])
    types = map_off + struct.unpack('>H', fork[map_off + 24:map_off + 26])[0]
    out = {}
    for i in range(struct.unpack('>H', fork[types:types + 2])[0] + 1):
        rtype, count, refs = struct.unpack('>4sHH', fork[types + 2 + i * 8:types + 10 + i * 8])
        for j in range(count + 1):
            e = types + refs + j * 12
            rid, _, attrs_off = struct.unpack('>hHI', fork[e:e + 8])
            off = data_off + (attrs_off & 0xFFFFFF)
            out[(rtype, rid)] = fork[off + 4:off + 4 + struct.unpack('>I', fork[off:off + 4])[0]]
    return out


def own_icon(res, ftype, creator):
    """The ICN# id of a file's own icon: its BNDL maps the FREF for its type
    to a local icon id, and that to the real one."""
    for (rtype, _), d in res.items():
        if rtype != b'BNDL' or d[:4] != creator:
            continue
        p, maps = 8, {}
        for _ in range(struct.unpack('>H', d[6:8])[0] + 1):
            mtype, count = d[p:p + 4], struct.unpack('>H', d[p + 4:p + 6])[0] + 1
            maps[mtype] = dict(struct.unpack('>hh', d[p + 6 + k * 4:p + 10 + k * 4]) for k in range(count))
            p += 6 + count * 4
        for fref in maps.get(b'FREF', {}).values():
            f = res.get((b'FREF', fref))
            if f and f[:4] == ftype:
                return maps.get(b'ICN#', {}).get(struct.unpack('>h', f[4:6])[0])
    return None


def draw(res, rid, pal):
    """The 8-bit icon (icl8) where there is one, else the black-and-white
    one, through the mask in the ICN#."""
    icn, icl8 = res[(b'ICN#', rid)], res.get((b'icl8', rid))
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    for y in range(32):
        for x in range(32):
            bit = 0x80 >> (x % 8)
            if not icn[128 + y * 4 + x // 8] & bit:
                continue
            if icl8:
                img.putpixel((x, y), pal[icl8[y * 32 + x]] + (255,))
            else:
                img.putpixel((x, y), (0, 0, 0, 255) if icn[y * 4 + x // 8] & bit else (255, 255, 255, 255))
    return img.resize((128, 128), Image.NEAREST)


def main(image):
    vol = machfs.Volume()
    with open(image, 'rb') as f:
        vol.read(f.read())

    def find(path):
        node = vol
        for part in path.split(':'):
            node = node[part]
        return node

    pal = mac_palette()
    system = resources(find('System Folder:System').rsrc)
    os.makedirs(os.path.join(HERE, 'icons'), exist_ok=True)
    for name, path in APPS.items():
        f = find(path)
        res = resources(f.rsrc)
        rid = own_icon(res, f.type, f.creator)
        img = draw(res, rid, pal) if rid is not None else draw(system, GENERIC_APP, pal)
        img.save(os.path.join(HERE, 'icons', f'{name}.png'), optimize=True)


if __name__ == '__main__':
    main(sys.argv[1])
