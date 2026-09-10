"""Check for new data, and if any arrived, take it all the way to the bundles.

Cheap by default. The keyless CSV endpoint is polled first because it costs
nothing and diff-on-write means an unchanged series writes no rows; only when
something actually moved does this pay for the expensive ALFRED re-fetch, the
validation pass and a re-export.

Order matters and is not negotiable: validate BEFORE export. A release that
fails its assertions must leave the previous bundles in place rather than
publish figures that disagree with the source. That failure is invisible on the
page - a stale dashboard looks entirely normal - so it is also pushed.

Usage:
  refresh.py                      # every series
  refresh.py --releases eta.claims
  refresh.py --force              # re-export even when nothing changed
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = str(ROOT / "venv" / "bin" / "python")
DSN = os.environ["MACRO_DSN"]
STATUS = ROOT / "data" / "v1" / "status.json"
NL = "\n"


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z  {msg}", flush=True)


def notify(title: str, body: str, priority: str = "default", tags: str = "") -> None:
    """Push an alert, if one is configured.

    Alerting must never be able to break the pipeline: a push failure is logged
    and swallowed. The refresh succeeding matters more than being told about it.
    """
    url = os.environ.get("NTFY_URL", "").strip()
    if not url:
        return
    try:
        httpx.post(url, content=body.encode("utf-8"), timeout=10,
                   headers={"Title": title, "Priority": priority, "Tags": tags})
        log(f"notified: {title}")
    except Exception as exc:                                   # noqa: BLE001
        log(f"notify failed ({type(exc).__name__}); continuing")


def run(script: str, *args: str) -> tuple[int, str]:
    p = subprocess.run([PY, str(HERE / script), *args],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def series_for(releases: list[str] | None) -> list[str]:
    """Every catalogued series for these releases, whatever its source.

    This used to say `WHERE source='fred'` in both branches, and so no
    scheduled run had ever refreshed a BLS-sourced series -- 37 of them,
    updated only when somebody ran ingest.py by hand. `ingest.py` dispatches on
    `macro_series_meta.source` and batches the BLS ids itself, so the filter
    belonged in neither branch. CLAUDE.md trap 35.

    Do not reintroduce a source filter here. If a source ever needs excluding
    from a scheduled run, that is a property of the series -- give it a column
    and read it -- not a literal in the orchestrator.
    """
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        if releases:
            cur.execute("SELECT series_id FROM macro_series_meta "
                        "WHERE release_id = ANY(%s) ORDER BY 1",
                        (releases,))
        else:
            cur.execute("SELECT series_id FROM macro_series_meta ORDER BY 1")
        return [r[0] for r in cur.fetchall()]


def releases_of(series: list[str]) -> list[str]:
    """The releases these series belong to.

    The success alert named the releases POLLED, so on 10 September 2026 the
    push read "New data: bls.ppi,eta.claims" when only claims had landed and
    FRED still had July's PPI. On a day two releases share, that says the
    wrong one arrived.
    """
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT release_id FROM macro_series_meta "
                    "WHERE series_id = ANY(%s) ORDER BY 1", (series,))
        return [r[0] for r in cur.fetchall()]


def changed_since(ts: datetime) -> list[str]:
    """Series that gained rows during this run."""
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT series_id FROM macro_observations "
                    "WHERE vintage_dt >= %s ORDER BY 1", (ts,))
        return [r[0] for r in cur.fetchall()]


# Everything below is asked in America/New_York, because that is the timezone the
# releases are scheduled in and the one the timers already fire on.
_CAL_USABLE = """
SELECT count(*) FROM macro_release_dates
WHERE release_id = ANY(%s) AND release_at >= now() - interval '1 day'
"""
_CAL_DUE_TODAY = """
SELECT count(*) FROM macro_release_dates
WHERE release_id = ANY(%s)
  AND (release_at AT TIME ZONE 'America/New_York')::date
    = (now() AT TIME ZONE 'America/New_York')::date
"""
# Which (release, source) pairs dated today have not landed yet. A release has
# landed only when EVERY source feeding it has written something since its
# embargo -- judged per source, not per release. ingest.py stamps each new row
# with the fetch time; the ALFRED backfill then replaces a FRED row's stamp with
# its publication date (00:00 UTC), while a BLS or BEA row keeps its fetch time
# for ever. The first version asked "is there any row dated today", so on a CPI
# morning the 270 BLS-API items -- published at 08:30, fetched at 08:35 -- would
# have answered yes for the whole release while the FRED headline was still an
# hour away, and every later window would have stood down until the 01:40
# sweep. Six of ten releases mix sources; CPI on 11 September 2026 was the first
# to meet --due since trap 35 let BLS series reach ingest. CLAUDE.md trap 65.
#
# "Landed" is the distinction export.py already draws: a publication vintage
# (00:00 UTC) on the release date, or a fetch-time vintage at or after the
# embargo. A fetch before the embargo -- the 01:40 ET sweep catching something
# unrelated -- is not the release.
#
# Still resolved per release, which is trap 33: two releases sharing a day are
# judged separately, so the first to land cannot silence the second.
_OUTSTANDING = """
WITH today AS (
  SELECT DISTINCT d.release_id, d.release_at
  FROM macro_release_dates d
  WHERE (d.release_at AT TIME ZONE 'America/New_York')::date
      = (now() AT TIME ZONE 'America/New_York')::date
), pairs AS (
  SELECT DISTINCT t.release_id, t.release_at, m.source
  FROM today t JOIN macro_series_meta m ON m.release_id = t.release_id
)
SELECT p.release_id, p.source, p.release_at <= now() AS past_embargo
FROM pairs p
WHERE NOT EXISTS (
  SELECT 1 FROM macro_observations o
  JOIN macro_series_meta m USING (series_id)
  WHERE m.release_id = p.release_id
    AND m.source = p.source
    AND o.vintage_dt >= ((p.release_at AT TIME ZONE 'America/New_York')::date)::timestamp
                        AT TIME ZONE 'UTC'
    AND (o.vintage_dt >= p.release_at
         OR (o.vintage_dt AT TIME ZONE 'UTC')::time = '00:00'))
ORDER BY 1, 2
"""

# A forward calendar with nothing in it is not a quiet day, it is a broken
# calendar -- and --due would then poll nothing, for ever, in silence. The
# sweep refreshes this daily, so emptiness here means that has been failing.
_CAL_FORWARD = """
SELECT count(*) FROM macro_release_dates WHERE release_at >= now() - interval '1 day'
"""

# The vintage side is read in UTC and the calendar side in Eastern, which looks
# wrong and is not. An ALFRED vintage is stored at MIDNIGHT UTC of its realtime
# date, so `2026-09-04 00:00+00` is the 4 September vintage -- but read in
# America/New_York that timestamp is the 3rd, and the first guard never matched:
# on 4 September the release landed at 13:35Z and the windows at 13:45Z and
# 13:55Z each fetched all 64,220 observations again (trap 34). _OUTSTANDING
# bounds the vintage by midnight UTC of the release's Eastern date for the same
# reason. export.py identifies these rows the same way, by their 00:00:00 UTC.


def nothing_to_poll_for(releases: list[str]) -> str | None:
    """Why this run can stop now, or None to carry on.

    Fails open on purpose: with no usable calendar rows this returns None and
    the run proceeds. A gate that can silence the pipeline when its own inputs
    are missing is worse than no gate.
    """
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute(_CAL_USABLE, (releases,))
        if cur.fetchone()[0] == 0:
            return None                      # no calendar to judge by
        cur.execute(_CAL_DUE_TODAY, (releases,))
        if cur.fetchone()[0] == 0:
            return "nothing scheduled today; not polling"
        cur.execute(_OUTSTANDING)
        if not [r for r in cur.fetchall() if r[0] in releases]:
            return "today's release has landed from every source; not polling again"
    return None


def releases_due_now() -> list[str] | None:
    """Releases the calendar says are outstanding, or None if it cannot say.

    Outstanding: dated today, past its embargo, and not yet landed from every
    source that feeds it.
    """
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute(_CAL_FORWARD)
        if cur.fetchone()[0] == 0:
            return None
        cur.execute(_OUTSTANDING)
        return sorted({r[0] for r in cur.fetchall() if r[2]})


def catalogue_size() -> dict:
    """Series and vintage-row counts, for the landing page to state.

    Counted here rather than typed there. The page said "53 series, 231,000
    vintage rows" for weeks after it was 78 and 259,000, because a sentence and
    a database have no way of disagreeing out loud.
    """
    try:
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM macro_series_meta")
            series = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM macro_observations")
            rows = cur.fetchone()[0]
        return {"series": series, "vintage_rows": rows}
    except Exception:                                          # noqa: BLE001
        # Never let a count break a refresh: the page falls back to saying
        # nothing rather than saying something wrong.
        return {}


def write_status(payload: dict) -> None:
    payload = {**payload, **catalogue_size()}
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(STATUS)          # atomic: no reader sees a half-written file


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--releases", nargs="*")
    ap.add_argument("--due", action="store_true",
                    help="fetch whatever the release calendar says is "
                         "outstanding, instead of a list typed into a unit file")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)

    # --due turns the schedule into a question asked of the catalogue. A new
    # release needs a calendar row and nothing else -- no unit file, and nobody
    # remembering. CPI and PPI shipped with no timer at all for exactly that
    # reason, and were a day stale after every release until somebody noticed.
    if args.due:
        due = releases_due_now()
        if due is None:
            log("refresh start (--due): forward calendar is EMPTY; not polling")
            notify("Release calendar is empty",
                   "macro_release_dates holds no future rows, so --due has "
                   "nothing to act on. The daily sweep refreshes it; that is "
                   "what to look at.", "high", "warning")
            return 1
        if not due:
            log("refresh start (--due): nothing outstanding; not polling")
            return 0
        args.releases = due

    label = ",".join(args.releases) if args.releases else "all"
    log(f"refresh start ({label})")

    prior = {}
    if STATUS.exists():
        try:
            prior = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            prior = {}

    status = {
        "last_run": started.isoformat().replace("+00:00", "Z"),
        "scope": label,
        "changed": [],
        "ok": True,
        "error": None,
        "last_change": prior.get("last_change"),
    }

    def fail(stage: str, title: str, body: str, out: str, tags: str) -> int:
        status.update(ok=False, error=stage)
        write_status(status)
        notify(title, body, "high", tags)
        print(out[-3000:], file=sys.stderr)
        return 1

    # The forward release calendar, on the full sweep only: it changes rarely
    # and doing it every window would be seven needless API calls an hour.
    # The stamp's "Next" date reads from it, so it must not be left to age --
    # it was a hard-coded literal until 4 September 2026, when the release it
    # named happened and the page began advertising it as still to come.
    # Auxiliary, so a failure is logged and does not abort the refresh.
    if args.releases is None:
        rc, out = run("release_dates.py")
        last = out.strip().splitlines()[-1] if out.strip() else ""
        log(f"release dates rc={rc} {last}")

    # Before the first FRED call. --force skips it: a forced run is a person
    # asking, and the calendar does not get to argue.
    if args.releases and not args.force:
        why = nothing_to_poll_for(args.releases)
        if why:
            log(why)
            write_status(status)
            return 0

    sids = series_for(args.releases)
    if not sids:
        return fail(f"no series for releases {args.releases}",
                    "Dashboard refresh misconfigured",
                    f"No catalogued series for {label}.", "", "warning")

    rc, out = run("ingest.py", "--series", *sids)
    tail = [l for l in out.strip().splitlines() if l.strip()][-1:]
    log(f"ingest rc={rc} {tail[0] if tail else ''}")
    if rc != 0:
        return fail("ingest failed", "Dashboard refresh failed",
                    f"Fetch failed ({label}).{NL}{NL}{out[-600:]}", out, "warning")

    changed = changed_since(started)
    status["changed"] = changed

    if not changed and not args.force:
        log("no new observations; nothing to do")
        write_status(status)
        return 0

    if changed:
        log(f"changed: {', '.join(changed)}")
        # ALFRED is authoritative. The rows just written carry a fetch-time
        # vintage as a placeholder; this replaces them with real realtime_start
        # vintages, for the affected series only.
        rc, out = run("backfill.py", "--series", *changed)
        last = out.strip().splitlines()[-1] if out.strip() else ""
        log(f"backfill rc={rc} {last}")
        if rc != 0:
            return fail("backfill failed", "Dashboard refresh failed",
                        f"ALFRED backfill failed for {', '.join(changed)}."
                        f"{NL}{NL}{out[-600:]}", out, "warning")

    rc, out = run("validate.py")
    passed = [l for l in out.splitlines() if "checks passed" in l]
    log(f"validate rc={rc} {passed[0].strip() if passed else ''}")
    if rc != 0:
        # Deliberately do NOT export. The previous bundles keep serving, so the
        # site never shows figures that disagree with the published release.
        fails = [l.strip() for l in out.splitlines() if l.strip().startswith("FAIL")]
        detail = NL.join(fails[:8]) or out[-600:]
        return fail("validation failed; bundles left untouched",
                    "Dashboard data FAILED validation",
                    "New data disagrees with the published release. The previous "
                    "bundles are still serving, so the site is not showing wrong "
                    f"numbers.{NL}{NL}{detail}", out, "rotating_light")

    rc, out = run("export.py")
    log(f"export rc={rc}")
    if rc != 0:
        return fail("export failed", "Dashboard export failed",
                    out[-600:], out, "warning")
    for line in out.strip().splitlines():
        if line.strip():
            log("  " + line.strip())

    if changed:
        status["last_change"] = status["last_run"]
        shown = ", ".join(changed[:14]) + ("..." if len(changed) > 14 else "")
        notify(f"New data: {', '.join(releases_of(changed)) or label}",
               f"{len(changed)} series updated and published.{NL}{shown}",
               "default", "chart_with_upwards_trend")
    write_status(status)
    log("refresh done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
