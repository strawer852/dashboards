"""Replace provisional current-vintage rows with true ALFRED revision history.

For each catalogued series this fetches every known vintage of every
observation, then — in one transaction per series, so a series is never left
empty — deletes its provisional `fred_csv` rows and inserts the real ones with
`vintage_dt = realtime_start`.

Vintage-mode handling follows FINDINGS_revision_handling.md, but VERIFIES rather
than assumes. The retired stack found eight series with no usable ALFRED history
and moved them to fetch-date vintaging; one of those (FRBATLWGT3MMAUMHWGO) is in
our catalog. Instead of trusting that classification, this probes ALFRED for
every series and reports the observed vintage depth, so a series whose
ALFRED-eligibility has since changed shows up rather than silently keeping the
wrong mode.

A series has no ALFRED history only when every row in its response carries the
SAME realtime_start -- ALFRED knows a single vintage date for it. Its provisional
rows are then kept as the anchor and it is reported as such. Until 9 September
2026 the test was "one row per observation", which cannot tell that case from a
series that is never revised: the unadjusted CPI and ECI never move after first
print (CLAUDE.md trap 25), so each observation has exactly one row, whose
realtime_start is its own publication date. That test filed 358 such series as
vintage-less and left them on fetch-time rows (trap 63). A publication date per
observation is history -- it is what the stamp and every as-of query read.

Usage:  venv/bin/python backfill.py [--series ID ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

import psycopg

import fred

DSN = os.environ["MACRO_DSN"]
PROVISIONAL = "fred_csv"
FINAL = "fred"

INSERT = """
INSERT INTO macro_observations (series_id, source, observation_dt, vintage_dt, value)
SELECT %(sid)s, %(src)s, t.obs, t.vin, t.val
FROM unnest(%(obs)s::date[], %(vin)s::timestamptz[], %(val)s::numeric[])
     AS t(obs, vin, val)
ON CONFLICT DO NOTHING
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    totals = defaultdict(int)
    anchored: list[str] = []
    failures: list[tuple[str, str]] = []

    with psycopg.connect(DSN, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT series_id, vintage_mode FROM macro_series_meta "
                "WHERE source='fred' ORDER BY importance DESC, series_id")
            catalog = cur.fetchall()

        if args.series:
            wanted = set(args.series)
            catalog = [r for r in catalog if r[0] in wanted]

        print(f"{len(catalog)} series\n")
        print(f"{'series':<22} {'obs':>6} {'vintages':>9} {'depth':>6} {'stored':>8}  mode")
        print("-" * 68)

        for sid, mode in catalog:
            try:
                rows = fred.get_vintages(sid)
            except Exception as exc:                       # noqa: BLE001
                failures.append((sid, f"{type(exc).__name__}: {exc}"))
                print(f"{sid:<22} {'FAIL':>6}  {str(exc)[:38]}")
                continue

            obs, vin, val = [], [], []
            per_obs: dict[str, set] = defaultdict(set)
            for r in rows:
                d = r["date"]
                rs = r["realtime_start"]
                per_obs[d].add(rs)
                obs.append(d)
                vin.append(fred.parse_vintage(rs))
                val.append(fred.parse_value(r.get("value")))

            n_obs = len(per_obs)
            n_rows = len(rows)
            depth = (n_rows / n_obs) if n_obs else 0.0

            # ALFRED holds no history for this series only if it knows a single
            # vintage date: every row then shares one realtime_start. One row per
            # observation is NOT that -- a series that is never revised looks the
            # same, with each row dated by its own publication (trap 63).
            starts = {r["realtime_start"] for r in rows}
            if n_obs and len(starts) <= 1:
                anchored.append(sid)
                print(f"{sid:<22} {n_obs:>6} {n_rows:>9} {depth:>6.2f} {'anchor':>8}  "
                      f"{mode} -> no ALFRED history (single vintage date)")
                continue

            if args.dry_run:
                stored = 0
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM macro_observations "
                        "WHERE series_id=%s AND source=%s", (sid, PROVISIONAL))
                    cur.execute(INSERT, {"sid": sid, "src": FINAL,
                                         "obs": obs, "vin": vin, "val": val})
                    stored = cur.rowcount
                conn.commit()

            totals["rows"] += stored
            totals["obs"] += n_obs
            print(f"{sid:<22} {n_obs:>6} {n_rows:>9} {depth:>6.2f} {stored:>8}  {mode}")

    print("-" * 68)
    print(f"{totals['obs']} observations, {totals['rows']} vintage rows stored")
    if anchored:
        print(f"\n{len(anchored)} series with no ALFRED revision history "
              f"(provisional anchor kept): {', '.join(anchored)}")
        print("  -> these should carry vintage_mode='fetch_date'; anything listed "
              "here that is set to 'from_row' is a misclassification.")
    if failures:
        print(f"\n{len(failures)} FAILED:", file=sys.stderr)
        for sid, err in failures:
            print(f"  {sid}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
