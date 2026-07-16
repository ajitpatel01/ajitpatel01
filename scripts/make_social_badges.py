#!/usr/bin/env python3
"""
Generate SaaS-style social link pills (rounded, informative, brand accent).
Each badge is a separate SVG so README links stay clickable.

    python scripts/make_social_badges.py
"""
from __future__ import annotations

import html
import os
import re

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CFG = os.path.join(ROOT, "data", "social.yaml")
ICON_DIR = os.path.join(ROOT, "assets", "icons")
OUT_DIR = os.path.join(ROOT, "badges")

BG = "#0d1117"
SURFACE = "#161b22"
BORDER = "#30363d"
MUTED = "#8b949e"
INK = "#e6edf3"
STATIC = bool(os.environ.get("STATIC"))


def icon_path(slug: str) -> str:
    path = os.path.join(ICON_DIR, f"{slug}.svg")
    if not os.path.exists(path):
        return ""
    raw = open(path).read()
    m = re.search(r'<path[^>]*\sd="([^"]+)"', raw)
    return m.group(1) if m else ""


def make_badge(item: dict, index: int, height: int) -> str:
    label = item["label"]
    value = item["value"]
    hint = item.get("hint", "")
    accent = item["accent"].lstrip("#")
    d = icon_path(item["logo"])

    # Width from content
    w = max(260, 56 + max(len(value), len(hint)) * 7.4 + 28)
    h = height
    rx = 14

    delay = 0.1 + index * 0.12
    anim = ""
    if not STATIC:
        anim = (
            f' opacity="0" transform="translate(0,8)"'
            f'><animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.45s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="0 8" to="0 0" '
            f'begin="{delay:.2f}s" dur="0.45s" fill="freeze" calcMode="spline" keySplines="0.22 1 0.36 1"/>'
        )
    else:
        anim = ">"

    # Soft left accent bar + icon chip + copy
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h}" '
        f'viewBox="0 0 {w:.0f} {h}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
        f"<defs>"
        f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{SURFACE}"/>'
        f'<stop offset="1" stop-color="{BG}"/>'
        f"</linearGradient>"
        f'<filter id="soft" x="-10%" y="-20%" width="120%" height="140%">'
        f'<feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000" flood-opacity="0.35"/>'
        f"</filter>"
        f"</defs>",
        f'<g{anim}',
        f'<rect x="1" y="1" width="{w - 2:.0f}" height="{h - 2}" rx="{rx}" '
        f'fill="url(#g)" stroke="{BORDER}" stroke-width="1" filter="url(#soft)"/>',
        # accent rail
        f'<rect x="1" y="1" width="5" height="{h - 2}" rx="2.5" fill="#{accent}"/>',
        # icon chip
        f'<rect x="18" y="{(h - 36) / 2:.1f}" width="36" height="36" rx="10" fill="#{accent}" fill-opacity="0.18"/>',
    ]
    if d:
        scale = 18 / 24
        ix = 18 + (36 - 18) / 2
        iy = (h - 18) / 2
        parts.append(
            f'<g transform="translate({ix:.1f},{iy:.1f}) scale({scale:.4f})">'
            f'<path d="{d}" fill="#{accent}"/></g>'
        )
    parts.append(
        f'<text x="66" y="{h * 0.38:.1f}" fill="{MUTED}" font-size="11" font-weight="600" '
        f'letter-spacing="0.06em">{html.escape(label.upper())}</text>'
        f'<text x="66" y="{h * 0.62:.1f}" fill="{INK}" font-size="14" font-weight="700">'
        f"{html.escape(value)}</text>"
    )
    if hint:
        parts.append(
            f'<text x="66" y="{h * 0.84:.1f}" fill="{MUTED}" font-size="10.5">'
            f"{html.escape(hint)}</text>"
        )
    parts.append("</g></svg>")
    return "".join(parts)


def main():
    with open(CFG) as f:
        raw = yaml.safe_load(f)
    cfg = raw.get("social", raw)
    height = int(cfg.get("height", 72))
    os.makedirs(OUT_DIR, exist_ok=True)
    for i, item in enumerate(cfg["items"]):
        svg = make_badge(item, i, height)
        out = os.path.join(OUT_DIR, f"{item['id']}.svg")
        with open(out, "w") as f:
            f.write(svg)
        print("wrote", out, len(svg), "bytes")


if __name__ == "__main__":
    main()
