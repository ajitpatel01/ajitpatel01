"""
Convert a portrait photo into a CLEAN, monochrome ASCII-art SVG that "types"
itself in like a terminal, then holds.

GitHub renders SVGs embedded via <img> and runs their SMIL animations there (JS
does not run). Each row is revealed with a left-to-right clip wipe plus a small
block cursor riding the wipe edge, staggered top -> bottom.

    python scripts/make_ascii_svg.py [prepped.png] [out.svg]
"""
from PIL import Image, ImageEnhance, ImageFilter
import html
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
PROFILE = os.path.join(ROOT, "data", "profile.yaml")

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "source-prepped.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "ajit-ascii.svg")

with open(PROFILE) as f:
    profile = yaml.safe_load(f)

ascii_cfg = profile.get("ascii", {})
TITLEBAR_LABEL = ascii_cfg.get("titlebar", "ajit@github: ~$ ./portrait.sh")
WHOAMI = ascii_cfg.get("whoami", profile["identity"]["name"])

# Wider grid so the portrait fills the terminal after subject crop.
COLS = 112
ROWS = 52
CELL_W = 8
CELL_H = 15
RAMP = " .`:-=+*cs#%@"  # bright(sparse) -> dark(dense); leading space clears bg

CONTRAST = 1.05
BRIGHTNESS = 1.0
GAMMA = 1.18
SHARPEN = False
WHITE_FLOOR = 0.80
# Crop away empty white margins so the face spans most of COLS (not a slim center strip).
CROP_WHITE = 248
CROP_PAD_FRAC = 0.01

PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
ART_W = COLS * CELL_W
ART_H = ROWS * CELL_H
CANVAS_W = ART_W + PAD * 2
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"
CURSOR = "#c9d1d9"

ROW_DUR = 0.11
STAGGER = 0.11


def crop_to_subject(im, white_thresh=CROP_WHITE, pad_frac=CROP_PAD_FRAC):
    """Tight crop around non-white pixels so the portrait fills the ASCII grid."""
    import numpy as np

    arr = np.asarray(im)
    mask = arr < white_thresh
    if not mask.any():
        return im
    ys, xs = np.where(mask)
    left, right = int(xs.min()), int(xs.max())
    top, bottom = int(ys.min()), int(ys.max())
    bw, bh = right - left + 1, bottom - top + 1
    pad_x = max(2, int(bw * pad_frac))
    pad_y = max(2, int(bh * pad_frac))
    h, w = arr.shape
    left = max(0, left - pad_x)
    right = min(w - 1, right + pad_x)
    top = max(0, top - pad_y)
    bottom = min(h - 1, bottom + pad_y)
    return im.crop((left, top, right + 1, bottom + 1))


im = Image.open(SRC).convert("L")
im = crop_to_subject(im)
if SHARPEN:
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=2))
im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
im = ImageEnhance.Contrast(im).enhance(CONTRAST)
im = im.resize((COLS, ROWS), Image.LANCZOS)
px = im.load()

STATIC = bool(os.environ.get("STATIC"))

rows_txt = []
for y in range(ROWS):
    chars = []
    for x in range(COLS):
        lum = px[x, y] / 255.0
        lum = pow(lum, GAMMA)
        if lum >= WHITE_FLOOR:
            chars.append(" ")
            continue
        idx = int((1.0 - lum) * (len(RAMP) - 1) + 0.5)
        idx = max(0, min(len(RAMP) - 1, idx))
        chars.append(RAMP[idx])
    rows_txt.append("".join(chars))

art_top = TITLEBAR_H + PAD * 0.35

parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
    f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="ui-monospace, SFMono-Regular, '
    f'Menlo, Consolas, monospace">'
)
parts.append(
    "<defs>"
    f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
    f"</linearGradient></defs>"
)

parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>')
parts.append(
    f'<rect x="0.5" y="0.5" width="{CANVAS_W - 1}" height="{CANVAS_H - 1}" rx="12" '
    f'fill="none" stroke="{FRAME}" stroke-width="1"/>'
)

parts.append(
    f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>'
)
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{dotcol}"/>')
parts.append(
    f'<text x="{CANVAS_W / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
    f'text-anchor="middle">{html.escape(TITLEBAR_LABEL)}</text>'
)

font_size = CELL_H * 0.86
for ry, line in enumerate(rows_txt):
    y = art_top + ry * CELL_H + CELL_H * 0.74
    row_y = art_top + ry * CELL_H
    delay = ry * STAGGER
    safe = html.escape(line)
    text = (
        f'<text xml:space="preserve" x="{PAD}" y="{y:.1f}" fill="{INK}" '
        f'font-size="{font_size:.1f}" textLength="{ART_W}" lengthAdjust="spacing">{safe}</text>'
    )

    if STATIC:
        parts.append(text)
        continue

    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y:.1f}" height="{CELL_H}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>'
    )
    parts.append(f'<g clip-path="url(#r{ry})">{text}</g>')
    parts.append(
        f'<rect y="{row_y + 1:.1f}" width="{CELL_W}" height="{CELL_H - 2}" fill="{CURSOR}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD + ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay + ROW_DUR:.3f}s"/></rect>'
    )

status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
status_y = status_line_y + 19
# Approximate monospace advance for "ajit@github:~$ whoami " then name
prefix = "ajit@github:~$ whoami "
cursor_x = PAD + len(prefix) * 7.8 + len(WHOAMI) * 7.8 + 6

parts.append(
    f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>'
)
parts.append(
    f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
    f'ajit@github:~$ whoami <tspan fill="{INK}">{html.escape(WHOAMI)}</tspan></text>'
)
parts.append(
    f'<rect x="{cursor_x:.1f}" y="{status_y - 12:.1f}" width="8" height="14" fill="{INK}">'
    f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
    f'dur="1s" repeatCount="indefinite"/></rect>'
)

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w") as f:
    f.write(svg)
print("wrote", OUT, len(svg), "bytes;", CANVAS_W, "x", CANVAS_H)
