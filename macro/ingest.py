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

import bea
import bls
import fred

DSN = os.environ.get("MACRO_DSN", "postgresql://strawer@127.0.0.1:5432/macro")
# Row-level provenance, distinct from the catalog's source. The FRED CSV path
# is PROVISIONAL: the ALFRED backfill replaces those rows per series with
# true realtime_start vintages. Nothing replaces the BLS rows, because the
# API has no point-in-time history at all -- see CLAUDE.md trap 15.
ROW_SOURCE = {"fred": "fred_csv", "bls": "bls_api", "bea": "bea_api"}

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
                "SELECT series_id, title, source, dataset FROM macro_series_meta "
                "ORDER BY importance DESC, series_id"
            )
            catalog = cur.fetchall()
        unknown = sorted({r[2] for r in catalog} - set(ROW_SOURCE))
        if unknown:
            print(f"!! catalog has unknown source(s): {unknown}", file=sys.stderr)
            return 1

        if args.series:
            wanted = set(args.series)
            catalog = [r for r in catalog if r[0] in wanted]
            missing = wanted - {r[0] for r in catalog}
            if missing:
                # Refuse rather than warn. A named id that is not catalogued
                # means the caller built its list wrongly, and silently
                # ingesting the rest turns that into a hole nothing reports:
                # the run exits 0 and the series simply have no observations
                # until `validate.py` notices, which is a whole release later.
                print(f"!! not in catalog, refusing: {sorted(missing)}",
                      file=sys.stderr)
                return 1

        # BLS batches: one call carries fifty series, so fetch them all up front
        # rather than paying a round trip each.
        bls_ids = [r[0] for r in catalog if r[2] == "bls"]
        bls_rows: dict[str, list] = {}
        if bls_ids:
            # Only the years we lack. See module docstring in bls.py for the
            # 50-series/20-year chunking this feeds. A series with nothing
            # stored gets the full history; otherwise five years back from the
            # oldest last-observation in the batch, which is wider than any
            # seasonal-factor revision BLS applies and one call instead of five.
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.series_id, max(o.observation_dt) "
                    "FROM macro_series_meta m "
                    "LEFT JOIN macro_observations o USING (series_id) "
                    "WHERE m.series_id = ANY(%s) GROUP BY 1", (bls_ids,))
                last = dict(cur.fetchall())
            start = (bls.EARLIEST if any(v is None for v in last.values())
                     else min(v.year for v in last.values()) - 5)
            print(f"BLS: {len(bls_ids)} series from {start}"
                  f"{' (full history: new series present)' if start == bls.EARLIEST else ''}")
            try:
                bls_rows = bls.get_observations(bls_ids, start_year=start)
            except Exception as exc:                      # noqa: BLE001
                for sid in bls_ids:
                    failures.append((sid, f"{type(exc).__name__}: {exc}"))
                print(f"!! BLS batch failed: {exc}", file=sys.stderr)

        # BEA: one request returns a whole table's history, so group by table
        # and fetch each once rather than per series. The table is held in the
        # catalog's `dataset` column as "<dataset>:<TableName>".
        bea_rows: dict[str, list] = {}
        bea_by_table: dict[str, list[str]] = {}
        for r in catalog:
            if r[2] == "bea":
                bea_by_table.setdefault(r[3] or bea.DEFAULT_TABLE, []).append(r[0])
        for spec, ids in bea_by_table.items():
            try:
                print(f"BEA: {len(ids)} series from {spec}")
                bea_rows.update(bea.get_observations(ids, spec))
            except Exception as exc:                      # noqa: BLE001
                for sid in ids:
                    failures.append((sid, f"{type(exc).__name__}: {exc}"))
                print(f"!! BEA fetch failed for {spec}: {exc}", file=sys.stderr)

        print(f"{len(catalog)} series to load\n")
        print(f"{'series':<22} {'rows':>6} {'new':>6}  {'from':<8} {'to':<8}")
        print("-" * 56)

        for sid, _title, source, _dataset in catalog:
            if source == "bea":
                rows = bea_rows.get(sid)
                if not rows:
                    if sid not in [f[0] for f in failures]:
                        failures.append((sid, "BEA returned no observations"))
                        print(f"{sid:<22} {'FAIL':>6}  no observations")
                    continue
            elif source == "bls":
                rows = bls_rows.get(sid)
                if not rows:
                    if sid not in [f[0] for f in failures]:
                        failures.append((sid, "BLS returned no observations"))
                        print(f"{sid:<22} {'FAIL':>6}  no observations")
                    continue
            else:
                try:
                    rows = fred.get_observations_csv(sid)
                except Exception as exc:                  # noqa: BLE001
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
                        "src": ROW_SOURCE[source], "vin": vintage,
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
