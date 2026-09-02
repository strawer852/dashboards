"""Assert the loaded data reproduces the published July 2026 releases.

The news release PDF is the acceptance test. If the database and the PDF
disagree, the build is wrong — fail loudly rather than publish a dashboard that
quietly contradicts its own source.

Usage:  venv/bin/python validate.py
"""
from __future__ import annotations

import os
import sys

import psycopg

DSN = os.environ["MACRO_DSN"]

# (series, observation, expected, note) — from USDL-26-1291 and USDL-26-1432.
LEVELS = [
    ("UNRATE",        "2026-07-01",   4.1,   "unemployment rate"),
    ("CIVPART",       "2026-07-01",  61.4,   "participation rate"),
    ("EMRATIO",       "2026-07-01",  58.9,   "employment-population ratio"),
    ("CES0500000003", "2026-07-01",  37.62,  "avg hourly earnings, all employees"),
    ("AHETPI",        "2026-07-01",  32.40,  "avg hourly earnings, prod & nonsup"),
    ("AWHAETP",       "2026-07-01",  34.3,   "average weekly hours"),
    ("U6RATE",        "2026-07-01",   7.9,   "U-6"),
    ("JTSJOL",        "2026-07-01", 7271.0,  "job openings (7.3m)"),
]

# Month-on-month changes the release states explicitly.
CHANGES = [
    ("PAYEMS", "2026-06-01", "2026-07-01", -23.0, "July payroll change"),
    ("PAYEMS", "2026-05-01", "2026-06-01",  20.0, "June, as revised"),
    ("PAYEMS", "2026-04-01", "2026-05-01",  63.0, "May, as revised"),
]

# The shutdown gap is household-survey only: CPS series are genuinely empty for
# October 2025 while the establishment survey carries a value.
NULLS = [
    ("UNRATE",  "2025-10-01", True,  "CPS not collected"),
    ("CIVPART", "2025-10-01", True,  "CPS not collected"),
    ("EMRATIO", "2025-10-01", True,  "CPS not collected"),
    ("PAYEMS",  "2025-10-01", False, "CES was collected"),
]


def val(cur, sid, obs):
    cur.execute(
        "SELECT value FROM macro_observations_current "
        "WHERE series_id=%s AND observation_dt=%s", (sid, obs))
    row = cur.fetchone()
    return (None, False) if row is None else (row[0], True)


def main() -> int:
    fails: list[str] = []
    checks = 0

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        print("=== published levels ===")
        for sid, obs, want, note in LEVELS:
            got, present = val(cur, sid, obs)
            checks += 1
            ok = present and got is not None and abs(float(got) - want) < 1e-9
            print(f"  {'OK ' if ok else 'FAIL'}  {sid:<16} {obs}  got {got}  want {want}   {note}")
            if not ok:
                fails.append(f"{sid} {obs}: got {got}, want {want}")

        print("\n=== stated month-on-month changes ===")
        for sid, a, b, want, note in CHANGES:
            va, _ = val(cur, sid, a)
            vb, _ = val(cur, sid, b)
            checks += 1
            got = None if va is None or vb is None else float(vb) - float(va)
            ok = got is not None and abs(got - want) < 1e-6
            print(f"  {'OK ' if ok else 'FAIL'}  {sid:<16} {b}  got {got}  want {want}   {note}")
            if not ok:
                fails.append(f"{sid} change to {b}: got {got}, want {want}")

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

        cur.execute("SELECT count(*), min(observation_dt), max(observation_dt) FROM macro_observations")
        n, lo, hi = cur.fetchone()
        print(f"\n  {n} observations, {lo} .. {hi}")

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
