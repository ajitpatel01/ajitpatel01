#!/usr/bin/env python3
"""
Fetch daily contribution counts into data/contributions.json.

Prefer GitHub GraphQL with a personal token so private contributions match what
you see when logged into github.com (Include private contributions on profile).

Env (first match wins):
  PROFILE_GITHUB_TOKEN | GH_TOKEN | GITHUB_TOKEN

Falls back to the public HTML contributions calendar (public activity only).

    python scripts/fetch_contributions.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

import requests
import yaml
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
PROFILE_PATH = os.path.join(ROOT, "data", "profile.yaml")
OUT_PATH = os.path.join(ROOT, "data", "contributions.json")

USERNAME = os.environ.get("GH_PROFILE_USER")
if not USERNAME and os.path.exists(PROFILE_PATH):
    with open(PROFILE_PATH) as f:
        USERNAME = yaml.safe_load(f).get("heatmap", {}).get("github_user", "ajitpatel01")
USERNAME = USERNAME or "ajitpatel01"

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


def assign_quartile_levels(days: list[dict]) -> None:
    """GitHub-style levels when API did not supply contributionLevel."""
    if any("level" in d and d.get("level") is not None for d in days):
        # If levels came from HTML data-level / GraphQL, keep them when present.
        if all("level" in d for d in days):
            return
    nonzero = sorted(d["count"] for d in days if d["count"] > 0)
    if not nonzero:
        for d in days:
            d["level"] = 0
        return
    # Quartile thresholds over non-zero days (matches GitHub intensity buckets).
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


def build_data(days, total, source):
    assign_quartile_levels(days)
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

    data = build_data(days, total, source)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(
        f"wrote {OUT_PATH}: {data['total_contributions']} contributions "
        f"(source={source}), current streak {data['current_streak']['length']}, "
        f"longest streak {data['longest_streak']['length']}"
    )
