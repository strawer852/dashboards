"""Assert the loaded data reproduces the published July 2026 releases.

The news release PDF is the acceptance test. If the database and the PDF
disagree, the build is wrong — fail loudly rather than publish a dashboard that
quietly contradicts its own source.

Usage:  venv/bin/python validate.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg

DSN = os.environ["MACRO_DSN"]

# Every published figure below is asserted AS OF a vintage, never against the
# current one. A revision then cannot break it: what the July 2026 release said
# is a permanent fact, and a test pinned to it needs no maintenance. Tests that
# must hold for TODAY's data -- the shutdown gap, the supersector sum, and the
# invariants at the bottom -- deliberately read the current vintage instead.
ES = "2026-08-07"   # Employment Situation, July 2026 (USDL-26-1291)
JT = "2026-09-01"   # JOLTS, July 2026 (USDL-26-1432)
BL = "2026-09-03"   # BLS-API series: no vintage history, so ingestion is all
                    # there is. Pinning still freezes the value we first saw.

# (series, observation, as-of vintage, expected, note) — USDL-26-1291 / -26-1432.
LEVELS = [
    ("UNRATE",        "2026-07-01", ES,   4.1,   "unemployment rate"),
    ("CIVPART",       "2026-07-01", ES,  61.4,   "participation rate"),
    ("EMRATIO",       "2026-07-01", ES,  58.9,   "employment-population ratio"),
    ("CES0500000003", "2026-07-01", ES,  37.62,  "avg hourly earnings, all employees"),
    ("AHETPI",        "2026-07-01", ES,  32.40,  "avg hourly earnings, prod & nonsup"),
    ("AWHAETP",       "2026-07-01", ES,  34.3,   "average weekly hours"),
    ("U6RATE",        "2026-07-01", ES,   7.9,   "U-6"),
    ("JTSJOL",        "2026-07-01", JT, 7271.0,  "job openings (7.3m)"),
    # BLS-sourced. 1-, 3- and 6-month spans are seasonally adjusted; the
    # 12-month span exists only unadjusted, which is why it is a CEU id.
    ("CES0500000021", "2026-07-01", BL,   51.8,   "diffusion, 1-month span"),
    ("CES0500000022", "2026-07-01", BL,   50.8,   "diffusion, 3-month span"),
    ("CES0500000023", "2026-07-01", BL,   55.0,   "diffusion, 6-month span"),
    ("CEU0500000024", "2026-07-01", BL,   51.8,   "diffusion, 12-month span, NSA"),
    ("LNS16000000",   "2026-07-01", BL, 156497.0, "CPS employment on the CES concept"),
]

# The shutdown gap is household-survey only: CPS series are genuinely empty for
# October 2025 while the establishment survey carries a value.
NULLS = [
    ("UNRATE",  "2025-10-01", True,  "CPS not collected"),
    ("CIVPART", "2025-10-01", True,  "CPS not collected"),
    ("EMRATIO", "2025-10-01", True,  "CPS not collected"),
    ("PAYEMS",  "2025-10-01", False, "CES was collected"),
]


# Revision facts the July release states outright. These exercise the vintage
# store, which nothing else can: they are wrong the moment point-in-time reads
# break.
#
# NOTE the release phrases a revision against the PREVIOUSLY PUBLISHED figure,
# not the first print. May 2026 went 172 -> 129 -> 63 across three releases; the
# PDF's "revised down by 66,000, from +129,000 to +63,000" is the last step.
CHANGE_AS_OF = [
    ("PAYEMS", "2026-06-01", "2026-07-02",  57.0, "June, as first reported"),
    ("PAYEMS", "2026-06-01", "2026-08-07",  20.0, "June, as revised in the July release"),
    ("PAYEMS", "2026-05-01", "2026-06-05", 172.0, "May, as first reported"),
    ("PAYEMS", "2026-05-01", "2026-07-02", 129.0, "May, as the July release quotes it"),
    ("PAYEMS", "2026-05-01", "2026-08-07",  63.0, "May, as revised"),
    ("PAYEMS", "2026-07-01", "2026-08-07", -23.0, "July, first and only print"),
]

CHANGE_SQL = """
SELECT (SELECT o.value FROM macro_observations o
         WHERE o.series_id=%(sid)s AND o.observation_dt=%(m)s
           AND o.vintage_dt::date <= %(asof)s::date ORDER BY o.vintage_dt DESC LIMIT 1)
     - (SELECT o.value FROM macro_observations o
         WHERE o.series_id=%(sid)s
           AND o.observation_dt=(%(m)s::date - interval '1 month')::date
           AND o.vintage_dt::date <= %(asof)s::date ORDER BY o.vintage_dt DESC LIMIT 1)
"""


def val(cur, sid, obs):
    """Latest vintage. For invariants that must hold for TODAY's data."""
    cur.execute(
        "SELECT value FROM macro_observations_current "
        "WHERE series_id=%s AND observation_dt=%s", (sid, obs))
    row = cur.fetchone()
    return (None, False) if row is None else (row[0], True)


def val_asof(cur, sid, obs, asof):
    """The value as it stood on a given date — what a release actually said.

    Immune to every later revision, which is the point: an acceptance test that
    changes meaning when the data is revised is not an acceptance test.
    """
    cur.execute(
        "SELECT value FROM macro_observations WHERE series_id=%s AND observation_dt=%s "
        "AND vintage_dt::date <= %s::date AND value IS NOT NULL "
        "ORDER BY vintage_dt DESC LIMIT 1",
        (sid, obs, asof))
    row = cur.fetchone()
    return (None, False) if row is None else (row[0], True)


def main() -> int:
    fails: list[str] = []
    checks = 0

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        print("=== published levels, as of the release that stated them ===")
        for sid, obs, asof, want, note in LEVELS:
            got, present = val_asof(cur, sid, obs, asof)
            checks += 1
            ok = present and got is not None and abs(float(got) - want) < 1e-9
            print(f"  {'OK ' if ok else 'FAIL'}  {sid:<16} {obs} @{asof}  got {got}  "
                  f"want {want}   {note}")
            if not ok:
                fails.append(f"{sid} {obs} as of {asof}: got {got}, want {want}")

        print("\n=== October 2025 shutdown gap ===")
        for sid, obs, want_null, note in NULLS:
            got, present = val(cur, sid, obs)
            checks += 1
            is_null = present and got is None
            ok = (is_null == want_null)
            state = "NULL" if is_null else ("absent" if not present else str(got))
            print(f"  {'OK ' if ok else 'FAIL'}  {sid:<16} {obs}  {state:<12} "
                  f"expect {'NULL' if want_null else 'a value'}   {note}")
            if not ok:
                fails.append(f"{sid} {obs}: {state}, expected {'NULL' if want_null else 'value'}")

        print("\n=== revisions, read point-in-time ===")
        for sid, month, asof, want, note in CHANGE_AS_OF:
            cur.execute(CHANGE_SQL, {"sid": sid, "m": month, "asof": asof})
            row = cur.fetchone()
            got = None if row is None or row[0] is None else float(row[0])
            checks += 1
            ok = got is not None and abs(got - want) < 1e-6
            print(f"  {'OK ' if ok else 'FAIL'}  {sid} {month} as of {asof}  "
                  f"got {got}  want {want}   {note}")
            if not ok:
                fails.append(f"{sid} {month} as of {asof}: got {got}, want {want}")

        print("\n=== supersector decomposition ===")
        # The strongest integrity check available for the sector panels: if the
        # fourteen supersectors do not sum to total nonfarm, one is missing,
        # duplicated, or is not actually a supersector. Rounding alone should
        # leave well under 1k.
        cur.execute("""
            WITH sect AS (
              SELECT observation_dt, sum(value) AS parts
              FROM macro_observations_current
              WHERE series_id IN ('USMINE','USCONS','MANEMP','USWTRADE','USTRADE',
                                  'CES4300000001','CES4422000001','USINFO','USFIRE',
                                  'USPBS','USEHS','USLAH','USSERV','USGOVT')
              GROUP BY 1 HAVING count(*) = 14),
                 tot AS (SELECT observation_dt, value AS total
                         FROM macro_observations_current WHERE series_id='PAYEMS')
            SELECT count(*), max(abs(s.parts - t.total))
            FROM tot t JOIN sect s USING (observation_dt)""")
        months, worst = cur.fetchone()
        checks += 1
        ok = months > 600 and worst is not None and float(worst) < 1.0
        print(f"  {'OK ' if ok else 'FAIL'}  14 supersectors sum to PAYEMS over {months} months, "
              f"worst residual {worst}k  (expect <1k)")
        if not ok:
            fails.append(f"supersector decomposition: {months} months, worst residual {worst}")

        print("\n=== order-of-magnitude sanity on the newest value ===")
        # Calibrated to catch a UNITS change, not an economic shock. JOLTS
        # levels arrive in thousands and weekly claims in persons (CLAUDE.md
        # trap 7); a source switching silently is a factor of 1000. Initial
        # claims went from 200k to 6.9m in a fortnight in 2020, so a bound tight
        # enough to flag that would have frozen the dashboards in the most
        # important week the series ever had.
        cur.execute("""
            WITH cur AS (
              SELECT DISTINCT ON (series_id, observation_dt)
                     series_id, observation_dt, value
              FROM macro_observations WHERE value IS NOT NULL
              ORDER BY series_id, observation_dt, vintage_dt DESC),
            latest AS (
              SELECT DISTINCT ON (series_id) series_id, observation_dt, value
              FROM cur ORDER BY series_id, observation_dt DESC),
            hist AS (
              SELECT c.series_id,
                     min(abs(c.value)) FILTER (WHERE c.value <> 0) AS lo,
                     max(abs(c.value)) AS hi
              FROM cur c JOIN latest l USING (series_id)
              WHERE c.observation_dt < l.observation_dt
              GROUP BY 1)
            SELECT l.series_id, l.observation_dt, l.value, h.lo, h.hi
            FROM latest l JOIN hist h USING (series_id)
            WHERE abs(l.value) > h.hi * 10
               OR (l.value <> 0 AND h.lo IS NOT NULL AND abs(l.value) < h.lo / 10)
            ORDER BY 1""")
        odd = cur.fetchall()
        checks += 1
        print(f"  {'OK ' if not odd else 'FAIL'}  every newest value within 10x of its "
              f"own history ({len(odd)} outside)")
        for sid, obs, v, lo, hi in odd:
            print(f"        {sid} {obs} = {v}, history {lo} .. {hi}")
            fails.append(f"{sid} {obs}={v} is outside 10x of its history ({lo}..{hi})")

        print("\n=== no series lost observations against the shipped bundle ===")
        # The exporter writes the bundles the site serves. If the database now
        # holds fewer observations than the bundle already on disk, a fetch
        # dropped history and the export must not overwrite good data with it.
        cur.execute("""
            SELECT series_id, count(*) FROM (
              SELECT DISTINCT ON (series_id, observation_dt) series_id, value
              FROM macro_observations ORDER BY series_id, observation_dt, vintage_dt DESC) t
            WHERE value IS NOT NULL GROUP BY 1""")
        db_counts = dict(cur.fetchall())
        bundles = Path(__file__).resolve().parent.parent / "data" / "v1" / "dashboards"
        lost, compared = [], 0
        for path in sorted(bundles.glob("*.json")):
            for sid, e in json.loads(path.read_text(encoding="utf-8"))["series"].items():
                if e.get("derived") or sid not in db_counts:
                    continue
                shipped = sum(1 for v in e["values"] if v is not None)
                compared += 1
                if db_counts[sid] < shipped:
                    lost.append((sid, db_counts[sid], shipped))
        checks += 1
        print(f"  {'OK ' if not lost else 'FAIL'}  {compared} series compared against the "
              f"bundles on disk ({len(lost)} shrank)")
        for sid, now, was in sorted(set(lost)):
            print(f"        {sid}: database has {now}, bundle already has {was}")
            fails.append(f"{sid} lost observations: {now} < {was} already shipped")

        print("\n=== freshness, by release ===")
        # Measured from the last vintage, not the last observation date: a
        # quarterly series whose newest observation is April is not stale in
        # September if it was published in July. This warns rather than fails
        # unless the delay is absurd — a genuine publication delay is not a
        # data-integrity problem, and failing would freeze the site over it.
        CADENCE_DAYS = {"weekly": 14, "monthly": 45, "quarterly": 130}
        cur.execute("""
            SELECT r.release_id, r.cadence, max(o.vintage_dt)::date, max(o.observation_dt)
            FROM macro_releases r
            JOIN macro_series_meta m ON m.release_id = r.release_id
            JOIN macro_observations o ON o.series_id = m.series_id
            GROUP BY 1,2 ORDER BY 1""")
        today = date.today()
        for rid, cadence, last_vin, last_obs in cur.fetchall():
            limit = CADENCE_DAYS.get(cadence, 45)
            age = (today - last_vin).days
            checks += 1
            if age > limit * 3:
                print(f"  FAIL  {rid:<28} last new data {age}d ago (limit {limit}d)")
                fails.append(f"{rid} has had no new data for {age} days")
            else:
                flag = "OK " if age <= limit else "warn"
                print(f"  {flag}  {rid:<28} last new data {age:>3}d ago, newest "
                      f"observation {last_obs}  (expect within {limit}d)")

        print("\n=== structural ===")
        cur.execute("""
            SELECT count(*) FROM (
              SELECT series_id, observation_dt, vintage_dt
              FROM macro_observations
              GROUP BY 1,2,3 HAVING count(*) > 1) d""")
        dups = cur.fetchone()[0]
        checks += 1
        print(f"  {'OK ' if dups == 0 else 'FAIL'}  duplicate (series, obs, vintage) keys: {dups}")
        if dups:
            fails.append(f"{dups} duplicate keys")

        cur.execute("""
            SELECT count(*) FROM macro_series_meta m
            WHERE NOT EXISTS (SELECT 1 FROM macro_observations o
                              WHERE o.series_id = m.series_id)""")
        empty = cur.fetchone()[0]
        checks += 1
        print(f"  {'OK ' if empty == 0 else 'FAIL'}  catalogued series with no observations: {empty}")
        if empty:
            fails.append(f"{empty} series have no data")

        cur.execute("SELECT count(*), count(DISTINCT (series_id, observation_dt)), "
                    "min(observation_dt), max(observation_dt) FROM macro_observations")
        rows, obs, lo, hi = cur.fetchone()
        print(f"\n  {rows} vintage rows over {obs} observations, {lo} .. {hi}")

    print(f"\n{checks - len(fails)}/{checks} checks passed")
    if fails:
        print("\nFAILURES:", file=sys.stderr)
        for f in fails:
            print("  " + f, file=sys.stderr)
        return 1
    print("ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
