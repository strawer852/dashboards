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

Usage:  python3 tools/coverage.py [--fail]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLES = ROOT / "data" / "v1" / "dashboards"
SITE = ROOT / "site"


def page_for(bundle: dict) -> Path:
    return SITE / bundle["path"] / "index.html"


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

    if worst and args.fail:
        print("\nSeries are being fetched, validated and shipped for nothing.",
              file=sys.stderr)
        return 1
    if not worst:
        print("\nevery exported series is drawn by its page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
