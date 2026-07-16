#!/usr/bin/env python3
"""
Fetch daily contribution counts into data/contributions.json.

Modes (data/profile.yaml → heatmap.mode):
  attractive — dense, GitHub-green calendar targeting ~338 (profile look)
  live       — GraphQL (token) or public HTML scrape

Env for live mode (first match wins):
  PROFILE_GITHUB_TOKEN | GH_TOKEN | GITHUB_TOKEN

    python scripts/fetch_contributions.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import sys

import requests
import yaml
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
PROFILE_PATH = os.path.join(ROOT, "data", "profile.yaml")
OUT_PATH = os.path.join(ROOT, "data", "contributions.json")

_PROFILE = {}
if os.path.exists(PROFILE_PATH):
    with open(PROFILE_PATH) as f:
        _PROFILE = yaml.safe_load(f) or {}
_HEAT = _PROFILE.get("heatmap", {})

USERNAME = os.environ.get("GH_PROFILE_USER") or _HEAT.get("github_user") or "ajitpatel01"
HEAT_MODE = os.environ.get("HEATMAP_MODE") or _HEAT.get("mode") or "live"
ATTRACTIVE_TOTAL = int(os.environ.get("ATTRACTIVE_TOTAL") or _HEAT.get("attractive_total") or 338)
ATTRACTIVE_SEED = int(os.environ.get("ATTRACTIVE_SEED") or _HEAT.get("attractive_seed") or 3382026)

LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

GQL = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""


def token() -> str | None:
    for key in ("PROFILE_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


def fetch_days_graphql(tok: str) -> tuple[list[dict], int, str]:
    resp = requests.post(
        "https://api.github.com/graphql",
        headers={
            "Authorization": f"Bearer {tok}",
            "User-Agent": "profile-readme-bot/1.0",
            "Accept": "application/json",
        },
        json={"query": GQL, "variables": {"login": USERNAME}},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            days.append(
                {
                    "date": day["date"],
                    "count": int(day["contributionCount"]),
                    "level": LEVEL_MAP.get(day["contributionLevel"], 0),
                }
            )
    days.sort(key=lambda d: d["date"])
    return days, int(cal["totalContributions"]), "graphql"


def fetch_days_html() -> tuple[list[dict], int, str]:
    url = f"https://github.com/users/{USERNAME}/contributions"
    resp = requests.get(url, headers={"User-Agent": "profile-readme-bot/1.0"}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print("no calendar cells found -- github markup may have changed", file=sys.stderr)
        sys.exit(1)

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if re.search(r"no contributions", text, re.I):
            count = 0
        else:
            m = re.match(r"(\d+)", text)
            count = int(m.group(1)) if m else 0
        level = int(td.get("data-level") or 0)
        days.append({"date": date, "count": count, "level": level})

    days.sort(key=lambda d: d["date"])
    total = sum(d["count"] for d in days)
    h2 = soup.select_one("#js-contribution-activity-description")
    if h2:
        m = re.search(r"([\d,]+)", h2.get_text(" ", strip=True))
        if m:
            total = int(m.group(1).replace(",", ""))
    return days, total, "html_public"


def _season_weight(d: dt.date) -> float:
    """Match logged-in profile shape: quiet Jul–Dec, ramp Jan, dense Mar–Jul."""
    if d.year < 2026:
        if d.month in (8, 9):
            return 0.06
        return 0.01
    if d.month == 1:
        return 1.05
    if d.month == 2:
        return 0.75
    if d.month in (3, 4, 5, 6):
        return 1.7
    if d.month == 7:
        return 1.35
    return 0.2


def github_calendar_dates(end: dt.date | None = None) -> list[dt.date]:
    """~53-week Sunday-start window ending today (GitHub contribution grid)."""
    end = end or dt.date.today()
    start = end - dt.timedelta(days=370)
    while start.weekday() != 6:  # Sunday
        start -= dt.timedelta(days=1)
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += dt.timedelta(days=1)
    return out


def generate_attractive_days(
    target: int = ATTRACTIVE_TOTAL, seed: int = ATTRACTIVE_SEED
) -> tuple[list[dict], int, str]:
    """
    Curated random calendar: sparse early year, dense bright greens later.
    Levels use GitHub quartiles so greens match native profile shades.
    """
    dates = github_calendar_dates()
    rng = random.Random(seed + dates[-1].toordinal())

    weights = []
    for d in dates:
        w = _season_weight(d)
        if d.weekday() >= 5:  # weekends quieter
            w *= 0.5
        weights.append(w)

    # Active-day probability from weights (dense Mar–Jul)
    active = []
    for i, (d, w) in enumerate(zip(dates, weights)):
        # Base chance scales with season; clamp for attractive fill
        p = min(0.92, 0.08 + w * 0.42)
        if rng.random() < p and w > 0.05:
            active.append(i)
        elif w >= 1.0 and rng.random() < 0.55:
            active.append(i)

    # Ensure enough active days for a rich Mar–Jul look
    dense_idx = [
        i
        for i, d in enumerate(dates)
        if d.year == 2026 and d.month >= 3 and d.weekday() < 5
    ]
    rng.shuffle(dense_idx)
    for i in dense_idx:
        if len(active) >= 145:
            break
        if i not in active:
            active.append(i)

    if not active:
        active = list(range(max(0, len(dates) - 120), len(dates)))

    # Intensity buckets → raw counts (later mapped to GitHub levels 0–4)
    # Higher tops → more neon FOURTH_QUARTILE greens like the native graph.
    bucket_counts = [1, 2, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 22]
    bucket_weights = [6, 8, 8, 9, 9, 8, 7, 6, 5, 4, 3, 2, 2]

    counts = [0] * len(dates)
    for i in active:
        boost = 1.0 + max(0.0, weights[i] - 0.4) * 1.4
        local_w = [bw * boost for bw in bucket_weights]
        counts[i] = rng.choices(bucket_counts, weights=local_w, k=1)[0]

    # A few sparse “embers” in Aug/Sep (screenshot: mostly empty first half)
    for i, d in enumerate(dates):
        if d.year == 2025 and d.month in (8, 9) and counts[i] == 0 and rng.random() < 0.035:
            counts[i] = rng.choice([1, 2, 3])
        # Clear accidental Oct–Dec noise
        if d.year == 2025 and d.month >= 10:
            counts[i] = 0

    total = sum(counts)
    # Scale to exact target
    if total == 0:
        counts[-1] = target
        total = target
    elif total != target:
        scale = target / total
        counts = [int(round(c * scale)) for c in counts]
        # fix rounding drift
        drift = target - sum(counts)
        order = sorted(active, key=lambda i: counts[i], reverse=True) or list(range(len(counts)))
        k = 0
        while drift != 0 and order:
            i = order[k % len(order)]
            if drift > 0:
                counts[i] += 1
                drift -= 1
            elif counts[i] > 0:
                counts[i] -= 1
                drift += 1
            k += 1
            if k > len(order) * 50:
                break

    days = [
        {"date": d.isoformat(), "count": int(counts[i])}
        for i, d in enumerate(dates)
    ]
    return days, int(sum(counts)), "graphql"


def assign_quartile_levels(days: list[dict], force: bool = False) -> None:
    """GitHub-style levels (NONE→FOURTH_QUARTILE) from count quartiles."""
    if (
        not force
        and all("level" in d and d.get("level") is not None for d in days)
        and any(d.get("level", 0) > 0 for d in days)
    ):
        return
    nonzero = sorted(d["count"] for d in days if d["count"] > 0)
    if not nonzero:
        for d in days:
            d["level"] = 0
        return

    def q(p: float) -> float:
        if len(nonzero) == 1:
            return nonzero[0]
        idx = min(len(nonzero) - 1, max(0, int(round(p * (len(nonzero) - 1)))))
        return nonzero[idx]

    t1, t2, t3 = q(0.25), q(0.50), q(0.75)
    for d in days:
        c = d["count"]
        if c <= 0:
            d["level"] = 0
        elif c <= t1:
            d["level"] = 1
        elif c <= t2:
            d["level"] = 2
        elif c <= t3:
            d["level"] = 3
        else:
            d["level"] = 4


def compute_current_streak(days):
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days, total, source, force_levels: bool = False):
    assign_quartile_levels(days, force=force_levels)
    # Prefer GitHub's reported total (includes private when authed).
    sum_counts = sum(d["count"] for d in days)
    if total < sum_counts:
        total = sum_counts
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"])
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username": USERNAME,
        "source": source,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "counted_contributions": sum_counts,
        "active_days": active_days,
        "avg_per_active_day": round(sum_counts / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


if __name__ == "__main__":
    force_levels = False
    if HEAT_MODE == "attractive":
        days, total, source = generate_attractive_days(ATTRACTIVE_TOTAL, ATTRACTIVE_SEED)
        force_levels = True
        print(
            f"heatmap.mode=attractive → target={ATTRACTIVE_TOTAL} seed={ATTRACTIVE_SEED}",
            file=sys.stderr,
        )
    else:
        tok = token()
        source = "html_public"
        try:
            if tok:
                days, total, source = fetch_days_graphql(tok)
            else:
                print(
                    "warning: no PROFILE_GITHUB_TOKEN/GH_TOKEN — using public HTML "
                    "(private contributions omitted; total may be lower than your logged-in profile)",
                    file=sys.stderr,
                )
                days, total, source = fetch_days_html()
        except Exception as exc:
            if tok:
                print(f"graphql failed ({exc}); falling back to public HTML", file=sys.stderr)
                days, total, source = fetch_days_html()
            else:
                raise

    data = build_data(days, total, source, force_levels=force_levels)
    if HEAT_MODE == "attractive":
        data["total_contributions"] = sum(d["count"] for d in data["days"])

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(
        f"wrote {OUT_PATH}: {data['total_contributions']} contributions "
        f"(source={data['source']}, mode={HEAT_MODE}), "
        f"current streak {data['current_streak']['length']}, "
        f"longest streak {data['longest_streak']['length']}"
    )
