#!/usr/bin/env python3
"""Push a reminder when a dashboard with a forecast record releases tomorrow
and no call has been recorded for it.

Calendar-driven, nothing typed: the release dates come from
`macro_release_dates` (the same table the refresh polls), the dashboards that
carry forecasts are the ones with a `forecasts.json` beside their page, and
the reference period the next release covers is the bundle's current
`ref_period` plus one cadence step. A record for that period means the call
is made and nothing is sent. Silence therefore means either "nothing due" or
"already done"; the push only ever says "due tomorrow and missing".

Runs daily from `systemd/macro-forecast-reminder.timer` at 08:00 Europe/London,
which is the morning of the day before a US release at 08:30 ET. The window is
36 hours so that morning catches it and the morning before does not.

Exit 0 always: a reminder that can fail the timer it runs from is worse than
no reminder, and the timer watchdog already alarms if this unit stops firing.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sys
from pathlib import Path

import httpx
import psycopg
import yaml

ROOT = Path(__file__).resolve().parent.parent
WINDOW_HOURS = 36
STEP = {"monthly": 1, "quarterly": 3, "annual": 12}


def log(msg: str) -> None:
    print(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%SZ}  {msg}", flush=True)


def notify(title: str, body: str, priority: str = "high", tags: str = "calendar") -> None:
    url = os.environ.get("NTFY_URL", "").strip()
    if not url:
        log("NTFY_URL unset; would have sent: " + title)
        return
    try:
        httpx.post(url, content=body.encode("utf-8"), timeout=10,
                   headers={"Title": title, "Priority": priority, "Tags": tags})
        log("notified: " + title)
    except Exception as exc:  # noqa: BLE001
        log(f"notify failed ({type(exc).__name__}); continuing")


def next_period(ref_period: str, cadence: str) -> str:
    y, m = int(ref_period[:4]), int(ref_period[5:7])
    m += STEP.get(cadence, 1)
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-01"


def main() -> int:
    specs = []
    for f in sorted(glob.glob(str(ROOT / "dashboards" / "*.yml"))):
        spec = yaml.safe_load(open(f, encoding="utf-8"))
        rec = ROOT / "site" / spec["path"] / "forecasts.json"
        if rec.exists():
            specs.append((spec, rec))
    if not specs:
        log("no dashboard carries a forecast record; nothing to do")
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    with psycopg.connect(os.environ["MACRO_DSN"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT release_id, min(release_at) FROM macro_release_dates "
            "WHERE release_at > %s AND release_at <= %s GROUP BY 1",
            (now, now + dt.timedelta(hours=WINDOW_HOURS)))
        due = dict(cur.fetchall())

    for spec, rec in specs:
        rel = spec["release"]
        when = due.get(rel)
        if not when:
            log(f"{spec['id']}: {rel} not due within {WINDOW_HOURS}h")
            continue
        bundle_path = ROOT / "data" / "v1" / "dashboards" / f"{spec['id'].replace('.', '-')}.json"
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            r = bundle["releases"][rel]
            period = next_period(r["ref_period"], r.get("cadence", "monthly"))
        except Exception as exc:  # noqa: BLE001
            log(f"{spec['id']}: cannot read bundle ({type(exc).__name__}); reminding anyway")
            period = None
        doc = json.loads(rec.read_text(encoding="utf-8"))
        have = {x.get("for") for x in doc.get("forecasts", [])}
        et = when.astimezone(dt.timezone(dt.timedelta(hours=-4)))  # display only; ET offset in summer
        if period and period in have:
            log(f"{spec['id']}: {rel} due {when:%Y-%m-%d %H:%MZ}, record for {period} present")
            continue
        month = "" if not period else dt.date.fromisoformat(period).strftime("%B %Y")
        title = f"{spec['title']} releases tomorrow: no forecast recorded"
        body = (f"{r.get('name', rel) if period else rel} for {month or 'the next period'} "
                f"is released {when:%a %d %b} at {when:%H:%M}Z. "
                f"No call is in site/{spec['path']}/forecasts.json yet. "
                f"Make it today (CLAUDE.md, Forecasts).")
        log(f"{spec['id']}: {body}")
        notify(title, body)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        log(f"reminder failed ({type(exc).__name__}: {exc}); exiting 0")
        sys.exit(0)
