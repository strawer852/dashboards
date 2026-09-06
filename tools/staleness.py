"""Every catalogued series, checked for a last observation recent enough for
its own frequency -- and, where one looks dead, asked of the OTHER source
before it is believed.

`tools/coverage.py` already does this, but only for series that reach a bundle.
On 5 September the catalogue went from 388 series to 2,641, and 2,344 of them
are `publish=false`: held and refreshed, drawn by nothing, and therefore
invisible to every check the project had. The 66 dead ones among them were
found by an ad-hoc query, which is another way of saying the next series to
stop publishing would not have been found at all.

Two things this does that a naive freshness check does not:

  * **The grace scales with the period.** Imported from coverage.py rather than
    restated, so there is one definition. A fixed six-month margin condemns
    every healthy annual series, and weeks are date arithmetic rather than
    short months -- traps 29 and 30.

  * **It asks BLS before calling a series dead** (trap 40). FRED can stop
    updating a series that BLS still publishes: `observation_end` simply stops,
    no title says DISCONTINUED, and every check that compares us against FRED
    agrees we are current, because we are -- we are mirroring a stale mirror.
    Six ECI series sat at October 2017 against BLS's April 2026 that way.

Exit status is the point of the split. **Dead at source is information, not a
fault**: nothing can be done about it and it must never fail a pipeline. A
series whose other source has newer data IS actionable, and only that returns
non-zero.

Usage:
  python3 tools/staleness.py               # report
  python3 tools/staleness.py --self-test   # the grace policy, on synthetic input
  python3 tools/staleness.py --no-probe    # skip the BLS cross-check
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLES = ROOT / "data" / "v1" / "dashboards"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "macro"))

from coverage import GRACE_MONTHS, STEP_MONTHS      # noqa: E402  one definition

# Ids the BLS API can actually be asked about. A FRED mnemonic (PAYEMS, ICSA,
# USGOOD, OPHNFB) names a series BLS knows under a different id, so it cannot
# be cross-checked here; those are reported as unverifiable rather than dead.
BLS_ID = re.compile(r"^(CE[SU]|CU[SU]R|CU[SU]U|WP[SU]|JT[SU]|PRS|CI[SU]|LN[SU])")

# Protects the 500/day BLS key when something systemic goes wrong and half the
# catalogue looks stale at once.
MAX_PROBE = 200


def shipped() -> set[str]:
    """Series that actually reach a page.

    NOT the `publish` column: that means eligible for the release sweep, and a
    spec can still drop one with `exclude_series` -- which WPS3012, trap 28's
    dead series, carries. Using the column as a proxy reported it as drawn.
    """
    import json
    out: set[str] = set()
    for f in sorted(BUNDLES.glob("*.json")):
        try:
            out |= set(json.loads(f.read_text(encoding="utf-8"))["series"])
        except Exception:                               # noqa: BLE001
            print("!! could not read bundle %s" % f.name, file=sys.stderr)
    return out


def overdue_months(freq: str, last_obs: date, today: date) -> int:
    """How many months past due this series is. <= 0 means healthy.

    The margin scales with the period: an annual series stamped 2025 is the
    latest that CAN exist for most of 2026.
    """
    if freq == "W":
        # Weeks are not short months. Treated as months, a weekly series lands
        # years in the future and can never be flagged.
        gap_m = (today - last_obs).days / 30.44
        return int(gap_m - 1 - GRACE_MONTHS)
    step = STEP_MONTHS.get(freq, 1)
    gap = (today.year - last_obs.year) * 12 + today.month - last_obs.month
    return gap - step - max(GRACE_MONTHS, step)


def self_test() -> int:
    """A guard that has never fired is not known to work -- trap 30."""
    today = date(2026, 9, 5)
    cases = [
        ("live monthly",      "M", date(2026, 8, 1),  False),
        ("dead monthly",      "M", date(2011, 12, 1), True),
        ("monthly, 6mo old",  "M", date(2026, 3, 1),  False),
        ("live quarterly",    "Q", date(2026, 4, 1),  False),
        ("dead quarterly",    "Q", date(2017, 10, 1), True),
        ("healthy annual",    "A", date(2025, 1, 1),  False),
        ("dead annual",       "A", date(2022, 1, 1),  True),
        ("weekly current",    "W", date(2026, 8, 29), False),
        ("weekly dead",       "W", date(2019, 5, 4),  True),
        ("semiannual live",   "SA", date(2026, 1, 1), False),
    ]
    bad = 0
    print("%-20s %-3s %-12s %8s  %-8s %s" %
          ("case", "frq", "last", "overdue", "expect", "got"))
    for name, freq, last, expect_stale in cases:
        n = overdue_months(freq, last, today)
        got = n > 0
        ok = got == expect_stale
        bad += not ok
        print("%-20s %-3s %-12s %8d  %-8s %-6s %s" %
              (name, freq, last.isoformat(), n,
               "stale" if expect_stale else "fresh",
               "stale" if got else "fresh", "" if ok else "<-- WRONG"))
    print("\n%d/%d cases correct" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0



def source_split(cur, months=1):
    """Releases where one source is more than `months` behind another.

    Returns (release, behind_source, behind_date, ahead_source, ahead_date).
    """
    cur.execute("""
        SELECT m.release_id, m.source, max(o.observation_dt)
        FROM macro_series_meta m JOIN macro_observations o USING (series_id)
        GROUP BY 1, 2
    """)
    by_rel = {}
    for rel, src, last in cur.fetchall():
        by_rel.setdefault(rel, []).append((src, last))
    out = []
    for rel, rows in by_rel.items():
        if len(rows) < 2:
            continue
        ahead = max(rows, key=lambda r: r[1])
        for src, last in rows:
            gap = ((ahead[1].year - last.year) * 12
                   + ahead[1].month - last.month)
            if gap > months:
                out.append((rel, src, last, ahead[0], ahead[1]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-probe", action="store_true",
                    help="skip the BLS cross-check; report every stale series "
                         "as unverified rather than dead")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--bundles", help="read bundles from here instead of "
                    "data/v1/dashboards. Exists so the on-a-page alarm can be "
                    "fired on demand rather than assumed to work.")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    import psycopg

    today = date.today()
    with psycopg.connect(os.environ["MACRO_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT m.series_id, m.release_id, m.source, m.frequency, m.publish,
                   max(o.observation_dt)
            FROM macro_series_meta m
            LEFT JOIN macro_observations o USING (series_id)
            GROUP BY 1, 2, 3, 4, 5
            ORDER BY 1
        """)
        rows = cur.fetchall()

    global BUNDLES
    if args.bundles:
        BUNDLES = Path(args.bundles)
    with psycopg.connect(os.environ["MACRO_DSN"]) as _c, _c.cursor() as _cur:
        split = source_split(_cur)
    on_a_page = shipped()
    empty, stale = [], []
    for sid, rel, src, freq, pub, last in rows:
        if last is None:
            empty.append((sid, rel, pub))
            continue
        n = overdue_months(freq or "M", last, today)
        if n > 0:
            stale.append({"id": sid, "release": rel, "source": src,
                          "freq": freq, "publish": pub, "last": last,
                          "overdue": n, "drawn": sid in on_a_page})

    print("%d series checked, %d actually on a page, %d held for analysis"
          % (len(rows), len(on_a_page), len(rows) - len(on_a_page)))
    if empty:
        print("\n!! %d catalogued series have NO observations: %s"
              % (len(empty), ", ".join(s for s, _, _ in empty[:12])))

    if split:
        print("\n=== a release is half updated: one source behind another ===")
        for rel, src, last, asrc, alast in split:
            print("  %-24s %s stops at %s while %s has %s"
                  % (rel, src, last, asrc, alast))

    if not stale:
        print("\nno series is overdue for its own frequency")
        return 1 if (empty or split) else 0

    stale.sort(key=lambda r: -r["overdue"])
    probeable = [r for r in stale if BLS_ID.match(r["id"])]
    capped = probeable[:MAX_PROBE]

    newer: dict[str, date] = {}
    if not args.no_probe and capped:
        import bls
        oldest = min(r["last"] for r in capped)
        try:
            obs = bls.get_observations([r["id"] for r in capped],
                                       start_year=oldest.year,
                                       end_year=today.year)
            for r in capped:
                v = obs.get(r["id"]) or []
                if v:
                    bl = max(d for d, _ in v)
                    if bl > r["last"]:
                        newer[r["id"]] = bl
        except Exception as exc:                        # noqa: BLE001
            # A monitoring call that can fail the job it monitors is worse than
            # no monitoring. Report the gap and carry on.
            print("\n!! BLS cross-check unavailable (%s: %s); every stale "
                  "series below is UNVERIFIED" % (type(exc).__name__, exc),
                  file=sys.stderr)

    fixable = [r for r in stale if r["id"] in newer]
    unverifiable = [r for r in stale if not BLS_ID.match(r["id"])]
    dead = [r for r in stale
            if r["id"] not in newer and BLS_ID.match(r["id"])]

    if fixable:
        print("\n=== ACTIONABLE: our source is stale, the other has newer data ===")
        for r in fixable:
            print("  %-20s %-24s held %s  ->  BLS has %s   (%s)"
                  % (r["id"], r["release"], r["last"], newer[r["id"]],
                     "on a page" if r["drawn"] else "analysis-only"))

    if dead:
        print("\n=== dead at source, confirmed against BLS (%d) ===" % len(dead))
        by_rel: dict[str, list] = {}
        for r in dead:
            by_rel.setdefault(r["release"], []).append(r)
        for rel, rs in sorted(by_rel.items()):
            print("  %-24s %3d series, oldest last observation %s"
                  % (rel, len(rs), min(x["last"] for x in rs)))
            drawn = [x for x in rs if x["drawn"]]
            if drawn:
                # This is trap 28 happening again: a series that stopped
                # publishing is on a page, where it draws nothing.
                print("      !! %d of these are ON A PAGE: %s"
                      % (len(drawn), ", ".join(x["id"] for x in drawn)))

    if unverifiable:
        print("\n=== stale, but not cross-checkable (FRED mnemonic, %d) ==="
              % len(unverifiable))
        for r in unverifiable[:20]:
            print("  %-20s %-24s last %s" % (r["id"], r["release"], r["last"]))

    if len(probeable) > MAX_PROBE:
        print("\nnote: %d stale series were probeable but only %d probed, to "
              "protect the BLS daily limit." % (len(probeable), MAX_PROBE))

    print("\n%d overdue: %d actionable, %d dead at source, %d unverifiable"
          % (len(stale), len(fixable), len(dead), len(unverifiable)))
    # Dead at source is information and must never fail a pipeline. Two
    # things are faults: a source that has newer data than we hold, and a dead
    # series that is still on a page, which is trap 28 with the alarm attached.
    drawn_dead = [r for r in dead if r["drawn"]]
    return 1 if (fixable or empty or drawn_dead or split) else 0


if __name__ == "__main__":
    raise SystemExit(main())
