"""Load current-vintage observations for every catalogued series.

Keyless: uses FRED's public CSV endpoint, so this runs before any API key
exists. Rows land with source='fred_csv', which marks them PROVISIONAL — the
ALFRED backfill replaces them per series with true realtime_start vintages.

Two behaviours carried over from FINDINGS_revision_handling.md:

  * Bare `ON CONFLICT DO NOTHING`. The retired stack used
    `ON CONFLICT (cols) DO NOTHING` on a TimescaleDB hypertable, where chunk
    constraint inference meant it never fired — 650,093 duplicate rows in
    1,784,464. Our table is plain, but the bare form is the robust one and the
    primary key is the only unique constraint that can fire.

  * Diff-on-write. A new vintage row is written only when the value actually
    differs from the latest stored vintage. Without this, every re-run would
    stamp a fresh vintage_dt and manufacture revisions that never happened.
    The comparison is server-side and NULL-safe (`IS DISTINCT FROM`), so a
    genuinely-null observation does not spuriously rewrite.

Usage:  venv/bin/python ingest.py [--series ID ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import psycopg

import fred

DSN = os.environ.get("MACRO_DSN", "postgresql://strawer@127.0.0.1:5432/macro")
PROVISIONAL_SOURCE = "fred_csv"

UPSERT = """
WITH incoming AS (
    SELECT * FROM unnest(%(dates)s::date[], %(vals)s::numeric[])
                  AS t(observation_dt, value)
),
latest AS (
    SELECT DISTINCT ON (observation_dt) observation_dt, value
    FROM   macro_observations
    WHERE  series_id = %(sid)s
    ORDER  BY observation_dt, vintage_dt DESC
)
INSERT INTO macro_observations (series_id, source, observation_dt, vintage_dt, value)
SELECT %(sid)s, %(src)s, i.observation_dt, %(vin)s, i.value
FROM   incoming i
LEFT   JOIN latest l USING (observation_dt)
WHERE  l.observation_dt IS NULL
   OR  l.value::float8 IS DISTINCT FROM i.value::float8
ON CONFLICT DO NOTHING
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="*", help="limit to these series ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vintage = datetime.now(timezone.utc)
    inserted_total = fetched_total = 0
    failures: list[tuple[str, str]] = []

    with psycopg.connect(DSN, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT series_id, title FROM macro_series_meta "
                "WHERE source = 'fred' ORDER BY importance DESC, series_id"
            )
            catalog = cur.fetchall()

        if args.series:
            wanted = set(args.series)
            catalog = [r for r in catalog if r[0] in wanted]
            missing = wanted - {r[0] for r in catalog}
            if missing:
                print(f"!! not in catalog: {sorted(missing)}", file=sys.stderr)

        print(f"{len(catalog)} series to load\n")
        print(f"{'series':<22} {'rows':>6} {'new':>6}  {'from':<8} {'to':<8}")
        print("-" * 56)

        for sid, _title in catalog:
            try:
                rows = fred.get_observations_csv(sid)
            except Exception as exc:                      # noqa: BLE001
                failures.append((sid, f"{type(exc).__name__}: {exc}"))
                print(f"{sid:<22} {'FAIL':>6}  {exc!s:.40}")
                continue

            fetched_total += len(rows)
            dates = [d for d, _ in rows]
            vals = [v for _, v in rows]

            if args.dry_run:
                n = 0
            else:
                with conn.cursor() as cur:
                    cur.execute(UPSERT, {
                        "dates": dates, "vals": vals, "sid": sid,
                        "src": PROVISIONAL_SOURCE, "vin": vintage,
                    })
                    n = cur.rowcount
                conn.commit()
            inserted_total += n
            print(f"{sid:<22} {len(rows):>6} {n:>6}  "
                  f"{dates[0].isoformat():<8} {dates[-1].isoformat():<8}")

    print("-" * 56)
    print(f"fetched {fetched_total} observations; inserted {inserted_total} rows")
    if failures:
        print(f"\n{len(failures)} FAILED:", file=sys.stderr)
        for sid, err in failures:
            print(f"  {sid}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
