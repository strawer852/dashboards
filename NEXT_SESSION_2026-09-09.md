# Next session — the second half of the audit, on the VPS

Written 9 September 2026 by a session that could not reach the VPS. Read in
this order: `CLAUDE.md` (60 traps), `HANDOFF.md`, `AUDIT.md`,
`AUDIT_FINDINGS_2026-09-09.md`. Then this file. **Ingest nothing.**

## 0. Where you are

```bash
ssh strawer@bigricebowl.cloud
cd ~/dashboards
git status                       # anything uncommitted on the VPS since the 6th?
git log --oneline origin/master..HEAD   # anything the nightly push has not sent?
git fetch origin
git log --oneline master..origin/claude/data-bigricebowl-audit-a7bbms
```

The branch has one commit (39ab758) on top of c4082ef. Merge it:

```bash
git checkout master
git merge origin/claude/data-bigricebowl-audit-a7bbms
```

If `HANDOFF.md` conflicts, take the branch's side: the VPS copy is the 15 MB
corrupted one (trap 56). Then `wc -c HANDOFF.md` must be about 12 KB.

## 1. Prove the merge before anything else

```bash
set -a && . .env && set +a
cp -r data/v1/dashboards /tmp/bundles-before        # to compare derived values
./venv/bin/python -m macro.validate                  # 37/37, as before
./venv/bin/python macro/refresh.py --force           # derived.py changed: re-export
./venv/bin/python tools/coverage.py                  # 100% on all seven
python3 tools/keycheck.py                            # new; 0 findings
python3 tools/build_nav.py --check                   # nothing to change
~/.venvs/shot/bin/python tools/clipcheck.py          # real render, real bundles
~/.venvs/shot/bin/python tools/shoot.py --path us/inflation/ppi
```

Then compare the derived series before and after the re-export:

```bash
./venv/bin/python - <<'PY'
import json
for b in ["us-inflation-cpi","us-inflation-pce","us-employment-weekly-claims","us-inflation-ppi"]:
    old=json.load(open(f"/tmp/bundles-before/{b}.json"))["series"]
    new=json.load(open(f"data/v1/dashboards/{b}.json"))["series"]
    for sid,e in new.items():
        if not e.get("derived"): continue
        o=old.get(sid,{}).get("values")
        n=sum(1 for a,c in zip(o or [],e["values"]) if a!=c)
        print(f"{b:32} {sid:22} changed={n:4} of {len(e['values'])}")
PY
```

Expected: **zero changes** for every derived series. The by-date fix (trap
60) gives the same answer as the old positional code whenever every input
ends on the same period, which truncation guaranteed. If any CPI/PCE median,
breadth or state-breadth value changed, an input was misaligned before, and
the new value is the correct one -- record which series and how many months
in `AUDIT_FINDINGS_2026-09-09.md`.

Then look, with `shoot.py` and a browser: PPI Tables 21–22 read top-down
from consumer foods to construction; payroll Table 6 mining at the top,
government at the bottom; claims Table 9 Alaska at the top; PCE Table 3 and
every Labour Costs key draw the ink swatch in ink; `/us/` renders with the
rail open on United States; the map's United States links to `/us/`.

## 2. Thursday 10 and Friday 11 September

PPI and claims land Thursday, CPI Friday, both 08:30 ET. First live release
through nearly everything that changed on 5–6 September (trap 35, trap 39,
`truncate_history`, six derived measures) plus the 9 September merge.

Watch `logs/refresh.log`. Good looks like: `refresh start
(bls.ppi,eta.claims)` after 08:35 ET, `BLS: ... series from <recent year>`
rather than 1939, `validate rc=0`, `export`, an ntfy push, and later windows
saying nothing outstanding rather than refetching. Friday the same for
`bls.cpi`. Then look at the pages, not the log: the stamp dates, the newest
column of every heatmap, Table 1 on CPI, the PPI weights in Table 6.

Nothing in prose needs retyping at these releases any more (trap 59). If a
caption reads wrong against the new print, that is a defect to fix in the
caption's mechanism, not a number to update.

## 3. Area A — reconcile against the news releases

Not done for CPI, PPI, PCE or Labour Costs. The method that worked for the
174 payroll ids: for every id, reproduce the published figure from
`macro_observations` **as of the vintage that published it**, never by
title. Write the method down so it can be re-run at every release.

- CPI: news release Table 1 and Table 2, 338 categories, unadjusted
  12-month change and the relative importance column (Jun. 2026).
- PPI: Table 1 relative importances (goods 29.028 + services 68.338 +
  construction 2.634 = 100.000 identifies the published ones); Table 2 and
  the FD-ID stages.
- PCE: BEA Table 2.4.5U against the 210 underlying-detail lines and their
  weights in the spec (sum 99.658).
- Labour Costs: Productivity and Costs (ULC, hourly compensation,
  productivity to a tenth of a point: ULC = compensation − productivity),
  and the ECI news release.

A failure is a figure that differs, an id mapped to the wrong row, or a
published category absent from the database. The current value is the
latest vintage per `(series_id, observation_dt)`; a naive SELECT is wrong.

## 4. Area B — vintages

```sql
-- every fetch_date series should be one whose source serves no vintages
SELECT source, vintage_mode, count(*) FROM macro_series_meta GROUP BY 1,2 ORDER BY 1,2;
-- from_row series on a single vintage: must be 0 (trap 35 regression check)
SELECT count(*) FROM (
  SELECT m.series_id FROM macro_series_meta m JOIN macro_observations o USING (series_id)
  WHERE m.vintage_mode='from_row' GROUP BY 1 HAVING count(DISTINCT vintage_dt)=1) t;
-- a revision spot check: July 2026 payrolls, first print vs latest
SELECT vintage_dt, value FROM macro_observations
WHERE series_id='PAYEMS' AND observation_dt='2026-07-01' ORDER BY vintage_dt;
```

Any FRED series marked `fetch_date` must be one ALFRED genuinely has
nothing for; check a sample against ALFRED directly.

## 5. Decisions left open (recorded, not changed)

- Labour Costs draws 24–25 years with no window in its headers; Table 4
  leads with the quarterly ECI on purpose (trap 17's cost, accepted).
- JOLTS Table 5 could draw `JTSTSR` beside hires if it is in the bundle.
- Claims Table 9 lists states in postal-code order.
- PCE Table 14's BEA-side shares and CPI Table 32's "8.1% in April 2023"
  were not verifiable without the data.
- `export.page_requirements` undercounts by one for default-`diff` panels
  and cannot see ids in a bare array; harmless today.
- Area H: 2,308 series held and not drawn is deliberate; no promotion
  proposed without the data.

## 6. Do not

Ingest. Hand-edit a generated block: the rail, the landing index, the map,
the scope line, `catalog.sql`, or `site/us/index.html` (generated whole).
Touch `caddy`, `everos`, `everos_mcp`, `litellm`, `linkding`, `postgres`,
`docker-compose.core.yml`, or an existing Caddy site block. Commit a doc
without reading `git diff --stat` (trap 56).
