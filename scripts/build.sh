#!/usr/bin/env bash
# One-shot profile art pipeline. See docs/PIPELINE.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
DO_PREP=1
DO_ASCII=1
DO_INFO=1
DO_STACK=1
DO_HEAT=1

usage() {
  cat <<'EOF'
Usage: ./scripts/build.sh [flags]

  (default)     prep photo → ascii → info → tech stack → heatmap
  --prep        only run prep_photo.py
  --ascii       only run make_ascii_svg.py
  --info        only run make_info_card.py
  --stack       only run make_tech_stack_svg.py
  --heatmap     only fetch + render contribution heatmap
  --no-prep     skip photo prep (reuse assets/source-prepped.png)
  -h, --help    show this help
EOF
}

if [[ $# -gt 0 ]]; then
  DO_PREP=0
  DO_ASCII=0
  DO_INFO=0
  DO_STACK=0
  DO_HEAT=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --prep) DO_PREP=1 ;;
      --ascii) DO_ASCII=1 ;;
      --info) DO_INFO=1 ;;
      --stack) DO_STACK=1 ;;
      --heatmap) DO_HEAT=1 ;;
      --no-prep) DO_PREP=0; DO_ASCII=1; DO_INFO=1; DO_STACK=1; DO_HEAT=1 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "unknown flag: $1" >&2; usage; exit 1 ;;
    esac
    shift
  done
fi

echo "==> profile art build (root=$ROOT)"

if [[ "$DO_PREP" -eq 1 ]]; then
  echo "→ prep_photo"
  "$PY" scripts/prep_photo.py
fi

if [[ "$DO_ASCII" -eq 1 ]]; then
  echo "→ make_ascii_svg"
  "$PY" scripts/make_ascii_svg.py
fi

if [[ "$DO_INFO" -eq 1 ]]; then
  echo "→ make_info_card"
  "$PY" scripts/make_info_card.py
fi

if [[ "$DO_STACK" -eq 1 ]]; then
  echo "→ make_tech_stack_svg"
  "$PY" scripts/make_tech_stack_svg.py
fi

if [[ "$DO_HEAT" -eq 1 ]]; then
  echo "→ fetch_contributions"
  "$PY" scripts/fetch_contributions.py
  echo "→ render_heatmap_svg"
  "$PY" scripts/render_heatmap_svg.py
fi

echo "==> done"
ls -la ajit-ascii.svg info-card.svg tech-stack.svg contrib-heatmap.svg 2>/dev/null || true
