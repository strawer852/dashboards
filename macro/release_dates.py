"""Sync the forward release calendar from FRED into macro_release_dates.

The stamp's "Next" date was a hard-coded constant in export.py. It was correct
until 08:30 on 4 September 2026 and wrong one second later, because the release
it named had happened -- the page then advertised the next Employment Situation
as the one already on screen. That is the trap-18 shape again: a fact that has
to be retyped at every release, with nothing to notice when it is not.

FRED publishes the forward calendar for each release and its own `/series/release`
endpoint says which release a series belongs to, so nothing here is typed by
hand: the FRED release id is discovered from a series we already hold. Six of
the seven releases we track have a calendar; the Atlanta Fed wage tracker has
none, so it gets no rows and its stamp shows no "Next" rather than a guess.

The one thing FRED does not give is the time of day -- its calendar is dates
only. The times below are stated in the releases themselves and are stable
policy, not inference:

    08:30 ET  Employment Situation, CPI, ECI, Productivity and Costs,
              ETA weekly claims (national, Thursdays; the state report,
              a separate FRED release, Fridays), Personal Income and Outlays
              (each news release carries "8:30 a.m. (ET)")
    10:00 ET  JOLTS               (matches the 10:05 ET refresh window)

Run it from the daily sweep; the calendar changes rarely and a stale future
date is caught by export refusing to show one that has already passed.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

import httpx
import psycopg

import fred

DSN = os.environ["MACRO_DSN"]
ET = ZoneInfo("America/New_York")

# Time of day each release publishes, from the releases' own text.
RELEASE_TIME = {
    "bls.employment_situation": time(8, 30),
    "bls.cpi":                  time(8, 30),
    "bls.ppi":                  time(8, 30),
    "bls.eci":                  time(8, 30),
    "bls.productivity":         time(8, 30),
    "eta.claims":               time(8, 30),
    "eta.state_claims":         time(8, 30),
    "bea.personal_income":      time(8, 30),
    "bls.jolts":                time(10, 0),
}

UPSERT = """
INSERT INTO macro_release_dates (release_id, release_at, ref_period, status)
VALUES (%(rid)s, %(at)s, NULL, 'scheduled')
ON CONFLICT (release_id, release_at) DO NOTHING
"""


def main() -> int:
    today = datetime.now(ET).date().isoformat()
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        # The FRED release is discovered from series we hold -- and it is a
        # property of the SERIES, so two are asked, the first and last id in
        # the release. On 5 September 2026 the 106 state claims series joined
        # eta.claims and min(series_id) went from CC4WSA (FRED 180, Thursdays)
        # to AKCCLAIMS (FRED 469, the state report, Fridays): the calendar
        # quietly started filling with Fridays and would have stopped carrying
        # Thursdays once the rows stored before the change ran out. A release
        # here must map to exactly one FRED release; if the two probes
        # disagree the catalogue is wrong, and this says so loudly while
        # storing dates for BOTH, so the pipeline keeps polling on the right
        # days until somebody fixes the catalogue.
        cur.execute("SELECT release_id, min(series_id), max(series_id) "
                    "FROM macro_series_meta WHERE source = 'fred' "
                    "GROUP BY 1 ORDER BY 1")
        rows = cur.fetchall()

        total = 0
        with httpx.Client(timeout=fred.HTTP_TIMEOUT) as client:
            for rid, first, last in rows:
                tod = RELEASE_TIME.get(rid)
                if tod is None:
                    print(f"  {rid:<26} no published release time; skipped")
                    continue

                fids: dict[int, str] = {}
                for sid in sorted({first, last}):
                    r = client.get(f"{fred.FRED_BASE}/series/release",
                                   params={"series_id": sid, "api_key": fred.api_key(),
                                           "file_type": "json"})
                    r.raise_for_status()
                    rel = (r.json().get("releases") or [{}])[0]
                    if rel.get("id"):
                        fids.setdefault(rel["id"], sid)
                if not fids:
                    print(f"  {rid:<26} FRED has no release for {first}")
                    continue
                if len(fids) > 1:
                    print(f"  {rid:<26} !! spans {len(fids)} FRED releases: "
                          + ", ".join(f"{k} ({v})" for k, v in fids.items())
                          + " -- the catalogue mixes two releases; storing dates for all")

                for fid in fids:
                    r2 = client.get(f"{fred.FRED_BASE}/release/dates",
                                    params={"release_id": fid, "api_key": fred.api_key(),
                                            "file_type": "json", "sort_order": "asc",
                                            "include_release_dates_with_no_data": "true",
                                            "realtime_start": today, "limit": 24})
                    r2.raise_for_status()
                    dates = [d["date"] for d in r2.json().get("release_dates", [])]

                    n = 0
                    for d in dates:
                        y, m, dd = (int(x) for x in d.split("-"))
                        at = datetime(y, m, dd, tod.hour, tod.minute, tzinfo=ET)
                        cur.execute(UPSERT, {"rid": rid, "at": at})
                        n += cur.rowcount
                    total += n
                    print(f"  {rid:<26} fred_release={fid:<5} {len(dates):>2} dates, "
                          f"{n} new  next={dates[0] if dates else '-'}")
        conn.commit()
    print(f"\n{total} release date(s) stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
