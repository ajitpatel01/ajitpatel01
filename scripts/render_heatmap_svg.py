#!/usr/bin/env python3
"""
Render data/contributions.json as a GitHub-accurate contribution heatmap SVG
(terminal chrome + native calendar proportions, 5-level palette, informative stats).

    python scripts/render_heatmap_svg.py
"""
import datetime
import json
import os

import yaml

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
IN_PATH = os.path.join(ROOT, "data", "contributions.json")
OUT_PATH = os.path.join(ROOT, "contrib-heatmap.svg")
PROFILE_PATH = os.path.join(ROOT, "data", "profile.yaml")

# Exact GitHub dark-theme contribution levels (NONE → FOURTH_QUARTILE)
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

# Native-ish cell geometry (GitHub uses ~11px cells + 3–4px gutters)
CELL = 11
GAP = 3
STEP = CELL + GAP
PAD = 20
LEFT_LABEL_W = 28
TOP_LABEL_H = 18
TITLEBAR_H = 30
HEADER_H = 28  # "N contributions in the last year"

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"
ACCENT = "#58a6ff"
GREEN = "#3fb950"
GOLD = "#d29922"

COL_T = 0.016
ROW_T = 0.04
CELL_DUR = 0.38

TITLEBAR = "ajit@github: ~/contributions --graph"
if os.path.exists(PROFILE_PATH):
    with open(PROFILE_PATH) as f:
        TITLEBAR = yaml.safe_load(f).get("heatmap", {}).get("titlebar", TITLEBAR)


def level_for(day: dict) -> int:
    if "level" in day and day["level"] is not None:
        return max(0, min(4, int(day["level"])))
    count = day.get("count", 0)
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 9:
        return 3
    return 4


def build_grid(days):
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d)))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def month_labels_for(grid):
    """Place a label at the first week that contains day 1 of a month (GitHub-like)."""
    labels = []
    seen = set()
    for ci, column in enumerate(grid):
        for cell in column:
            if cell is None:
                continue
            date = datetime.date.fromisoformat(cell[0])
            key = (date.year, date.month)
            if key in seen:
                break
            # Prefer columns that include the 1st; else first seen week of that month.
            if date.day == 1 or (date.day <= 7 and key not in seen):
                seen.add(key)
                labels.append((ci, date.strftime("%b")))
            break
    return labels


def render(data):
    days = data["days"]
    grid = build_grid(days)
    n_cols = len(grid)
    art_w = n_cols * STEP - GAP
    art_h = 7 * STEP - GAP

    labels = month_labels_for(grid)

    footer_h = 72
    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    canvas_h = TITLEBAR_H + HEADER_H + TOP_LABEL_H + art_h + footer_h + PAD

    css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-5px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{ opacity: 0; animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
@media (prefers-reduced-motion: reduce) {{
  .c {{ opacity: 1 !important; animation: none !important; }}
}}
""".strip()

    total = data["total_contributions"]
    cs = data["current_streak"]["length"]
    ls = data["longest_streak"]["length"]
    best = data["best_day"]
    active = data.get("active_days", 0)
    avg = data.get("avg_per_active_day", 0)
    rng = data["range"]
    source = data.get("source", "unknown")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="-apple-system,BlinkMacSystemFont,'
        f'Segoe UI,Helvetica,Arial,sans-serif,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        f"<style>{css}</style>",
        "<defs>"
        f'<linearGradient id="hbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient>'
        "</defs>",
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#hbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w - 1}" height="{canvas_h - 1}" rx="12" '
        f'fill="none" stroke="{FRAME}" stroke-width="1"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{dotcol}"/>')
    parts.append(
        f'<text x="{canvas_w / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{MUTED}" font-size="12" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        f'text-anchor="middle">{TITLEBAR}</text>'
    )

    # GitHub-native headline
    header_y = TITLEBAR_H + 20
    parts.append(
        f'<text x="{PAD}" y="{header_y}" font-size="14" fill="{INK}">'
        f'<tspan font-weight="600">{total:,}</tspan>'
        f'<tspan fill="{MUTED}"> contributions in the last year</tspan></text>'
    )
    parts.append(
        f'<text x="{canvas_w - PAD}" y="{header_y}" font-size="11" fill="{MUTED}" text-anchor="end">'
        f'{rng["start"]} → {rng["end"]}</text>'
    )

    grid_top = TITLEBAR_H + HEADER_H + TOP_LABEL_H
    grid_left = PAD + LEFT_LABEL_W

    for ci, label in labels:
        x = grid_left + ci * STEP
        parts.append(
            f'<text x="{x}" y="{TITLEBAR_H + HEADER_H + 12}" fill="{MUTED}" font-size="10">{label}</text>'
        )

    for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = grid_top + wi * STEP + CELL * 0.85
        parts.append(f'<text x="{PAD}" y="{y:.1f}" fill="{MUTED}" font-size="9">{wname}</text>')

    for ci, column in enumerate(grid):
        gx = grid_left + ci * STEP
        for ri, cell in enumerate(column):
            if cell is None:
                continue
            date_s, count, lvl = cell
            gy = grid_top + ri * STEP
            delay = ci * COL_T + ri * ROW_T
            plural = "s" if count != 1 else ""
            parts.append(
                f'<rect class="c" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{PALETTE[lvl]}" style="animation-delay:{delay:.3f}s">'
                f"<title>{date_s}: {count} contribution{plural}</title></rect>"
            )

    # Legend — GitHub: Less [5 swatches] More
    leg_y = grid_top + art_h + 14
    leg_x = canvas_w - PAD - (len(PALETTE) * (CELL + 2) + 52)
    parts.append(
        f'<text x="{leg_x}" y="{leg_y + CELL * 0.85:.1f}" fill="{MUTED}" font-size="10" text-anchor="end">Less</text>'
    )
    lx = leg_x + 6
    for color in PALETTE:
        parts.append(
            f'<rect x="{lx}" y="{leg_y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"/>'
        )
        lx += CELL + 2
    parts.append(f'<text x="{lx + 4}" y="{leg_y + CELL * 0.85:.1f}" fill="{MUTED}" font-size="10">More</text>')

    sep_y = leg_y + CELL + 12
    parts.append(
        f'<line x1="{PAD}" y1="{sep_y}" x2="{canvas_w - PAD}" y2="{sep_y}" stroke="{FRAME}" stroke-opacity="0.7"/>'
    )

    ly = sep_y + 20
    parts.append(
        f'<text x="{PAD}" y="{ly}" font-size="12" fill="{MUTED}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
        f'active <tspan fill="{GREEN}" font-weight="700">{active}</tspan> days'
        f'<tspan fill="{MUTED}">  ·  </tspan>avg '
        f'<tspan fill="{ACCENT}" font-weight="700">{avg}</tspan>/day'
        f'<tspan fill="{MUTED}">  ·  </tspan>streak '
        f'<tspan fill="{ACCENT}" font-weight="700">{cs}</tspan>'
        f'<tspan fill="{MUTED}"> (best </tspan>'
        f'<tspan fill="{ACCENT}" font-weight="700">{ls}</tspan>'
        f'<tspan fill="{MUTED}">)</tspan></text>'
    )
    parts.append(
        f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
        f'peak <tspan fill="{GOLD}" font-weight="700">{best["count"]}</tspan> on {best["date"]}</text>'
    )
    ly += 18
    parts.append(
        f'<text x="{PAD}" y="{ly}" font-size="10" fill="{MUTED}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
        f'source={source} · auto-refreshed daily</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    data = json.load(open(IN_PATH))
    svg = render(data)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes) total={data['total_contributions']}")
