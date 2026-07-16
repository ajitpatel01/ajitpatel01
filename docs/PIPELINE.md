# Pipeline

How to regenerate profile art. Prefer [`scripts/build.sh`](../scripts/build.sh) unless debugging a single stage.

## Prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Use the venv for all local runs (`.venv/` is gitignored). First `prep_photo` download may fetch the rembg `u2net` model (~176MB) into `~/.u2net/`.

Heavy packages (`rembg`, OpenCV) are required only for photo prep. Heatmap-only refreshes need `requests`, `beautifulsoup4`, and `PyYAML`.

## Full rebuild

```bash
./scripts/build.sh
```

Runs in order:

1. `prep_photo.py` — isolate subject, CLAHE contrast, white composite → `assets/source-prepped.png`
2. `make_ascii_svg.py` — ASCII grid + SMIL typing → `ajit-ascii.svg`
3. `make_info_card.py` — YAML → neofetch card → `info-card.svg`
4. `fetch_contributions.py` + `render_heatmap_svg.py` → `data/contributions.json` + `contrib-heatmap.svg`

## Partial rebuilds

| Intent | Command |
|---|---|
| New photo only | `./scripts/build.sh --prep && ./scripts/build.sh --ascii` |
| Copy / badges / stack text | edit `data/profile.yaml` then `./scripts/build.sh --info` |
| Heatmap only | `./scripts/build.sh --heatmap` |
| Skip rembg (reuse prepped) | `./scripts/build.sh --no-prep` |

## Photo replacement

1. Replace [`assets/source-photo.png`](../assets/source-photo.png) (PNG/JPG fine; keep high-contrast portrait on dark or plain background)
2. Run `./scripts/build.sh --prep --ascii` (or full `./scripts/build.sh`)
3. Commit `assets/source-photo.png`, `assets/source-prepped.png`, and `ajit-ascii.svg`

## Static previews

For Quick Look / design review without animation:

```bash
STATIC=1 python scripts/make_ascii_svg.py
STATIC=1 python scripts/make_info_card.py
```

## CI refresh

[`.github/workflows/update-profile-art.yml`](../.github/workflows/update-profile-art.yml):

- Cron `17 6 * * *` UTC
- Also on push to `main` and `workflow_dispatch`
- Commits only `data/contributions.json` and `contrib-heatmap.svg`

Portrait SVGs are **not** regenerated in CI (avoids pulling `rembg` on every run).

### Match logged-in totals (private contributions)

Public HTML scrape omits private activity (e.g. ~102 vs ~334 on a logged-in profile).

1. Create a **classic** Personal Access Token with `read:user`
2. Add repo secret `PROFILE_GITHUB_TOKEN`
3. Re-run the workflow (or locally: `PROFILE_GITHUB_TOKEN=… ./scripts/build.sh --heatmap`)

GraphQL then returns the same calendar + total GitHub shows when you are signed in.

## Fallback heatmap

If the HTML scrape fails locally:

```bash
python scripts/generate_streak_svg.py ajitpatel01 contrib-heatmap.svg
```

Prefer `render_heatmap_svg.py` for the framed terminal look used in the README.

## Verification checklist

- [ ] Open `ajit-ascii.svg` in a browser — portrait types top→bottom once
- [ ] Open `info-card.svg` — rows fade in; values match YAML
- [ ] Open `contrib-heatmap.svg` — cells animate; totals look sane
- [ ] Push and confirm GitHub profile renders both terminals + heatmap
