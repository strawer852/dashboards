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

import derived

DSN = os.environ["MACRO_DSN"]
SPEC_DIR = Path(__file__).resolve().parent.parent / "dashboards"
SCHEMA_VERSION = 1

# How late the earliest vintage may be and still count as a first print. One
# publication interval plus slack: a weekly figure first seen three months on
# has already been through the annual seasonal re-estimation, so calling it a
# first print would turn the edge of the archive into a finding.
FIRST_PRINT_GRACE = {"D": 14, "W": 28, "M": 100, "Q": 200, "A": 500}

# The next scheduled release, read from the calendar rather than typed here.
# This was a literal — "2026-09-04T12:30:00Z" — which was right until 08:30 that
# morning and wrong immediately after, when the page began advertising the next
# Employment Situation as the one already printed on it. A date that must be
# retyped every month is a date that will be wrong most months.
#
# macro_release_dates is filled from FRED's forward calendar by
# macro/release_dates.py. The `> now()` is what makes it self-correcting: the
# moment a release happens it stops being the next one, and a release with no
# calendar (the Atlanta Fed tracker) yields nothing and shows no "Next" at all,
# which is the same discipline released_at follows.
NEXT_RELEASE_SQL = """
SELECT release_id, min(release_at)
FROM macro_release_dates
WHERE release_id = ANY(%s) AND release_at > now()
GROUP BY 1
"""

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

    # A spec is a mapping with an id. Anything else in this directory is not one,
    # and must be skipped loudly rather than crashing the export: a stray YAML
    # file took the whole pipeline down once already.
    specs = []
    for path in sorted(SPEC_DIR.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "id" not in doc:
            print(f"!! {path.name} is not a dashboard spec (no id); skipping",
                  file=sys.stderr)
            continue
        specs.append(doc)
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
                    "companion_series_id, importance, release_id, source_url, unit, "
                    "vintage_mode "
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

                (_, title, freq, sa, companion, importance, rel, url, unit,
                 vintage_mode) = meta[sid]

                cur.execute(
                    "SELECT observation_dt, value, vintage_dt FROM macro_observations_first "
                    "WHERE series_id=%s ORDER BY observation_dt", (sid,))
                # A first print counts only when the earliest vintage we hold is
                # close enough to the observation to BE a first print. Older than
                # that and we are looking at the edge of the archive, not at an
                # unrevised figure.
                grace = FIRST_PRINT_GRACE.get(freq, 100)
                firsts = {}
                for d, v, vin in cur.fetchall():
                    if (vin.date() - d).days <= grace:
                        firsts[d] = None if v is None else float(v)
                first_print = [firsts.get(d) for d in dates]
                # Only worth shipping when it differs from the current vintage.
                if all(a == b for a, b in zip(first_print, values)):
                    first_print = None


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
                # 'fetch_date' means the source has no point-in-time history, so
                # the earliest stored vintage is the day ingestion began rather
                # than anything the agency ever published. Say so in the bundle.
                if vintage_mode == "fetch_date":
                    entry["vintages"] = "since_ingestion"
                    first_print = None
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
                    if vintage_mode == "fetch_date":
                        print(f"!! {spec['id']}: first_reported_change asks for "
                              f"{sid}, whose source has no vintage history",
                              file=sys.stderr)
                        return 1
                    cur.execute(FIRST_REPORTED_SQL,
                                {"sid": sid, "step": STEP_INTERVAL[freq]})
                    frd = {d: (None if v is None else float(v)) for d, v in cur.fetchall()}
                    entry["first_reported_diff"] = [frd.get(d) for d in dates]
                series_out[sid] = entry

            # Derived measures enter as ordinary series so the page renders them
            # with the existing panel types. Anything combining two vintages or
            # two series belongs here, never in the browser.
            for did in derived.build(spec, series_out):
                consumed.add(did)

            rel_ids = sorted({v["release"] for v in series_out.values()})
            # An ALFRED vintage is the date the figure was published and is
            # stored at midnight. A fetch-date vintage is just when we asked,
            # and carries a time of day -- so it can date nothing. Taking the
            # max over both reported a daily re-fetch as a release.
            cur.execute(
                "SELECT r.release_id, r.name, r.agency, r.cadence, "
                "       max(o.vintage_dt) FILTER (WHERE "
                "         (o.vintage_dt AT TIME ZONE 'UTC')::time "
                "         = '00:00:00'), "
                "       max(o.observation_dt) "
                "FROM macro_releases r "
                "JOIN macro_series_meta m ON m.release_id = r.release_id "
                "JOIN macro_observations o ON o.series_id = m.series_id "
                "WHERE r.release_id = ANY(%s) GROUP BY 1,2,3,4", (rel_ids,))
            releases = {}
            for rid, name, agency, cadence, last_vin, last_obs in cur.fetchall():
                releases[rid] = {
                    "name": name, "agency": agency, "cadence": cadence,
                    "ref_period": last_obs.isoformat(),
                }
                # A release with no published vintage yet -- a source that has
                # none, or one whose backfill has not run -- carries no date.
                # A date that cannot be sourced is worse than no date, so the
                # stamp omits it rather than showing when we last fetched.
                if last_vin is not None:
                    releases[rid]["released_at"] = \
                        last_vin.isoformat().replace("+00:00", "Z")

            cur.execute(NEXT_RELEASE_SQL, (rel_ids,))
            for rid, nxt in cur.fetchall():
                if rid in releases:
                    releases[rid]["next_at"] = \
                        nxt.isoformat().replace("+00:00", "Z")

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
