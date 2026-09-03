"""Tier 2: the raw archive. Every source response, exactly as it arrived.

The architecture claims the database is rebuildable and therefore disposable.
Until now that was false. FRED and ALFRED will re-serve anything, but the BLS
API has **no point-in-time history at all**: 2,735 vintage rows across seven
series existed only as rows in Postgres, and nothing upstream could return them.
Losing the database meant losing them permanently.

So: write the bytes down before they are parsed, and keep them.

**Content-addressed and deduplicated.** The daily sweep re-fetches every series
whether or not it changed, so storing each response would write the same
megabyte hundreds of times a year. A blob is named by the SHA-256 of its
payload and written once; the append-only manifest records every fetch, whether
or not the content was new. The blobs are what the data was, the manifest is
when we saw it.

**Immutable.** A blob is never rewritten. Its name is a hash of its data, so a
second write could only ever carry the same data; where a source stamps its
replies with something volatile (BLS sends `responseTime`), the blob is
addressed by the canonical form and the manifest keeps the exact byte hash of
every fetch.

**A write failure raises.** Silently losing the archive returns the system to a
state where the database is the only copy, without anyone knowing. This box has
455 GB free; a failure here is real and should stop the run.

Layout:

    archive/manifest.ndjson                  one line per fetch, append-only
    archive/<source>/<name>/<sha16>.<ext>.gz the payload, gzipped

Usage:
    python archive.py --stat
    python archive.py --verify ICSA PAYEMS
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("MACRO_ARCHIVE",
                           Path(__file__).resolve().parent.parent / "archive"))
MANIFEST = ROOT / "manifest.ndjson"

# Anything in a path segment that is not one of these becomes '_'. Series ids
# are alphanumeric, but a label is assembled from them and must not be able to
# escape the archive root.
SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._+-")


def _safe(name: str) -> str:
    cleaned = "".join(c if c in SAFE else "_" for c in name).strip("._")
    return cleaned[:120] or "unnamed"


def store(source: str, name: str, payload: str | bytes, ext: str = "json",
          dedupe_on: str | bytes | None = None) -> dict:
    """Write one source response. Returns what happened; raises if it cannot.

    `dedupe_on` is a canonical form of the payload used to ADDRESS the blob,
    for sources that vary between identical responses. BLS stamps every reply
    with `responseTime` in milliseconds, so raw-byte addressing deduplicated
    nothing at all. The payload written is always the one passed in; only the
    name is taken from the canonical form.
    """
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    sha = hashlib.sha256(raw).hexdigest()
    if dedupe_on is None:
        key = sha
    else:
        canon = dedupe_on.encode("utf-8") if isinstance(dedupe_on, str) else dedupe_on
        key = hashlib.sha256(canon).hexdigest()
    rel = Path(_safe(source)) / _safe(name) / f"{key[:16]}.{_safe(ext)}.gz"
    dest = ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    new = not dest.exists()
    if new:
        # Write beside, then rename: a reader must never see a partial blob, and
        # an interrupted run must not leave a truncated file wearing the name of
        # a hash it does not match.
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        with gzip.open(tmp, "wb", compresslevel=6) as fh:
            fh.write(raw)
        tmp.replace(dest)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "source": source, "name": name, "sha256": sha, "key": key,
            "bytes": len(raw), "path": str(rel).replace("\\", "/"), "new": new,
        }, separators=(",", ":")) + "\n")
    return {"sha256": sha, "path": dest, "new": new, "bytes": len(raw)}


def read(path: str | Path) -> bytes:
    """Read one blob back, by manifest path or absolute path."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with gzip.open(p, "rb") as fh:
        return fh.read()


def entries() -> list[dict]:
    if not MANIFEST.exists():
        return []
    out = []
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ── reporting and verification ───────────────────────────────────────────────

def _stat() -> int:
    rows = entries()
    if not rows:
        print("archive is empty")
        return 0
    blobs = {r.get("key", r["sha256"]) for r in rows}
    on_disk = sum(f.stat().st_size for f in ROOT.rglob("*.gz"))
    by_source: dict[str, list] = {}
    for r in rows:
        by_source.setdefault(r["source"], []).append(r)
    print(f"{len(rows)} fetches recorded, {len(blobs)} distinct payloads, "
          f"{on_disk / 1e6:.1f} MB on disk")
    print(f"  {rows[0]['t']} .. {rows[-1]['t']}\n")
    print(f"  {'source':<12} {'fetches':>8} {'distinct':>9} {'names':>7}")
    for src, rs in sorted(by_source.items()):
        print(f"  {src:<12} {len(rs):>8} {len({r.get('key', r['sha256']) for r in rs}):>9} "
              f"{len({r['name'] for r in rs}):>7}")
    dedupe = 100 * (1 - len(blobs) / len(rows))
    print(f"\n  deduplication saved {dedupe:.1f}% of writes")
    return 0


def _verify(series: list[str]) -> int:
    """Re-parse the newest archived CSV for a series and compare with the database.

    The archive is only worth having if what it holds can be turned back into
    the data. This does that for the FRED CSV path, which is how nearly every
    observation in the store arrived.
    """
    import csv as _csv
    import io as _io

    import psycopg

    rows = entries()
    fails = 0
    with psycopg.connect(os.environ["MACRO_DSN"]) as conn, conn.cursor() as cur:
        for sid in series:
            mine = [r for r in rows if r["source"] == "fred_csv" and r["name"] == sid]
            if mine:
                latest = mine[-1]
                when = latest["t"]
                text = read(latest["path"]).decode("utf-8")
                parsed = {}
                rdr = _csv.reader(_io.StringIO(text))
                next(rdr, None)
                for row in rdr:
                    if len(row) >= 2 and row[0].strip():
                        v = row[1].strip()
                        parsed[row[0].strip()] = None if v in (".", "") else float(v)
            else:
                # BLS answers in batches spanning several series and twenty-year
                # windows, so one series is reassembled across blobs. These are
                # the series with no point-in-time source to fall back on, which
                # is exactly why they are worth proving.
                parsed, when, seen = {}, None, 0
                for r in [r for r in rows if r["source"] == "bls"]:
                    try:
                        doc = json.loads(read(r["path"]))
                    except FileNotFoundError:
                        continue
                    for ser in (doc.get("Results") or {}).get("series", []):
                        if ser.get("seriesID") != sid:
                            continue
                        seen += 1
                        when = r["t"]
                        for row in ser.get("data", []):
                            per = row.get("period", "")
                            if not per.startswith("M") or per == "M13":
                                continue
                            key = f"{row['year']}-{per[1:]}-01"
                            val = str(row.get("value", "")).replace(",", "").strip()
                            parsed[key] = None if val in ("", "-", ".") else float(val)
                if not seen:
                    print(f"  MISS  {sid}: nothing archived yet")
                    fails += 1
                    continue

            cur.execute("SELECT observation_dt, value FROM macro_observations_current "
                        "WHERE series_id=%s", (sid,))
            db = {d.isoformat(): (None if v is None else float(v)) for d, v in cur.fetchall()}

            common = set(parsed) & set(db)
            diff = [k for k in common if parsed[k] != db[k]]
            only_archive = set(parsed) - set(db)
            ok = not diff and not only_archive
            fails += 0 if ok else 1
            print(f"  {'OK  ' if ok else 'FAIL'}  {sid:<16} archive {len(parsed):>5} obs, "
                  f"database {len(db):>5}, {len(common):>5} shared, {len(diff)} differ, "
                  f"{len(only_archive)} only in the archive   [{when}]")
            for k in sorted(diff)[:3]:
                print(f"          {k}: archive {parsed[k]}, database {db[k]}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stat", action="store_true")
    ap.add_argument("--verify", nargs="*", metavar="SERIES")
    args = ap.parse_args()
    if args.verify is not None:
        return _verify(args.verify or ["PAYEMS", "UNRATE", "ICSA"])
    return _stat()


if __name__ == "__main__":
    raise SystemExit(main())
