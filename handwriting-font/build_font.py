#!/usr/bin/env python3
"""Build the "Julia Age 3" font from a photo of a filled-in handwriting sheet.

Pipeline:
  1. Even out the lighting of the photo.
  2. Find the printed grid lines and fit each one with a curve (the paper is not flat).
  3. Find the marker strokes, ignore the thin printed labels and grid lines, and
     assign each stroke to the cell it was written in.
  4. Straighten each cell with its own perspective transform and cut the glyph out at 4x.
  5. Trace each glyph with potrace and assemble an OpenType font (OTF, TTF and WOFF2).

Needs: python3 with opencv-python-headless, numpy, fonttools, brotli; the potrace binary.
Usage: python3 build_font.py            (writes fonts/ and build/)
"""
import os, re, subprocess, tempfile
import xml.etree.ElementTree as ET

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PHOTO = os.path.join(HERE, 'source', 'julia-handwriting-sheet.jpg')
BUILD = os.path.join(HERE, 'build')
FONTS = os.path.join(HERE, 'fonts')

# The sheet, row by row, as printed on it. Only the first seven rows were filled in.
ROWS = [
    'ABCDEFGHIJ',
    'KLMNOPQRST',
    'UVWXYZ?!%&',
    'abcdefghij',
    'klmnopqrst',
    'uvwxyz:;.,',
    '0123456789',
]

# Rough outer corners of the printed table in the photo (TL, TR, BR, BL). Only used to
# keep the line search off the desk around the paper.
TABLE_QUAD = [(145, 130), (1331, 149), (1347, 1906), (110, 1903)]

UP = 4            # cut glyphs out at 4x the photo's resolution for smooth outlines
CELL_W = 127.0    # a cell's writing area in photo pixels (measured on the flat, lower part)
CELL_H = 126.0
INK = 160         # threshold on the lighting-corrected image (paper ~225, marker ~20-140)


def normalize(gray):
    """Divide out the uneven lighting so the paper is ~white everywhere."""
    g = gray.astype(np.float32)
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    bg = cv2.GaussianBlur(bg, (0, 0), 15)
    return (np.clip(g / np.maximum(bg, 1), 0, 1) * 255).astype(np.uint8)


def fit_lines(norm):
    """Return curved fits for the long horizontal (y=f(x)) and vertical (x=f(y)) grid lines."""
    quad = np.array(TABLE_QUAD, np.int32)
    tm = np.zeros_like(norm)
    cv2.fillPoly(tm, [quad], 1)
    tm = cv2.dilate(tm, np.ones((15, 15), np.uint8))
    m = ((norm < 190) & (tm > 0)).astype(np.uint8) * 255
    hmask = cv2.morphologyEx(cv2.dilate(m, np.ones((3, 1), np.uint8)), cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1)))
    vmask = cv2.morphologyEx(cv2.dilate(m, np.ones((1, 3), np.uint8)), cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80)))

    def segments(mask, horiz):
        k, lab, st, _ = cv2.connectedComponentsWithStats(mask)
        out = []
        for i in range(1, k):
            length = st[i, 2] if horiz else st[i, 3]
            if length < 150:
                continue
            ys, xs = np.nonzero(lab == i)
            a, b = (xs, ys) if horiz else (ys, xs)
            out.append((np.polyfit(a, b, 2 if length > 500 else 1), a, b))
        return out

    def merge(segs, mid):
        segs = sorted(segs, key=lambda s: np.polyval(s[0], mid))
        groups = []
        for s in segs:
            v = np.polyval(s[0], mid)
            if groups and abs(v - groups[-1][0]) < 7:
                groups[-1][1].append(s)
            else:
                groups.append([v, [s]])
        fits = []
        for _, ss in groups:
            a = np.concatenate([s[1] for s in ss]); b = np.concatenate([s[2] for s in ss])
            fits.append((np.polyfit(a, b, 2), a.max() - a.min()))
        return fits

    hl = [p for p, span in merge(segments(hmask, True), 728) if span > 1000]
    vl = [p for p, span in merge(segments(vmask, False), 1000) if span > 1000]
    # Expected: the title's bottom line = row 1's label top, then label-top / writing-top pairs.
    assert len(hl) >= 16, f'found {len(hl)} full-width horizontal lines'
    assert len(vl) == 9, f'found {len(vl)} interior vertical lines'
    return hl[:16], vl


class Grid:
    def __init__(self, hl, vl):
        self.hl, self.vl = hl, vl

    def label_top(self, r): return self.hl[2 * r]
    def writing_top(self, r): return self.hl[2 * r + 1]

    def vx(self, c, y):
        """x of vertical grid line c (0 = left border, 10 = right border) at height y."""
        vl = self.vl
        if 1 <= c <= 9:
            return np.polyval(vl[c - 1], y)
        if c == 0:   # the outer borders curl with the paper; extrapolate from the interior lines
            return 2 * np.polyval(vl[0], y) - np.polyval(vl[1], y)
        return 2 * np.polyval(vl[8], y) - np.polyval(vl[7], y)

    def corner(self, c, hp):
        y = np.polyval(hp, 700.0)
        for _ in range(20):
            x = self.vx(c, y); y = np.polyval(hp, x)
        return x, y

    def cell_corners(self, r, c):
        """Writing area of cell (r, c): TL, TR, BR, BL in photo pixels."""
        top, bot = self.writing_top(r), self.label_top(r + 1)
        return [self.corner(c, top), self.corner(c + 1, top), self.corner(c + 1, bot), self.corner(c, bot)]

    def locate(self, x, y):
        row = next((r for r in range(7) if np.polyval(self.label_top(r), x) <= y < np.polyval(self.label_top(r + 1), x)), None)
        col = next((c for c in range(10) if self.vx(c, y) <= x < self.vx(c + 1, y)), None)
        return row, col


def fill_small_holes(mask, max_area, max_width):
    """Fill the light streaks in the middle of marker strokes.

    A streak is a small hole that is also narrow; real counters (the loop of '%', the eye
    of 'e') are wider, so they stay open.
    """
    inv = (mask == 0).astype(np.uint8)
    k, lab, st, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    dist = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
    out = mask.copy()
    for i in range(1, k):
        x, y, w, h, a = st[i]
        if a > max_area:
            continue
        hole = lab[y:y + h, x:x + w] == i
        if dist[y:y + h, x:x + w][hole].max() <= max_width / 2:
            out[y:y + h, x:x + w][hole] = 1
    return out


def stroke_components(norm, grid):
    """Marker strokes per cell. Printed labels and grid lines are much thinner, so drop them."""
    ink = fill_small_holes((norm < INK).astype(np.uint8), 40, 4)
    opened = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    dist = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    k, lab, st, cen = cv2.connectedComponentsWithStats(opened)
    cells = {}
    for i in range(1, k):
        if st[i, 4] < 30 or st[i, 2] > 2 * CELL_W or st[i, 3] > 2 * CELL_H:   # specks; the table border
            continue
        comp = lab == i
        if dist[comp].max() < 3.5:      # a grid tick or a scrap of grid line
            continue
        r, c = grid.locate(*cen[i])
        if r is None or c is None:
            continue
        x, y, w, h = st[i, :4]
        if y + h <= np.polyval(grid.writing_top(r), x + w / 2) + 4:   # printed label in the strip above
            continue
        cells.setdefault((r, c), np.zeros_like(ink))
        cells[(r, c)][comp] = 1
    return cells


def cut_glyph(norm, grid, r, c, mask):
    """Straighten cell (r, c) and return its glyph as a 4x bitmap plus its frame offset.

    Canonical cell coordinates: u right, v down, in photo pixels, (0, 0) = top-left of the
    writing area. The returned image covers u in [-PAD_X, CELL_W + PAD_X], v in [-PAD_T, CELL_H + PAD_B].
    """
    PAD_X, PAD_T, PAD_B = 60, 45, 70
    src = np.float32([[0, 0], [CELL_W, 0], [CELL_W, CELL_H], [0, CELL_H]])
    dst = np.float32(grid.cell_corners(r, c))
    Hc = cv2.getPerspectiveTransform(src, dst)                       # canonical -> photo
    S = np.array([[UP, 0, UP * PAD_X], [0, UP, UP * PAD_T], [0, 0, 1]], np.float64)  # canonical -> output
    out_w = int(UP * (CELL_W + 2 * PAD_X)); out_h = int(UP * (CELL_H + PAD_T + PAD_B))
    M = S @ np.linalg.inv(Hc)                                        # photo -> output
    gray = cv2.warpPerspective(norm, M, (out_w, out_h), flags=cv2.INTER_CUBIC, borderValue=255)
    keep = cv2.warpPerspective(cv2.dilate(mask, np.ones((9, 9), np.uint8)) * 255, M, (out_w, out_h),
                               flags=cv2.INTER_LINEAR, borderValue=0)
    glyph = ((gray < INK) & (keep > 127)).astype(np.uint8)
    glyph = fill_small_holes(glyph, 40 * UP * UP, 4 * UP)
    # Trim stubs of grid lines that crossed the strokes.
    glyph = cv2.morphologyEx(glyph, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)))
    # Drop anything tiny the opening left behind.
    k, lab, st, _ = cv2.connectedComponentsWithStats(glyph)
    for i in range(1, k):
        if st[i, 4] < 60 * UP * UP / 4:
            glyph[lab == i] = 0
    return glyph, (PAD_X, PAD_T)


def extract_all():
    os.makedirs(BUILD, exist_ok=True)
    gray = cv2.cvtColor(cv2.imread(PHOTO), cv2.COLOR_BGR2GRAY)
    norm = normalize(gray)
    grid = Grid(*fit_lines(norm))
    cells = stroke_components(norm, grid)
    glyphs = {}
    for r, row in enumerate(ROWS):
        for c, ch in enumerate(row):
            assert (r, c) in cells, f'no strokes found for {ch!r}'
            bmp, (px, pt) = cut_glyph(norm, grid, r, c, cells[(r, c)])
            ys, xs = np.nonzero(bmp)
            # bbox in canonical photo-pixel units, relative to the cell's writing area
            glyphs[ch] = dict(bmp=bmp, row=r, pad=(px, pt),
                              left=xs.min() / UP - px, right=(xs.max() + 1) / UP - px,
                              top=ys.min() / UP - pt, bottom=(ys.max() + 1) / UP - pt)
    return glyphs


# ---------------------------------------------------------------- placement on the baseline

FAMILY = 'Julia Age 3'
PS_NAME = 'JuliaAge3-Regular'
VERSION = '1.000'
UPM = 1000
CAP_HEIGHT = 700      # font units for her median capital letter
SIDEBEARING = 55      # font units of space on each side of every glyph
SPACE = 300

# How far to even out her letters: 0 keeps them exactly as drawn, 1 makes every letter of a
# kind the same height and puts every letter exactly on the line. Partway keeps them hand-drawn.
ALIGN = 0.8

# Each letter's height moves ALIGN of the way (in proportion) to the median height of its kind,
# measured on her own letters.
KINDS = {
    'cap': 'ABCDEFGHIJKLMNOPRSTUVWXYZ?!%&',
    'digit': '0123456789',
    'x': 'acemnorsuvwxz',
    'tall': 'bdfhkli',
}
DESC_DEPTH = 0.4      # g j p q y hang this share of her x-height below the line
                      # (at three she mostly wrote them sitting on the line)


def stroke_px(bmp):
    """Marker width of a glyph bitmap in its own pixels: for a long stroke, 2 * area / perimeter."""
    cs, _ = cv2.findContours(bmp, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    return 2 * bmp.sum() / sum(cv2.arcLength(c, True) for c in cs)


def rescale(bmp, s):
    """Resize a glyph by s, keeping its marker stroke as thick as she drew it."""
    w = stroke_px(bmp)
    soft = cv2.GaussianBlur(bmp.astype(np.float32), (0, 0), 1.5)
    m = np.pad((cv2.resize(soft, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR) >= 0.5).astype(np.uint8), 40)
    r = int(round(abs(s - 1) * w / 2))
    if r >= 1:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        m = cv2.erode(m, k) if s > 1 else cv2.dilate(m, k)
    return crop(m)


def even_out(glyphs):
    """Bring her letters toward common heights and onto a common baseline, ALIGN of the way.

    Returns the resized glyphs and, for each, how far its lowest point sits below the
    baseline (photo pixels).
    """
    H = {ch: g['bottom'] - g['top'] for ch, g in glyphs.items()}
    med = {k: float(np.median([H[c] for c in v])) for k, v in KINDS.items()}
    cap, xh, tall = med['cap'], med['x'], med['tall']
    want = {c: med[k] for k, v in KINDS.items() for c in v}
    hang = {}                                   # letters placed by their top rather than their bottom
    want['t'] = xh + 0.6 * (tall - xh)          # t's cross reaches above the x-height, not to the top
    for c in 'gpqy':
        want[c], hang[c] = xh + DESC_DEPTH * xh, xh
    want['j'], hang['j'] = tall + DESC_DEPTH * xh, tall
    want['Q'], hang['Q'] = cap * H['Q'] / H['O'], cap      # her Q is her O plus a tail below the line

    # The line she wrote on: each row's median bottom.
    skip = set('gjpqy:;.,')
    base = {r: np.median([glyphs[c]['bottom'] for c in row if c not in skip]) for r, row in enumerate(ROWS)}
    out, drop = {}, {}
    for ch, g in glyphs.items():
        if ch not in want:                      # . , : ; stay as drawn
            out[ch], drop[ch] = g, 0.0
            continue
        ng = out[ch] = bitmap_glyph(rescale(g['bmp'], (want[ch] / H[ch]) ** ALIGN))
        h = ng['bottom'] - ng['top']
        if ch in hang:
            drop[ch] = h - hang[ch]
            if ch in 'gjpqy':
                drop[ch] = max(drop[ch], 0.2 * h)
        else:                                   # keep a little of her own bounce
            drop[ch] = (1 - ALIGN) * (g['bottom'] - base[g['row']])
    # '.' and ':' sit on the baseline. ';' keeps the drop she drew below her ':', and ','
    # hangs so that its top lines up with the top of her '.'.
    drop[';'] = glyphs[';']['bottom'] - glyphs[':']['bottom']
    drop[','] = (glyphs[',']['bottom'] - glyphs[',']['top']) - (glyphs['.']['bottom'] - glyphs['.']['top'])
    return out, drop, cap


def bitmap_glyph(bmp):
    ys, xs = np.nonzero(bmp)
    return dict(bmp=bmp, row=None, pad=(0, 0), left=xs.min() / UP, right=(xs.max() + 1) / UP,
                top=ys.min() / UP, bottom=(ys.max() + 1) / UP)


def crop(bmp, margin=8):
    ys, xs = np.nonzero(bmp)
    return np.pad(bmp[ys.min():ys.max() + 1, xs.min():xs.max() + 1], margin)


def stroke_width(glyphs):
    """Typical marker width in photo pixels: for a long stroke, 2 * area / perimeter."""
    area = perim = 0.0
    for g in glyphs.values():
        cs, _ = cv2.findContours(g['bmp'], cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        area += g['bmp'].sum(); perim += sum(cv2.arcLength(c, True) for c in cs)
    return 2 * area / perim / UP


def marker_line(length, width, bend):
    """A single gently bent marker stroke (for the dashes, which are not on the sheet)."""
    w, L = int(width * UP), int(length * UP)
    img = np.zeros((w * 3 + int(abs(bend) * UP) * 2, L + w * 3), np.uint8)
    t = np.linspace(0, 1, 40)
    pts = np.stack([w * 1.5 + t * L, img.shape[0] / 2 - bend * UP * 4 * t * (1 - t) + t * w * 0.3], 1)
    cv2.polylines(img, [pts.astype(np.int32)], False, 1, thickness=w, lineType=cv2.LINE_8)
    return img


def extra_glyphs(glyphs, dr, cap_px):
    """Characters that are not on the sheet, made from her strokes (or to match them)."""
    sw = stroke_width(glyphs)
    comma = crop(glyphs[',']['bmp'])
    gap = np.zeros((comma.shape[0], int(sw * UP * 0.9)), np.uint8)
    extra = {
        'quoteright': bitmap_glyph(comma),                      # ’ and ' : her comma, raised
        'quoteleft': bitmap_glyph(comma[::-1, ::-1].copy()),    # ‘ : her comma, turned round
        'quotedblright': bitmap_glyph(np.hstack([comma, gap, comma])),
        'quotedblleft': bitmap_glyph(np.hstack([comma, gap, comma])[::-1, ::-1].copy()),
        'hyphen': bitmap_glyph(marker_line(sw * 3.6, sw, 1.0)),
        'endash': bitmap_glyph(marker_line(sw * 5.6, sw, 1.4)),
    }
    for name, g in extra.items():
        h = g['bottom'] - g['top']
        if name.startswith('quote'):
            dr[name] = -(cap_px - h)                            # top at cap height
        else:
            dr[name] = -(0.36 * cap_px - h / 2)                 # centred a third of the way up
    return extra


# ---------------------------------------------------------------- tracing and font assembly

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

NAMES = {
    '?': 'question', '!': 'exclam', '%': 'percent', '&': 'ampersand', ':': 'colon',
    ';': 'semicolon', '.': 'period', ',': 'comma', '0': 'zero', '1': 'one', '2': 'two',
    '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
}
EXTRA_CMAP = {
    'quoteright': [0x2019, 0x27], 'quoteleft': [0x2018], 'quotedblright': [0x201D, 0x22],
    'quotedblleft': [0x201C], 'hyphen': [0x2D, 0x2010, 0x2011], 'endash': [0x2013],
    'space': [0x20, 0xA0],
}


def trace(bmp):
    """potrace a 0/1 bitmap. Returns a RecordingPen in bitmap pixels, y up from the bottom edge."""
    h, w = bmp.shape
    with tempfile.TemporaryDirectory() as td:
        pbm, svg = os.path.join(td, 'g.pbm'), os.path.join(td, 'g.svg')
        with open(pbm, 'wb') as f:
            f.write(b'P4\n%d %d\n' % (w, h))
            f.write(np.packbits(bmp.astype(np.uint8), axis=1).tobytes())
        subprocess.run(['potrace', '-b', 'svg', '-t', '40', '-a', '1.0', '-O', '0.4', '-o', svg, pbm], check=True)
        root = ET.parse(svg).getroot()
    ns = '{http://www.w3.org/2000/svg}'
    g = root.find(ns + 'g')
    sx, sy = (abs(float(v)) for v in re.search(r'scale\(([-\d.]+),([-\d.]+)\)', g.get('transform')).groups())
    rec = RecordingPen()
    pen = TransformPen(rec, (sx, 0, 0, sy, 0, 0))   # potrace's own units -> pixels (y already points up)
    for p in g.iter(ns + 'path'):
        parse_path(p.get('d'), pen)
    return rec


def placement(g, drop, scale):
    """Affine (scale k, dx, dy) from bitmap pixels (y up from the bottom edge) to font units:
    on the baseline, with SIDEBEARING to the left of the ink."""
    px, pt = g['pad']
    k = scale / UP
    dx = -(px + g['left']) * scale + SIDEBEARING
    dy = (g['bottom'] - drop + pt - g['bmp'].shape[0] / UP) * scale
    return k, dx, dy


def to_font_units(rec, g, drop, scale):
    """Returns (outline in font units, advance width)."""
    k, dx, dy = placement(g, drop, scale)
    out = RecordingPen()
    rec.replay(RoundingPen(TransformPen(out, (k, 0, 0, k, dx, dy))))
    return out, round((g['right'] - g['left']) * scale + 2 * SIDEBEARING)


# ---------------------------------------------------------------- kerning

BAND, Y0, NBANDS = 20, -500, 80    # horizontal slices of 20 units from y = -500 to 1100
KERN_STRENGTH = 0.5                # close half of the extra air between two shapes...
KERN_MAX = 160                     # ...but never by more than this
KERN_REACH = 2                     # count ink within 2 slices (40 units) above/below as facing


def ink_profile(g, drop, scale):
    """Leftmost and rightmost ink, in font units, for each horizontal slice of the glyph."""
    k, dx, dy = placement(g, drop, scale)
    bmp = g['bmp']; h = bmp.shape[0]
    left = np.full(NBANDS, np.inf); right = np.full(NBANDS, -np.inf)
    for r in np.nonzero(bmp.any(1))[0]:
        b = int(((h - r - 0.5) * k + dy - Y0) // BAND)
        cols = np.nonzero(bmp[r])[0]
        left[b] = min(left[b], cols[0] * k + dx)
        right[b] = max(right[b], (cols[-1] + 1) * k + dx)
    # widen each slice by its neighbours so near misses on a diagonal still count as facing
    lw, rw = left.copy(), right.copy()
    for s in range(1, KERN_REACH + 1):
        lw[s:] = np.minimum(lw[s:], left[:-s]); lw[:-s] = np.minimum(lw[:-s], left[s:])
        rw[s:] = np.maximum(rw[s:], right[:-s]); rw[:-s] = np.maximum(rw[:-s], right[s:])
    return lw, rw


def auto_kern(profiles, advances):
    """Spacing is by bounding box, so shapes with open sides (J, T, L, P, V...) leave big holes
    next to their neighbours. Pull such pairs together by half the extra gap."""
    names = sorted(profiles)
    pairs = {}
    for a in names:
        ra = advances[a] - profiles[a][1]
        for b in names:
            gap = ra + profiles[b][0]
            gap = gap[np.isfinite(gap)]
            if not len(gap):
                continue
            k = -min(KERN_MAX, KERN_STRENGTH * (gap.min() - 2 * SIDEBEARING))
            k = int(round(k / 5) * 5)
            if k <= -20:
                pairs[(a, b)] = k
    lines = [f'    pos {a} {b} {k};' for (a, b), k in sorted(pairs.items())]
    return 'languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n\nfeature kern {\n' + '\n'.join(lines) + '\n} kern;\n', pairs


def notdef():
    rec = RecordingPen()
    for (x0, y0, x1, y1), ccw in (((60, 0, 440, 700), True), ((110, 50, 390, 650), False)):
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if not ccw:
            pts = pts[::-1]
        rec.moveTo(pts[0]); [rec.lineTo(p) for p in pts[1:]]; rec.closePath()
    return rec, 500


def build_outlines():
    glyphs = extract_all()
    even, dr, cap_px = even_out(glyphs)
    scale = CAP_HEIGHT / cap_px
    source = {NAMES.get(ch, ch): (ch, g) for ch, g in even.items()}
    for name, g in extra_glyphs(glyphs, dr, cap_px).items():
        source[name] = (name, g)
    outlines = {'.notdef': notdef(), 'space': (RecordingPen(), SPACE)}
    profiles = {}
    for name, (key, g) in source.items():
        outlines[name] = to_font_units(trace(g['bmp']), g, dr[key], scale)
        profiles[name] = ink_profile(g, dr[key], scale)
    fea, pairs = auto_kern(profiles, {n: outlines[n][1] for n in profiles})
    cmap = {ord(ch): NAMES.get(ch, ch) for ch in ''.join(ROWS)}
    for name, cps in EXTRA_CMAP.items():
        for cp in cps:
            cmap[cp] = name
    return outlines, cmap, glyphs, scale, fea, pairs


def bounds(rec):
    bp = BoundsPen(None); rec.replay(bp)
    return bp.bounds or (0, 0, 0, 0)


def assemble(outlines, cmap, fea, ttf):
    order = ['.notdef', 'space'] + sorted(n for n in outlines if n not in ('.notdef', 'space'))
    fb = FontBuilder(UPM, isTTF=ttf)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    if ttf:
        glyf = {}
        for n in order:
            pen = TTGlyphPen(None)
            outlines[n][0].replay(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
            glyf[n] = pen.glyph()
        fb.setupGlyf(glyf)
    else:
        cs = {}
        for n in order:
            pen = T2CharStringPen(outlines[n][1], None)
            outlines[n][0].replay(pen)
            cs[n] = pen.getCharString()
        fb.setupCFF(PS_NAME, {'FullName': FAMILY, 'FamilyName': FAMILY, 'Weight': 'Regular'}, cs, {})
    fb.setupHorizontalMetrics({n: (outlines[n][1], round(bounds(outlines[n][0])[0])) for n in order})
    ymin = min(bounds(r)[1] for r, _ in outlines.values())
    ymax = max(bounds(r)[3] for r, _ in outlines.values())
    asc, desc = int(np.ceil(ymax / 10) * 10) + 30, int(np.floor(ymin / 10) * 10) - 30
    fb.setupHorizontalHeader(ascent=asc, descent=desc, lineGap=0)
    fb.setupNameTable({
        'familyName': FAMILY, 'styleName': 'Regular',
        'uniqueFontIdentifier': f'{VERSION};{PS_NAME}', 'fullName': FAMILY,
        'psName': PS_NAME, 'version': f'Version {VERSION}',
        'designer': 'Julia, at 3 years old',
        'description': "Made from Julia's handwriting sheet, filled in at 3 years old.",
    })
    xh = round(bounds(outlines['x'][0])[3])
    fb.setupOS2(sTypoAscender=asc, sTypoDescender=desc, sTypoLineGap=0,
                usWinAscent=asc, usWinDescent=-desc, sxHeight=xh, sCapHeight=CAP_HEIGHT,
                achVendID='NONE', fsType=0, fsSelection=0x40 | 0x80,   # REGULAR, USE_TYPO_METRICS
                usWeightClass=400, version=4)
    fb.setupPost()
    if ttf:
        fb.font['head'].flags |= 1 << 3
    addOpenTypeFeaturesFromString(fb.font, fea)
    return fb.font


def preview_extraction(glyphs):
    rows = []
    for row in ROWS:
        tiles = [cv2.copyMakeBorder(cv2.resize((1 - glyphs[ch]['bmp']) * 255, None, fx=0.25, fy=0.25,
                                               interpolation=cv2.INTER_AREA), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=160)
                 for ch in row]
        rows.append(np.hstack(tiles))
    cv2.imwrite(os.path.join(BUILD, 'extracted.png'), np.vstack(rows))


if __name__ == '__main__':
    os.makedirs(FONTS, exist_ok=True)
    outlines, cmap, glyphs, scale, fea, pairs = build_outlines()
    preview_extraction(glyphs)
    with open(os.path.join(BUILD, 'kern.fea'), 'w') as f:
        f.write(fea)
    otf = assemble(outlines, cmap, fea, ttf=False)
    otf.save(os.path.join(FONTS, PS_NAME + '.otf'))
    ttf = assemble(outlines, cmap, fea, ttf=True)
    ttf.save(os.path.join(FONTS, PS_NAME + '.ttf'))
    web = TTFont(os.path.join(FONTS, PS_NAME + '.ttf'))
    web.flavor = 'woff2'
    web.save(os.path.join(FONTS, PS_NAME + '.woff2'))
    print(f'{len(outlines)} glyphs, {len(cmap)} characters, {len(pairs)} kerning pairs, {scale:.2f} units per photo pixel -> {FONTS}')
