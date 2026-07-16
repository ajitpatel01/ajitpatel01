# Content

Editorial guide for [`data/profile.yaml`](../data/profile.yaml). This file is the **only** place to edit public copy for the info card, badge metadata, and terminal titlebars.

After edits:

```bash
./scripts/build.sh --info
# If you changed ascii.whoami or ascii.titlebar:
./scripts/build.sh --ascii
```

Then commit regenerated SVGs (and YAML).

## Schema overview

```yaml
identity:      # name, handle, host, title
badges:        # shields.io buttons under the name
info_card:     # neofetch panel rows + dimensions
ascii:         # portrait terminal chrome
heatmap:       # github_user + heatmap titlebar
```

## Character budgets (info card)

The SVG is monospace at ~12.5px inside a ~520px card. Stay inside these budgets or text will clip visually:

| Field | Soft max |
|---|---|
| `kv.value` | ~48 characters |
| `bul.text` | ~52 characters |
| Section titles | short nouns (`Stack`, `Highlights`) |

Prefer curated stack lines over dumping every tool from a resume.

## Row kinds (`info_card.rows`)

| `kind` | Fields | Renders as |
|---|---|---|
| `host` | — | `handle`@`host` + rule |
| `kv` | `key`, `value` | Orange key + light value |
| `sec` | `title` | Blue `— title` + rule |
| `bul` | `text` | Green dot + text |
| `gap` | — | Vertical spacer |

## Premium copy conventions

- **Now** — role + company, US product tone (`Software Engineer … @ KaDeep AI`)
- **Focus** — outcomes, not task lists
- **Edu** — degree + school only
- **Highlights** — 2–3 proof points (founding impact, peer-reviewed work)

Avoid: emojis in YAML values, rainbow ASCII, or pasting full bullet paragraphs into `kv.value`.

## Badges

Each badge becomes a shields.io for-the-badge link in README. Keep `label` / `value` short; `url` must be absolute HTTPS.

Current surface: Portfolio · LinkedIn · GitHub (no Instagram / live terminal).

## Identity ↔ generators

| YAML path | Consumed by |
|---|---|
| `identity.handle` / `host` | `make_info_card.py` host row |
| `identity.name` | fallback for `ascii.whoami` |
| `info_card.*` | `make_info_card.py` |
| `ascii.*` | `make_ascii_svg.py` |
| `heatmap.github_user` | `fetch_contributions.py` / streak fallback |
| `badges` | documented for README; maintain README shields in sync when changing URLs |

When you change badge URLs, update the shield links in [`README.md`](../README.md) in the same commit.
