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

import bls
import fred

DSN = os.environ["MACRO_DSN"]

UPSERT = """
INSERT INTO macro_series_meta
  (series_id, source, title, frequency, country, category, importance,
   seasonal_adjustment, validation_mode, originator, dataset, release_id,
   source_url, unit, vintage_mode, publish)
VALUES
  (%(sid)s, %(source)s, %(title)s, %(freq)s, 'US', %(cat)s, %(imp)s,
   %(sa)s, 'zscore', %(orig)s, %(dataset)s, %(rel)s,
   %(url)s, %(unit)s, %(vmode)s, %(publish)s)
ON CONFLICT (series_id) DO UPDATE SET
  title = EXCLUDED.title, frequency = EXCLUDED.frequency,
  seasonal_adjustment = EXCLUDED.seasonal_adjustment,
  release_id = EXCLUDED.release_id, importance = EXCLUDED.importance,
  publish = EXCLUDED.publish
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
    ap.add_argument("--source", choices=("fred", "bls"), default="fred",
                    help="FRED wherever both carry the series: it is the "
                         "only free source of vintages.")
    ap.add_argument("--no-publish", action="store_true",
                    help="Ingest for analysis, not for display: the series is "
                         "stored and refreshed like any other but is never "
                         "swept into a dashboard bundle. A spec can still ask "
                         "for it by name in include_series.")
    args = ap.parse_args()

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT name FROM macro_releases WHERE release_id=%s", (args.release,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"unknown release_id {args.release!r}")
        dataset = row[0]

        bls_cat = bls.get_catalog(args.series) if args.source == "bls" else {}

        for sid in args.series:
            if args.source == "bls":
                cat = bls_cat.get(sid)
                if not cat:
                    print(f"!! {sid}: BLS returned no catalog block. Metadata is "
                          "not available for every series; add it by hand rather "
                          "than guessing.", file=sys.stderr)
                    return 1
                title = cat.get("series_title") or cat.get("measure_data_type")
                freq = "M"          # every BLS series in this catalog is monthly
                sa = "SA" if str(cat.get("seasonality", "")).lower().startswith("s") else "NSA"
                unit = cat.get("measure_data_type")
                url = f"https://data.bls.gov/timeseries/{sid}"
                # No ALFRED equivalent, so the vintage IS the fetch date and
                # revision history accrues only from ingestion onward. The
                # schema already had a word for that; don't invent another.
                vmode = "fetch_date"
            else:
                info = series_info(sid)
                freq = FREQ.get(info.get("frequency", ""))
                if freq is None:
                    print(f"!! {sid}: unmapped frequency {info.get('frequency')!r}",
                          file=sys.stderr)
                    return 1
                title = info["title"]
                sa = "SA" if info.get("seasonal_adjustment_short") == "SA" else "NSA"
                unit = info.get("units_short")
                url = f"https://fred.stlouisfed.org/series/{sid}"
                vmode = "from_row"

            cur.execute(UPSERT, {
                "sid": sid, "title": title, "freq": freq,
                "publish": not args.no_publish,
                "cat": args.category, "imp": args.importance, "sa": sa,
                "orig": "U.S. Bureau of Labor Statistics", "dataset": dataset,
                "rel": args.release, "url": url, "unit": unit,
                "source": args.source, "vmode": vmode,
            })
            flag = "     " if not args.no_publish else " (--)"
            print(f"  {sid:<16} {freq} {sa:<4} {args.source:<4}{flag} "
                  f"{str(title)[:46]}")
        conn.commit()

    print(f"\n{len(args.series)} series upserted into {args.release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
