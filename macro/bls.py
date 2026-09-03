"""BLS API v2 client — the second source, and the first without vintages.

FRED is preferred wherever both carry a series, because ALFRED is the only free
source of revision history. BLS is used only for what FRED does not have:

  CES0500000021/22/23   private diffusion indexes, 1/3/6-month spans (SA)
  CEU0500000024         private diffusion, 12-month span — NSA only
  LNS16000000           CPS employment adjusted to CES concepts
  CES0500000012/13      real earnings, 1982-84 dollars
  LNS15026642           marginally attached, seasonally adjusted

**These series carry no vintage history.** ALFRED supplies point-in-time values
and this API does not, so a BLS-sourced series accumulates vintages only from
the day ingestion starts. Their catalog rows are marked `vintage_mode =
'fetch_date'`, the exporter passes that through, and no panel may offer a
revision overlay on them. CLAUDE.md trap 15.

Request limits: 50 series and 20 years per call, 500 calls a day with a key.
Both are handled here by chunking.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
HTTP_TIMEOUT = httpx.Timeout(90.0, connect=15.0)

MAX_SERIES = 50      # per request
MAX_SPAN = 20        # years per request
EARLIEST = 1939      # nothing in this catalog predates the CES series


class BlsError(Exception):
    pass


def api_key() -> str:
    """Read at call time, so importing this module never requires a key."""
    try:
        return os.environ["BLS_API_KEY"]
    except KeyError:
        raise BlsError("BLS_API_KEY is not set.") from None


def _retry():
    return Retrying(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, BlsError)),
        reraise=True,
    )


def _post(payload: dict) -> dict:
    body = json.dumps({**payload, "registrationkey": api_key()})
    for attempt in _retry():
        with attempt:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                r = client.post(BLS_URL, content=body,
                                headers={"Content-Type": "application/json"})
            if r.status_code != 200:
                raise BlsError(f"BLS returned {r.status_code}: {r.text[:200]}")
            data = r.json()
    status = data.get("status")
    if status != "REQUEST_SUCCEEDED":
        # The daily cap and a malformed series id both land here; the message
        # is the only way to tell them apart, so surface it rather than a code.
        raise BlsError(f"BLS status {status}: {'; '.join(data.get('message', []))[:300]}")
    return data


def parse_period(year: str, period: str) -> date | None:
    """BLS period code to an observation date.

    M13 is the annual average and Q05 the annual quarter — both are summaries
    sitting in the same array as the periods themselves. Loading them would put
    a thirteenth month into a monthly series and quietly corrupt every
    month-on-month change computed from it.
    """
    y = int(year)
    if period.startswith("M"):
        m = int(period[1:])
        return None if m == 13 else date(y, m, 1)
    if period.startswith("Q"):
        q = int(period[1:])
        return None if q == 5 else date(y, 3 * (q - 1) + 1, 1)
    if period.startswith("A"):
        return date(y, 1, 1)
    logger.warning("unrecognised BLS period %r", period)
    return None


def parse_value(v: str | None) -> float | None:
    if v is None or str(v).strip() in ("", "-", "."):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        logger.warning("unparseable BLS value: %r", v)
        return None


def get_observations(series_ids: list[str], start_year: int = EARLIEST,
                     end_year: int | None = None) -> dict[str, list[tuple[date, float | None]]]:
    """Full current history for each series, ascending by date.

    Chunked over both limits. A series the API knows nothing about comes back
    with an empty data array rather than an error, so an empty result is
    reported to the caller rather than silently returning nothing.
    """
    end_year = end_year or date.today().year
    out: dict[str, list[tuple[date, float | None]]] = {s: [] for s in series_ids}

    for i in range(0, len(series_ids), MAX_SERIES):
        chunk = series_ids[i:i + MAX_SERIES]
        y0 = start_year
        while y0 <= end_year:
            y1 = min(y0 + MAX_SPAN - 1, end_year)
            data = _post({"seriesid": chunk, "startyear": str(y0), "endyear": str(y1)})
            for s in data["Results"]["series"]:
                sid = s["seriesID"]
                for row in s.get("data", []):
                    d = parse_period(row["year"], row["period"])
                    if d is not None:
                        out[sid].append((d, parse_value(row.get("value"))))
            y0 = y1 + 1

    for sid in series_ids:
        # Later spans overlap nothing, but the API returns newest-first within a
        # span, so sort rather than trust the order.
        out[sid] = sorted(set(out[sid]), key=lambda r: r[0])
    return out


def get_catalog(series_ids: list[str]) -> dict[str, dict]:
    """Series metadata, where BLS will give it.

    Catalog data is not available for every series — the API says so per series
    in `message` and simply omits the block. The caller must cope rather than
    assume.
    """
    out: dict[str, dict] = {}
    for i in range(0, len(series_ids), MAX_SERIES):
        chunk = series_ids[i:i + MAX_SERIES]
        y = date.today().year
        data = _post({"seriesid": chunk, "startyear": str(y), "endyear": str(y),
                      "catalog": True})
        for s in data["Results"]["series"]:
            cat = s.get("catalog")
            if cat:
                out[s["seriesID"]] = cat
    return out
