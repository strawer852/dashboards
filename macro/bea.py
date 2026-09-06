"""BEA API client — the third source, and the second without vintages.

FRED is preferred wherever it carries a series, because ALFRED is the only free
source of revision history. BEA is used for what FRED does not have: the PCE
item structure, 388 monthly price series against the 25 headline ones FRED
publishes, which is what a median or a breadth measure needs.

**These series carry no vintage history.** BEA serves the current estimate and
nothing else, so a BEA-sourced series accumulates vintages only from the day
ingestion starts. Their catalog rows are marked `vintage_mode = 'fetch_date'`
and no panel may offer a revision overlay on them. CLAUDE.md trap 15.

That limitation bites harder here than for BLS. PCE is revised heavily -- the
FRED-sourced headline series carry ten vintages per observation -- so the
detail behind a median will not show its own revisions even though the
aggregate above it does.

Request limits: 100 requests and 100 MB per minute, 30 errors per minute, and
exceeding any of them blocks the key for an hour. One table with Year=ALL is a
single request returning about 75 MB, so two tables cannot be fetched in the
same minute: `pace()` enforces that rather than trusting a caller to remember.

The table is addressed as "<dataset>:<TableName>" and stored per series in the
catalog's `dataset` column, so a second table needs no code change here.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date

import httpx
import archive
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

BEA_URL = "https://apps.bea.gov/api/data"
HTTP_TIMEOUT = httpx.Timeout(300.0, connect=15.0)

DEFAULT_TABLE = "NIUnderlyingDetail:U20404"
_MB_PER_MIN = 100.0
_last_fetch: list[tuple[float, float]] = []      # (when, megabytes)


class BeaError(Exception):
    pass


def api_key() -> str:
    """Read at call time, so importing this module never requires a key."""
    try:
        return os.environ["BEA_API_KEY"]
    except KeyError:
        raise BeaError("BEA_API_KEY is not set.") from None


def _retry():
    return Retrying(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, BeaError)),
        reraise=True,
    )


def pace(mb: float = 80.0) -> None:
    """Wait until another `mb` megabytes fits inside the 100 MB/minute limit.

    Breaching it blocks the key for an hour, which is far more expensive than
    waiting. Tracked here rather than left to callers, because a caller that
    forgets costs the whole pipeline its next run.
    """
    now = time.time()
    _last_fetch[:] = [(t, m) for t, m in _last_fetch if now - t < 60]
    used = sum(m for _, m in _last_fetch)
    if used + mb > _MB_PER_MIN:
        wait = 61 - (now - min(t for t, _ in _last_fetch))
        if wait > 0:
            logger.info("BEA: %.0f MB used in the last minute; waiting %.0fs",
                        used, wait)
            time.sleep(wait)
        _last_fetch.clear()


def parse_period(tp: str) -> date | None:
    """BEA period to an observation date. 2026M07 -> 2026-07-01.

    Quarterly (2026Q3) and annual (2026) are returned as the first month of the
    period, matching how every other source in this catalog is keyed. A period
    code that is none of those is skipped rather than guessed at.
    """
    tp = tp.strip()
    if len(tp) == 7 and tp[4] == "M":
        m = int(tp[5:])
        return date(int(tp[:4]), m, 1) if 1 <= m <= 12 else None
    if len(tp) == 6 and tp[4] == "Q":
        q = int(tp[5:])
        return date(int(tp[:4]), 3 * (q - 1) + 1, 1) if 1 <= q <= 4 else None
    if tp.isdigit() and len(tp) == 4:
        return date(int(tp), 1, 1)
    logger.warning("unrecognised BEA period %r", tp)
    return None


def parse_value(v: str | None) -> float | None:
    if v is None or str(v).strip() in ("", "-", ".", "(NA)", "(D)"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        logger.warning("unparseable BEA value: %r", v)
        return None


def get_table(spec: str = DEFAULT_TABLE, freq: str = "M",
              year: str = "ALL") -> dict[str, list[tuple[date, float | None]]]:
    """Every series in one NIPA table, keyed by BEA series code.

    One request returns the whole history for the whole table -- 303,410 rows
    across 388 series for U20404 -- which is why this fetches a table rather
    than a series. Filtering to the ids we want happens in the caller.
    """
    dataset, _, table = spec.partition(":")
    if not table:
        raise BeaError(f"table spec {spec!r} should be '<dataset>:<TableName>'")
    params = {"UserID": api_key(), "method": "GetData", "datasetname": dataset,
              "TableName": table, "Frequency": freq, "Year": year,
              "ResultFormat": "JSON"}
    pace()
    for attempt in _retry():
        with attempt:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                r = client.get(BEA_URL, params=params)
            if r.status_code != 200:
                raise BeaError(f"BEA returned {r.status_code}: {r.text[:200]}")
            body = r.json().get("BEAAPI", {})
            # BEA answers 200 with an Error block, and the message is the only
            # way to tell a bad table from a throttled key, so surface it.
            if "Error" in body:
                raise BeaError(f"BEA error: {str(body['Error'])[:300]}")
            rows = body.get("Results", {}).get("Data")
            if not rows:
                raise BeaError(f"BEA returned no data for {spec}")
    _last_fetch.append((time.time(), len(r.content) / 1e6))

    # The response IS the only record that these values were current today:
    # nothing upstream can reproduce it, exactly as for the BLS adapter. The
    # key is in the query string, never in the body.
    archive.store("bea", f"{table}_{freq}_{year}", r.text, "json")

    out: dict[str, list[tuple[date, float | None]]] = {}
    for row in rows:
        d = parse_period(row.get("TimePeriod", ""))
        if d is None:
            continue
        out.setdefault(row["SeriesCode"].strip(), []).append(
            (d, parse_value(row.get("DataValue"))))
    for code in out:
        out[code] = sorted(set(out[code]), key=lambda r: r[0])
    return out


def get_observations(series_ids: list[str], spec: str = DEFAULT_TABLE,
                     ) -> dict[str, list[tuple[date, float | None]]]:
    """Full current history for each id, from its table.

    An id the table does not contain comes back as an empty list rather than a
    silent omission, so the caller can report it.
    """
    table = get_table(spec)
    return {sid: table.get(sid, []) for sid in series_ids}


def get_labels(spec: str = DEFAULT_TABLE) -> dict[str, str]:
    """Series code to line description, for composing catalog titles."""
    dataset, _, table = spec.partition(":")
    params = {"UserID": api_key(), "method": "GetData", "datasetname": dataset,
              "TableName": table, "Frequency": "M", "Year": "2026",
              "ResultFormat": "JSON"}
    pace(3.0)
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        r = client.get(BEA_URL, params=params)
    if r.status_code != 200:
        raise BeaError(f"BEA returned {r.status_code}: {r.text[:200]}")
    body = r.json().get("BEAAPI", {})
    if "Error" in body:
        raise BeaError(f"BEA error: {str(body['Error'])[:300]}")
    return {row["SeriesCode"].strip(): row["LineDescription"].strip()
            for row in body["Results"]["Data"]}
