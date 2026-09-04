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
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        if releases:
            cur.execute("SELECT series_id FROM macro_series_meta "
                        "WHERE source='fred' AND release_id = ANY(%s) ORDER BY 1",
                        (releases,))
        else:
            cur.execute("SELECT series_id FROM macro_series_meta "
                        "WHERE source='fred' ORDER BY 1")
        return [r[0] for r in cur.fetchall()]


def changed_since(ts: datetime) -> list[str]:
    """Series that gained rows during this run."""
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute("SELECT DISTINCT series_id FROM macro_observations "
                    "WHERE vintage_dt >= %s ORDER BY 1", (ts,))
        return [r[0] for r in cur.fetchall()]


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
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
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
        notify(f"New data: {label}",
               f"{len(changed)} series updated and published.{NL}{shown}",
               "default", "chart_with_upwards_trend")
    write_status(status)
    log("refresh done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
