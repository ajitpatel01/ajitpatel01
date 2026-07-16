# Architecture

This repository is a **GitHub profile art system**: generated SVG surfaces embedded in [`README.md`](../README.md). It is not an application runtime. Treat it like a small production asset pipeline with clear ownership boundaries.

## Goals

- Premium terminal aesthetic on the public GitHub profile (`ajitpatel01/ajitpatel01`)
- “Running sketch” ASCII portrait via **SMIL** (GitHub runs SVG animations; JS does not run in README)
- Single editorial source of truth for copy and badges
- Daily-fresh contribution heatmap without manual edits

## Constraints (platform)

| Constraint | Implication |
|---|---|
| README cannot run JavaScript | All motion is SMIL / CSS inside SVG `<img>` embeds |
| Relative image paths | Root SVGs (`ajit-ascii.svg`, `info-card.svg`, `contrib-heatmap.svg`) must stay at repo root |
| Profile repo naming | Repo must be `username/username` for GitHub to show README on the profile |

## Component map

```
┌─────────────────────────────────────────────────────────────┐
│  PUBLIC SURFACE                                             │
│  README.md  →  embeds root SVGs + shields.io badges         │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
     ┌──────────▼──────────┐       ┌──────────▼──────────┐
     │ BUILD ARTIFACTS     │       │ SCHEDULED ARTIFACT  │
     │ ajit-ascii.svg      │       │ contrib-heatmap.svg │
     │ info-card.svg       │       │ data/contributions  │
     └──────────▲──────────┘       └──────────▲──────────┘
                │                             │
     ┌──────────┴──────────┐       ┌──────────┴──────────┐
     │ GENERATORS          │       │ CI WORKFLOW         │
     │ scripts/prep_photo  │       │ update-profile-art  │
     │ scripts/make_*      │       │ fetch + render      │
     └──────────▲──────────┘       └──────────▲──────────┘
                │                             │
     ┌──────────┴──────────┐       ┌──────────┴──────────┐
     │ SOURCES             │       │ EXTERNAL DATA       │
     │ assets/source-photo │       │ github.com/users/…  │
     │ data/profile.yaml   │       │ /contributions HTML │
     └─────────────────────┘       └─────────────────────┘
```

## Ownership boundaries

| Path | Owner | Mutability |
|---|---|---|
| [`data/profile.yaml`](../data/profile.yaml) | Humans (editorial) | Edit anytime; regenerate info/ascii titlebars |
| [`assets/source-photo.png`](../assets/source-photo.png) | Humans (identity) | Replace → re-run prep + ascii |
| [`assets/source-prepped.png`](../assets/source-prepped.png) | Generator | Do not hand-edit |
| [`scripts/`](../scripts/) | Engineering | Change carefully; keep YAML contract |
| Root `*.svg` | Generators | Commit as artifacts for GitHub CDN |
| [`data/contributions.json`](../data/contributions.json) | CI / fetch script | Overwritten daily |
| [`docs/`](.) | Engineering | Keep in sync with pipeline |

## Data flow

1. **Portrait path (local, on photo change)**  
   `source-photo.png` → `prep_photo.py` (rembg + CLAHE) → `source-prepped.png` → `make_ascii_svg.py` → `ajit-ascii.svg` (SMIL row wipe)

2. **Info path (local, on copy change)**  
   `profile.yaml` → `make_info_card.py` → `info-card.svg` (staggered fade-in)

3. **Heatmap path (CI daily + local)**  
   GitHub contributions HTML → `fetch_contributions.py` → `contributions.json` → `render_heatmap_svg.py` → `contrib-heatmap.svg`

## Animation model

- **ASCII:** per-row `<clipPath>` width animate + block cursor; one-shot, then freeze
- **Info card:** opacity + translateY SMIL per row
- **Heatmap:** CSS `@keyframes` diagonal reveal of cells (works when SVG is loaded as `<img>` on GitHub)

## Security & ops

- Contribution scrape is **unauthenticated public HTML** — no GitHub token required
- Workflow uses `contents: write` only to commit heatmap artifacts
- Portrait deps (`rembg`, OpenCV) stay off the daily CI path; CI installs only scrape/render deps

## Related docs

- [PIPELINE.md](PIPELINE.md) — how to regenerate
- [CONTENT.md](CONTENT.md) — how to edit YAML safely
