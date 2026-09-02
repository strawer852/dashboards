"""Add series to the catalog, taking their metadata from FRED rather than typing it.

The restored 0018 catalog carries the headline employment series but not the
supersector decomposition, which two panels of the payroll dashboard need. This
adds them with titles, frequency and seasonal-adjustment flags read from FRED's
own /series endpoint, so nothing is transcribed by hand.

Usage:
  venv/bin/python add_series.py --release bls.employment_situation \
      --category employment --importance 5 SERIES [SERIES ...]
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx
import psycopg

import fred

DSN = os.environ["MACRO_DSN"]

UPSERT = """
INSERT INTO macro_series_meta
  (series_id, source, title, frequency, country, category, importance,
   seasonal_adjustment, validation_mode, originator, dataset, release_id,
   source_url, unit, vintage_mode)
VALUES
  (%(sid)s, 'fred', %(title)s, %(freq)s, 'US', %(cat)s, %(imp)s,
   %(sa)s, 'zscore', %(orig)s, %(dataset)s, %(rel)s,
   %(url)s, %(unit)s, 'from_row')
ON CONFLICT (series_id) DO UPDATE SET
  title = EXCLUDED.title, frequency = EXCLUDED.frequency,
  seasonal_adjustment = EXCLUDED.seasonal_adjustment,
  release_id = EXCLUDED.release_id, importance = EXCLUDED.importance
"""

FREQ = {"Monthly": "M", "Quarterly": "Q", "Annual": "A",
        "Weekly": "W", "Daily": "D",
        "Weekly, Ending Saturday": "W", "Weekly, Ending Thursday": "W"}


def series_info(sid: str) -> dict:
    with httpx.Client(timeout=fred.HTTP_TIMEOUT) as client:
        r = client.get(f"{fred.FRED_BASE}/series",
                       params={"series_id": sid, "api_key": fred.api_key(),
                               "file_type": "json"})
        r.raise_for_status()
        data = r.json()
    if not data.get("seriess"):
        raise SystemExit(f"FRED has no series {sid}")
    return data["seriess"][0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("series", nargs="+")
    ap.add_argument("--release", required=True)
    ap.add_argument("--category", default="employment")
    ap.add_argument("--importance", type=int, default=5)
    args = ap.parse_args()

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT name FROM macro_releases WHERE release_id=%s", (args.release,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"unknown release_id {args.release!r}")
        dataset = row[0]

        for sid in args.series:
            info = series_info(sid)
            freq = FREQ.get(info.get("frequency", ""))
            if freq is None:
                print(f"!! {sid}: unmapped frequency {info.get('frequency')!r}", file=sys.stderr)
                return 1
            sa = "SA" if info.get("seasonal_adjustment_short") == "SA" else "NSA"
            cur.execute(UPSERT, {
                "sid": sid, "title": info["title"], "freq": freq,
                "cat": args.category, "imp": args.importance, "sa": sa,
                "orig": "U.S. Bureau of Labor Statistics", "dataset": dataset,
                "rel": args.release,
                "url": f"https://fred.stlouisfed.org/series/{sid}",
                "unit": info.get("units_short"),
            })
            print(f"  {sid:<16} {freq} {sa:<4} {info['title'][:58]}")
        conn.commit()

    print(f"\n{len(args.series)} series upserted into {args.release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
