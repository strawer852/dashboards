"""Check for new data, and if any arrived, take it all the way to the bundles.

Cheap by default. The keyless CSV endpoint is polled first because it costs
nothing and diff-on-write means an unchanged series writes no rows; only when
something actually moved does this pay for the expensive ALFRED re-fetch, the
validation pass and a re-export.

Order matters and is not negotiable: validate BEFORE export. A release that
fails its assertions must leave the previous bundles in place rather than
publish figures that disagree with the source.

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

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = str(ROOT / "venv" / "bin" / "python")
DSN = os.environ["MACRO_DSN"]
STATUS = ROOT / "data" / "v1" / "status.json"


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z  {msg}", flush=True)


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


def write_status(payload: dict) -> None:
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
        except Exception:                                  # noqa: BLE001
            prior = {}

    status = {
        "last_run": started.isoformat().replace("+00:00", "Z"),
        "scope": label,
        "changed": [],
        "ok": True,
        "error": None,
        "last_change": prior.get("last_change"),
    }

    sids = series_for(args.releases)
    if not sids:
        status["ok"] = False
        status["error"] = f"no series for releases {args.releases}"
        write_status(status)
        log(status["error"])
        return 1

    rc, out = run("ingest.py", "--series", *sids)
    tail = [l for l in out.strip().splitlines() if l.strip()][-1:]
    log(f"ingest rc={rc} {tail[0] if tail else ''}")
    if rc != 0:
        status.update(ok=False, error="ingest failed")
        write_status(status)
        print(out[-2000:], file=sys.stderr)
        return 1

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
        # vintages for the affected series only.
        rc, out = run("backfill.py", "--series", *changed)
        log(f"backfill rc={rc} {out.strip().splitlines()[-1] if out.strip() else ''}")
        if rc != 0:
            status.update(ok=False, error="backfill failed")
            write_status(status)
            print(out[-2000:], file=sys.stderr)
            return 1

    rc, out = run("validate.py")
    passed = [l for l in out.splitlines() if "checks passed" in l]
    log(f"validate rc={rc} {passed[0].strip() if passed else ''}")
    if rc != 0:
        # Deliberately do NOT export. The previous bundles keep serving.
        status.update(ok=False, error="validation failed; bundles left untouched")
        write_status(status)
        print(out[-3000:], file=sys.stderr)
        return 1

    rc, out = run("export.py")
    log(f"export rc={rc}")
    if rc != 0:
        status.update(ok=False, error="export failed")
        write_status(status)
        print(out[-2000:], file=sys.stderr)
        return 1
    for line in out.strip().splitlines():
        if line.strip():
            log("  " + line.strip())

    if changed:
        status["last_change"] = status["last_run"]
    write_status(status)
    log("refresh done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
