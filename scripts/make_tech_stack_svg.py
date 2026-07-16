#!/usr/bin/env python3
"""
Build an animated, shields-style tech-stack SVG with real Simple Icons logos.

Icons are fetched once into assets/icons/ and embedded (GitHub <img> SVGs cannot
load external URLs). Badges stagger in with fade + slide for a smooth entrance.

    python scripts/make_tech_stack_svg.py
"""
from __future__ import annotations

import html
import os
import re
import sys
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CFG_PATH = os.path.join(ROOT, "data", "tech_stack.yaml")
OUT = os.path.join(ROOT, "tech-stack.svg")
ICON_DIR = os.path.join(ROOT, "assets", "icons")

ICON_CDN = "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/{slug}.svg"

# Badge geometry (for-the-badge inspired)
PAD_X = 12
PAD_Y = 8
ICON = 14
GAP_ICON = 8
CHAR_W = 7.2  # approx bold uppercase
H = 28
R = 6
GAP_X = 8
GAP_Y = 10
OUTER_PAD = 22
TITLEBAR_H = 30
HEADER_H = 36

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"

STATIC = bool(os.environ.get("STATIC"))


def fetch_icon(slug: str) -> str:
    os.makedirs(ICON_DIR, exist_ok=True)
    path = os.path.join(ICON_DIR, f"{slug}.svg")
    if not os.path.exists(path):
        url = ICON_CDN.format(slug=slug)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                path_data = resp.read().decode("utf-8")
        except Exception as exc:
            # slug aliases
            aliases = {
                "css": "css3",
                "amazonwebservices": "amazonaws",
                "powerbi": "powerbi",
            }
            alt = aliases.get(slug)
            if not alt or alt == slug:
                print(f"warn: icon {slug}: {exc}", file=sys.stderr)
                return ""
            url = ICON_CDN.format(slug=alt)
            with urllib.request.urlopen(url, timeout=20) as resp:
                path_data = resp.read().decode("utf-8")
            slug = alt
        with open(path, "w") as f:
            f.write(path_data)
    else:
        path_data = open(path).read()
    m = re.search(r'<path[^>]*\sd="([^"]+)"', path_data)
    return m.group(1) if m else ""


def badge_width(label: str) -> float:
    return PAD_X * 2 + ICON + GAP_ICON + max(36, len(label) * CHAR_W)


def rise(inner: str, i: int) -> str:
    if STATIC:
        return f"<g>{inner}</g>"
    delay = 0.12 + i * 0.045
    return (
        f'<g opacity="0" transform="translate(0,10)">{inner}'
        f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.45s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="translate" from="0 10" to="0 0" '
        f'begin="{delay:.2f}s" dur="0.45s" fill="freeze" calcMode="spline" '
        f'keySplines="0.22 1 0.36 1"/></g>'
    )


def main():
    with open(CFG_PATH) as f:
        raw = yaml.safe_load(f)
    cfg = raw.get("tech_stack", raw)

    rows = cfg["rows"]
    width = int(cfg.get("width", 860))
    title = cfg.get("title", "Tech Stack")
    titlebar = cfg.get("titlebar", "ajit@github: ~/stack --icons")

    # measure rows
    row_widths = []
    for row in rows:
        w = sum(badge_width(b["label"]) for b in row) + GAP_X * (len(row) - 1)
        row_widths.append(w)
    content_w = max(row_widths) if row_widths else width
    canvas_w = max(width, int(content_w + OUTER_PAD * 2))

    body_h = len(rows) * H + max(0, len(rows) - 1) * GAP_Y
    canvas_h = TITLEBAR_H + HEADER_H + body_h + OUTER_PAD

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="-apple-system,BlinkMacSystemFont,'
        f'Segoe UI,Helvetica,Arial,sans-serif">',
        "<defs>"
        f'<linearGradient id="tbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
        "</linearGradient></defs>",
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#tbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w - 1}" height="{canvas_h - 1}" rx="12" '
        f'fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{OUTER_PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{dotcol}"/>')
    parts.append(
        f'<text x="{canvas_w / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{MUTED}" font-size="12" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        f'text-anchor="middle">{html.escape(titlebar)}</text>'
    )

    # Header with laptop glyph + title
    header_inner = (
        f'<g transform="translate({OUTER_PAD}, {TITLEBAR_H + 8})">'
        f'<rect x="0" y="4" width="18" height="12" rx="2" fill="none" stroke="{INK}" stroke-width="1.5"/>'
        f'<path d="M-2 18h22" stroke="{INK}" stroke-width="1.5" stroke-linecap="round"/>'
        f'<text x="28" y="16" fill="{INK}" font-size="16" font-weight="700">{html.escape(title)}</text>'
        f"</g>"
    )
    parts.append(rise(header_inner, 0))

    y = TITLEBAR_H + HEADER_H
    badge_i = 0
    for row in rows:
        row_w = sum(badge_width(b["label"]) for b in row) + GAP_X * (len(row) - 1)
        x = (canvas_w - row_w) / 2
        for b in row:
            slug = b["slug"]
            label = b["label"]
            color = b["color"].lstrip("#")
            ink = b.get("ink", "FFFFFF").lstrip("#")
            bw = badge_width(label)
            d = fetch_icon(slug)
            # icon color: for light badges use ink; path fill = ink
            icon_fill = f"#{ink}"
            label_fill = f"#{ink}"
            # Layout: colored pill, icon left, label right
            g = (
                f"<g>"
                f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="{H}" rx="{R}" fill="#{color}"/>'
            )
            if d:
                # scale 24x24 path into ICON box
                scale = ICON / 24
                ix = x + PAD_X
                iy = y + (H - ICON) / 2
                g += (
                    f'<g transform="translate({ix:.1f},{iy:.1f}) scale({scale:.4f})">'
                    f'<path d="{d}" fill="{icon_fill}"/></g>'
                )
            tx = x + PAD_X + ICON + GAP_ICON
            ty = y + H * 0.68
            g += (
                f'<text x="{tx:.1f}" y="{ty:.1f}" fill="{label_fill}" font-size="11" '
                f'font-weight="700" letter-spacing="0.4">{html.escape(label.upper())}</text>'
                f"</g>"
            )
            parts.append(rise(g, badge_i + 1))
            badge_i += 1
            x += bw + GAP_X
        y += H + GAP_Y

    parts.append("</svg>")
    svg = "".join(parts)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg)} bytes) badges={badge_i} {canvas_w}x{canvas_h}")


if __name__ == "__main__":
    main()
