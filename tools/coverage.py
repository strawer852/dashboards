#!/usr/bin/env python3
"""Report bundle series that no page draws.

Seasonal-adjustment companions are counted as held rather than unused: they
exist so a panel can offer the unadjusted view, and the catalog records the
pairing.

The exporter already fails when a catalogued series reaches no bundle. It cannot
see the other end: a series can be fetched, validated, exported and shipped in
every bundle while no panel on the page ever reads it. That gap is invisible by
construction -- nothing looks wrong, the page renders, the tests pass -- and it
is the defect class recorded in FINDINGS as collected-data coverage.

A series counted here is one whose id appears in the page's panel list or its
summary strip. Derived series count their inputs as used, since a panel drawing
the derivative is genuinely consuming them.

There is a second way a series can be shipped for nothing, and being drawn does
not rule it out: the source can stop publishing it. A discontinued series has
observations, so the exporter is content; it has a panel, so coverage above is
content; its acceptance tests pin old vintages, so validation is content. Every
number in every report is correct and the chart is empty, because the window a
panel shows is the recent past and the series left it years ago. WPS3012 sat on
the PPI page in exactly that state. So each series is also checked for a last
observation recent enough for its own frequency.

Usage:  python3 tools/coverage.py [--fail]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLES = ROOT / "data" / "v1" / "dashboards"
SITE = ROOT / "site"

# How long after a period ends the next value may reasonably be outstanding.
# Generous on purpose: this is looking for series abandoned years ago, not for
# a release running a few days late.
STEP_MONTHS = {"M": 1, "Q": 3, "SA": 6, "A": 12}
GRACE_MONTHS = 6


def page_for(bundle: dict) -> Path:
    return SITE / bundle["path"] / "index.html"


def months_since_last(entry: dict, today: date) -> tuple[int, str] | None:
    """Months between a series' last real observation and now, or None."""
    obs = entry.get("observations") or entry.get("values")
    start = entry.get("start")
    if not obs or not start:
        return None
    idx = max((i for i, v in enumerate(obs) if v is not None), default=None)
    if idx is None:
        return 0 if False else (10 ** 6, "never")
    freq = entry.get("step") or entry.get("frequency") or "M"
    st = date.fromisoformat(start)
    if freq == "W":
        # Weeks are not short months. Modelled as months a weekly series lands
        # years in the future, giving a negative gap and passing every check --
        # a silent exemption for exactly the dashboard that updates most often.
        last = st + timedelta(weeks=idx)
        gap_m = (today - last).days / 30.44
        return int(gap_m - 1 - GRACE_MONTHS), last.strftime("%Y-%m-%d")
    step = STEP_MONTHS.get(freq, 1)
    total = st.month - 1 + idx * step
    last = date(st.year + total // 12, total % 12 + 1, 1)
    gap = (today.year - last.year) * 12 + today.month - last.month
    # The margin has to scale with the period. An annual series stamped 2025
    # is the latest that CAN exist for most of 2026, so a fixed six-month
    # grace would condemn every healthy annual series in the catalogue.
    grace = max(GRACE_MONTHS, step)
    return gap - step - grace, last.strftime("%Y-%m")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail", action="store_true",
                    help="exit non-zero when anything is unused")
    args = ap.parse_args()

    worst = 0
    for path in sorted(BUNDLES.glob("*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        page = page_for(bundle)
        if not page.exists():
            print(f"!! {bundle['id']}: no page at {page}", file=sys.stderr)
            worst = 1
            continue
        html = page.read_text(encoding="utf-8")

        series = bundle["series"]
        # Ids appearing anywhere in the page's markup or script.
        drawn = {sid for sid in series if re.search(r'["\']' + re.escape(sid) + r'["\']', html)}
        # A drawn derived series consumes whatever it was built from.
        for sid in list(drawn):
            drawn.update(series[sid].get("derived_from", []))

        # The unadjusted twin of a drawn series is held on purpose, so a panel
        # can offer the unadjusted view. Not a series fetched for nothing.
        twins = {series[sid]["companion"] for sid in drawn
                 if series.get(sid, {}).get("companion") in series}
        unused = sorted(set(series) - drawn - twins)
        pct = 100 * len(drawn | twins) / len(series)
        flag = "" if not unused else "   <-- unused"
        print(f"{bundle['id']:<34} {len(drawn):>3} drawn + {len(twins):>2} twin "
              f"of {len(series):<3} ({pct:5.1f}%){flag}")
        for sid in unused:
            e = series[sid]
            print(f"      {sid:<16} {e.get('title','')[:58]}")
        if unused:
            worst = 1

        today = date.today()
        dead = []
        for sid, e in series.items():
            got = months_since_last(e, today)
            if got and got[0] > 0:
                dead.append((sid, got[1], e.get("title", "")[:52]))
        for sid, last, title in sorted(dead):
            print(f"      {sid:<16} last value {last}  DISCONTINUED?  {title}")
        if dead:
            worst = 1

    if worst and args.fail:
        print("\nSeries are being fetched, validated and shipped for nothing,",
              "or are no longer published at all.",
              file=sys.stderr)
        return 1
    if not worst:
        print("\nevery exported series is drawn by its page, and still published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
