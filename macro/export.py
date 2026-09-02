"""Export dashboard JSON bundles from the macro database.

One bundle per dashboard, so a page makes a single request. Each series carries
its current-vintage values and, where revision history exists, the first-print
series alongside — which is what the payroll revision overlay reads.

Dates are emitted as `start` + `step` when the observation dates are genuinely
regular, and as an explicit `dates` array when they are not. Regularity is
CHECKED, not assumed: a weekly series with a missing week would otherwise be
silently re-dated by the reconstruction on the page.

Coverage is asserted at the end. A catalogued series that no dashboard consumes
is a gap nothing else would surface.

Usage:  venv/bin/python export.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
import yaml

DSN = os.environ["MACRO_DSN"]
SPEC_DIR = Path(__file__).resolve().parent.parent / "dashboards"
SCHEMA_VERSION = 1

# Release dates stated in the source documents. Only what a release actually
# says — nothing inferred, so the page never shows a made-up "next" date.
NEXT_RELEASE = {
    "bls.employment_situation": "2026-09-04T12:30:00Z",   # 8:30 a.m. ET, per USDL-26-1291
}

STEP_DAYS = {"D": 1, "W": 7}

# The period-on-period change AS FIRST PUBLISHED. This cannot be derived on the
# page from the first_print levels: differencing two first prints subtracts
# values from two DIFFERENT vintages. The real figure reads both periods at the
# vintage of the later one's first print — which is what the release quotes.
# Verified against USDL-26-1291: June first reported +57k, revised to +20k.
FIRST_REPORTED_SQL = """
WITH firsts AS (
  SELECT observation_dt, min(vintage_dt) AS v
  FROM macro_observations WHERE series_id = %(sid)s GROUP BY 1
)
SELECT f.observation_dt,
       (SELECT o.value FROM macro_observations o
         WHERE o.series_id = %(sid)s AND o.observation_dt = f.observation_dt
           AND o.vintage_dt <= f.v ORDER BY o.vintage_dt DESC LIMIT 1)
     - (SELECT o.value FROM macro_observations o
         WHERE o.series_id = %(sid)s
           AND o.observation_dt = (f.observation_dt - %(step)s::interval)::date
           AND o.vintage_dt <= f.v ORDER BY o.vintage_dt DESC LIMIT 1)
FROM firsts f ORDER BY 1
"""
STEP_INTERVAL = {"M": "1 month", "Q": "3 months", "A": "1 year",
                 "W": "7 days", "D": "1 day"}


def regular_step(dates: list[date], freq: str):
    """Return a step token if the dates are evenly spaced, else None."""
    if len(dates) < 3:
        return None
    if freq in ("M", "Q", "A"):
        months = {"M": 1, "Q": 3, "A": 12}[freq]
        for a, b in zip(dates, dates[1:]):
            if (b.year - a.year) * 12 + (b.month - a.month) != months or b.day != a.day:
                return None
        return freq
    if freq in STEP_DAYS:
        want = STEP_DAYS[freq]
        for a, b in zip(dates, dates[1:]):
            if (b - a).days != want:
                return None
        return freq
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "v1"))
    args = ap.parse_args()
    out_root = Path(args.out) / "dashboards"
    out_root.mkdir(parents=True, exist_ok=True)

    specs = [yaml.safe_load(p.read_text(encoding="utf-8"))
             for p in sorted(SPEC_DIR.glob("*.yml"))]
    if not specs:
        print(f"no specs in {SPEC_DIR}", file=sys.stderr)
        return 1

    consumed: set[str] = set()
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT series_id, release_id FROM macro_series_meta")
        by_release = defaultdict(list)
        for sid, rel in cur.fetchall():
            by_release[rel].append(sid)

        cur.execute("SELECT series_id, title, frequency, seasonal_adjustment, "
                    "companion_series_id, importance, release_id, source_url, unit "
                    "FROM macro_series_meta")
        meta = {r[0]: r for r in cur.fetchall()}

        for spec in specs:
            wanted: list[str] = []
            for rel in spec.get("include_releases", []):
                wanted += by_release.get(rel, [])
            wanted += spec.get("include_series", [])
            wanted = sorted(set(wanted), key=lambda s: (-meta[s][5], s))
            consumed.update(wanted)

            series_out: dict = {}
            for sid in wanted:
                cur.execute(
                    "SELECT observation_dt, value FROM macro_observations_current "
                    "WHERE series_id=%s ORDER BY observation_dt", (sid,))
                rows = cur.fetchall()
                if not rows:
                    print(f"!! {spec['id']}: {sid} has no observations", file=sys.stderr)
                    continue
                dates = [r[0] for r in rows]
                values = [None if r[1] is None else float(r[1]) for r in rows]

                cur.execute(
                    "SELECT observation_dt, value FROM macro_observations_first "
                    "WHERE series_id=%s ORDER BY observation_dt", (sid,))
                firsts = {d: (None if v is None else float(v)) for d, v in cur.fetchall()}
                first_print = [firsts.get(d) for d in dates]
                # Only worth shipping when it differs from the current vintage.
                if all(a == b for a, b in zip(first_print, values)):
                    first_print = None

                _, title, freq, sa, companion, importance, rel, url, unit = meta[sid]
                entry = {
                    "title": title,
                    "frequency": freq,
                    "sa": sa,
                    "release": rel,
                    "importance": importance,
                    "source_url": url,
                    "values": values,
                }
                if unit:
                    entry["unit"] = unit
                if companion:
                    entry["companion"] = companion
                step = regular_step(dates, freq)
                if step:
                    entry["start"] = dates[0].isoformat()
                    entry["step"] = step
                else:
                    entry["dates"] = [d.isoformat() for d in dates]
                if first_print:
                    entry["first_print"] = first_print
                if sid in spec.get("first_reported_change", []):
                    cur.execute(FIRST_REPORTED_SQL,
                                {"sid": sid, "step": STEP_INTERVAL[freq]})
                    frd = {d: (None if v is None else float(v)) for d, v in cur.fetchall()}
                    entry["first_reported_diff"] = [frd.get(d) for d in dates]
                series_out[sid] = entry

            rel_ids = sorted({v["release"] for v in series_out.values()})
            cur.execute(
                "SELECT r.release_id, r.name, r.agency, r.cadence, "
                "       max(o.vintage_dt), max(o.observation_dt) "
                "FROM macro_releases r "
                "JOIN macro_series_meta m ON m.release_id = r.release_id "
                "JOIN macro_observations o ON o.series_id = m.series_id "
                "WHERE r.release_id = ANY(%s) GROUP BY 1,2,3,4", (rel_ids,))
            releases = {}
            for rid, name, agency, cadence, last_vin, last_obs in cur.fetchall():
                releases[rid] = {
                    "name": name, "agency": agency, "cadence": cadence,
                    "released_at": last_vin.isoformat().replace("+00:00", "Z"),
                    "ref_period": last_obs.isoformat(),
                }
                if rid in NEXT_RELEASE:
                    releases[rid]["next_at"] = NEXT_RELEASE[rid]

            bundle = {
                "schema": SCHEMA_VERSION,
                "id": spec["id"],
                "path": spec["path"],
                "region": spec["region"],
                "topic": spec["topic"],
                "title": spec["title"],
                "release": spec["release"],
                "generated_at": generated,
                "releases": releases,
                "series": series_out,
            }

            dest = out_root / (spec["path"].replace("/", "-") + ".json")
            tmp = dest.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
            tmp.replace(dest)            # atomic: no reader sees a half-written file
            kb = dest.stat().st_size / 1024
            withrev = sum(1 for v in series_out.values() if "first_print" in v)
            print(f"{spec['id']:<34} {len(series_out):>3} series  "
                  f"{withrev:>2} with revisions  {kb:>7.1f} KB  -> {dest.name}")

        cur.execute("SELECT series_id FROM macro_series_meta")
        orphans = sorted({r[0] for r in cur.fetchall()} - consumed)

    if orphans:
        print(f"\n!! {len(orphans)} catalogued series consumed by no dashboard: "
              f"{', '.join(orphans)}", file=sys.stderr)
        return 1
    print("\nall catalogued series are consumed by at least one dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
