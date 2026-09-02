"""FRED + ALFRED client.

Ported from the retired `investment` stack's macro_ingest/sources/fred.py, with
two changes:

  1. The API key is read lazily, not at import. The original did
     `API_KEY = os.environ["FRED_API_KEY"]` at module scope, so the module could
     not even be imported without a key — which would block the catalog and
     current-vintage work that needs no key at all.
  2. Added get_observations_csv(), which uses FRED's public graph endpoint and
     needs no key. Enough to load full current-vintage history for every series.

Three pull modes:
  get_observations_csv  keyless, current vintage       — no API key
  get_observations      current vintage via the API    — needs FRED_API_KEY
  get_vintages          full ALFRED revision history   — needs FRED_API_KEY
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import date, datetime, timezone

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# httpx logs full request URLs at INFO, including the api_key query parameter.
# Silence it; retries are still visible through tenacity.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=15.0)

# FRED caps /series/observations at 100000 rows per call. Dense vintage
# histories silently truncate at the limit, so paginate and stitch.
PAGE_LIMIT = 100000


class FredError(Exception):
    pass


def api_key() -> str:
    """Read the key at call time so key-free paths stay importable."""
    try:
        return os.environ["FRED_API_KEY"]
    except KeyError:
        raise FredError(
            "FRED_API_KEY is not set. Needed only for the ALFRED vintage "
            "backfill; get_observations_csv() works without it."
        ) from None


def _retry():
    return Retrying(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, FredError)),
        reraise=True,
    )


def _get(client: httpx.Client, path: str, params: dict) -> dict:
    params = {**params, "api_key": api_key(), "file_type": "json"}
    for attempt in _retry():
        with attempt:
            r = client.get(f"{FRED_BASE}{path}", params=params)
            if r.status_code != 200:
                raise FredError(f"FRED {path} returned {r.status_code}: {r.text[:200]}")
            return r.json()


# ── keyless path ─────────────────────────────────────────────────────────────

def get_observations_csv(series_id: str) -> list[tuple[date, float | None]]:
    """Full current-vintage history. No API key. '.' means published-as-missing."""
    for attempt in _retry():
        with attempt:
            with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                r = client.get(FRED_CSV, params={"id": series_id})
                if r.status_code != 200:
                    raise FredError(
                        f"FRED csv {series_id} returned {r.status_code}: {r.text[:160]}"
                    )
                text = r.text

    rows: list[tuple[date, float | None]] = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or len(header) < 2:
        raise FredError(f"FRED csv {series_id}: unexpected header {header!r}")
    for row in reader:
        if len(row) < 2 or not row[0].strip():
            continue
        rows.append((date.fromisoformat(row[0].strip()), parse_value(row[1])))
    if not rows:
        raise FredError(f"FRED csv {series_id}: no observations returned")
    return rows


# ── keyed paths ──────────────────────────────────────────────────────────────

def get_observations(series_id: str, start: date | None = None) -> list[dict]:
    """Current-vintage observations via the API. Cheap; for routine updates."""
    params: dict = {"series_id": series_id}
    if start:
        params["observation_start"] = str(start)
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        return _get(client, "/series/observations", params).get("observations", [])


def get_vintages(series_id: str, start: date | None = None) -> list[dict]:
    """
    Full ALFRED vintage history.

    Each row carries realtime_start / realtime_end — the period that value was
    current. Our key is (series_id, date, realtime_start), stored as
    (series_id, observation_dt, vintage_dt).

    FRED's sentinel range 1776-07-04 .. 9999-12-31 returns every known vintage
    of every observation.
    """
    base: dict = {
        "series_id": series_id,
        "realtime_start": "1776-07-04",
        "realtime_end": "9999-12-31",
        "limit": PAGE_LIMIT,
    }
    if start:
        base["observation_start"] = str(start)

    out: list[dict] = []
    offset = page = 0
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        while True:
            data = _get(client, "/series/observations", {**base, "offset": offset})
            batch = data.get("observations", [])
            out.extend(batch)
            page += 1
            if len(batch) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
            if page >= 20:
                logger.warning(
                    "FRED %s: stopping pagination at page %d (%d rows); "
                    "series likely needs date-range splitting.",
                    series_id, page, len(out),
                )
                break
    return out


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_value(v: str | None) -> float | None:
    if v is None or v.strip() in (".", ""):
        return None
    try:
        return float(v)
    except ValueError:
        logger.warning("Unparseable FRED value: %r", v)
        return None


def parse_vintage(realtime_start: str) -> datetime:
    return datetime.fromisoformat(realtime_start).replace(tzinfo=timezone.utc)
