# bigricebowl dashboards — project context

Read this before changing anything. It is the accumulated knowledge of the
build, including several traps that were paid for the hard way.

## What this is

William's private economic dashboards, live at <https://data.bigricebowl.cloud>
behind an Authelia login. Data comes from FRED/ALFRED, lands in a Postgres
database called `macro` with **every vintage of every observation**, is exported
to static JSON bundles, and rendered by a shared client-side engine.

Built September 2026. Everything runs on the VPS (`bigricebowl.cloud`); there is
no local build step.

## Layout

| Path | Purpose |
|---|---|
| `macro/schema.sql` | Tables, views. Plain tables — see traps |
| `macro/gen_catalog.py` | Regenerates `catalog.sql` from the retired stack's seed |
| `macro/fred.py` | FRED + ALFRED client. Keyless CSV path plus keyed API paths |
| `macro/ingest.py` | Current-vintage load, diff-on-write |
| `macro/backfill.py` | Full ALFRED vintage history |
| `macro/add_series.py` | Add series, metadata read from FRED rather than typed |
| `macro/validate.py` | Asserts the data reproduces the published releases |
| `macro/bls.py` | BLS API v2 client. Second source; **no vintage history** |
| `macro/derived.py` | Derived measures, shipped as ordinary series |
| `macro/export.py` | Bundles → `data/v1/dashboards/*.json` |
| `macro/refresh.py` | The orchestrator cron runs |
| `dashboards/*.yml` | One spec per dashboard — the only per-dashboard data file |
| `site/assets/brb-dash.js` | The shared rendering engine |
| `site/us/employment/*/index.html` | Pages. Each is a panel list, nothing more |
| `tools/refresh.sh` | Cron entry point; loads `.env`, rotates the log |
| `tools/stamp_assets.py` | Content-hashes asset URLs. **Run after any asset change** |
| `.env` | `MACRO_DSN`, `FRED_API_KEY`, `BLS_API_KEY`, `NTFY_URL`. Mode 600, gitignored |
| `FINDINGS_derived_measures.md` | Which derived measures were tested and what the numbers were. **Read before adding a derived panel** |
| `tools/research/` | Read-only exploratory helpers behind those findings |

Config that lives outside this repo: `~/bigricebowl/dashboards/` (Authelia config,
nginx.conf, `dashboards.env`) and `~/bigricebowl/docker-compose.dashboards.yml`.

## Decisions already settled — do not re-litigate

- **Database `macro`**, own `macro_app` role. The essays DSN is scoped to its own
  database and cannot read this one. That is deliberate.
- **`macro_observations` is keyed `(series_id, observation_dt, vintage_dt)`.**
  Every revision is its own row. This is the point of the whole system.
- **Plain tables, not hypertables.** See traps.
- **The page never queries Postgres.** Bundles are static files.
- **One release per dashboard.** Nonfarm Payroll, JOLTS and Weekly Claims each
  have exactly one release, so the stamp under the title is unambiguous.
- **A dashboard is a spec plus a panel list.** If a new dashboard needs a change
  in `brb-dash.js`, that is an engine defect, not a special case. Adding a
  *generic* panel type or transform is fine; a per-dashboard branch is not.
- **Style: Statistical Abstract.** Cool paper `#f7f7f4`, ink `#14161a`, slate
  `#35566b` gains, oxblood `#8c2f27` losses, `#8a7b4f` second series. Source
  Serif 4 for figures, Archivo for labels, JetBrains Mono for axes.
  **The cursor is ink and never encodes a value** — it marks the current period,
  so it can never be mistaken for data.

## Traps already hit — do not rediscover these

1. **`ON CONFLICT (cols) DO NOTHING` silently never fires on a TimescaleDB
   hypertable.** Chunk-constraint inference defeats it. The retired stack ended
   with 650,093 duplicate rows in 1,784,464, and 4,191 of those duplicate groups
   held *divergent values*, so a naive dedupe would have destroyed real data.
   This is why `macro_observations` is a plain table and the guard is a **bare**
   `ON CONFLICT DO NOTHING`. At ~230k rows the chunking bought nothing anyway.

2. **The "as first reported" change cannot be derived from first-print levels.**
   Differencing two first prints subtracts values from two *different* vintages.
   It gives −126k for July 2026 where the release says −23k. The real figure
   reads both periods at the vintage of the later one's first print, which is
   what `first_reported_diff` in the exporter does. This mistake was made twice
   — once in SQL, then again in JavaScript after being caught. Verified: June
   2026 first reported +57k, revised to +20k, and the release states −37k.

3. **A release quotes revisions against the PREVIOUSLY PUBLISHED figure, not the
   first print.** May 2026 ran 172 → 129 → 63 across three releases; the PDF's
   "revised down by 66,000, from +129,000" is the last step only.

4. **The October 2025 gap is household-survey only.** `UNRATE`, `CIVPART`,
   `EMRATIO` are genuinely null; `PAYEMS` carries 158,408. A blanket "October
   2025 is missing" rule punches a false hole in the payroll line.

5. **Never serve an unversioned asset as `immutable`.** `brb-dash.js` was matched
   by the fingerprinted-asset rule and cached for a year. Chrome will not
   revalidate an immutable entry even on a normal reload, so a browser that had
   loaded an older build silently rendered nothing for panel types added later —
   with the correct file on the server the whole time. Brave, never having seen
   the old build, worked; that difference was the tell. **Cache-busting must be
   in the URL**: run `tools/stamp_assets.py` after any asset change.

6. **Align series by date, never by index.** Zipping positionally is correct only
   when series share a frequency *and* end on the same date. `alignAsOf()` uses
   "most recent value at or before this date": exact for equal frequencies,
   forward-filling for coarser ones (monthly payrolls on a weekly claims axis),
   and a published null still survives as a gap because the lookup lands on the
   observation itself.

7. **Units differ by source.** JOLTS levels arrive in *thousands* (7271 =
   7.27m); weekly claims arrive in *persons* (203000 = 203k). Continuing claims
   rendered as "1778.00m" before the formats distinguished them.

8. **Panels need a trailing window.** Without one, payrolls plot from 1939 and
   the war years put the axis at ±5,000k, flattening everything recent to a
   line. The window is applied *after* transforms so a 3-month average at the
   left edge still uses real prior data.

9. **A near-flat or quantised series lies when auto-scaled.** Average weekly
   hours moves only 34.2–34.3; sparklines floor their range at 2% of the level,
   and the chart carries a 3-month average through the square wave.

10. **Only signed quantities take a colour.** A level — participation, hourly
    earnings — stays ink. Colouring a level by direction reads as a judgement
    the number does not support.

11. **`effectScatter` draws nothing** under the SVG renderer with animation
    disabled. Use plain `scatter`.

12. **Cron is scheduled in `America/New_York`, not UTC.** The embargoes are
    08:30 and 10:00 ET; a UTC schedule drifts an hour at each DST change and
    misses the release entirely on the far side of one.

13. **DOM probes are not looking.** "5 charts, no errors" was reported while the
    Beveridge curve rendered nothing — the chart object existed and had drawn
    its axes; only the series was missing. Screenshot or open the page.

14. **The January labour force figure is a level break, not a flow.** BLS applies
    new population controls each January and does **not** revise prior months, so
    January 2026 shows the civilian labour force falling 1,030k when the flow was
    nothing of the kind. A twelve-month change spanning January mixes the break
    into the flow and reads -110k/month where the post-control window shows
    -228k/month. Anything computed from `CLF16OV` or `CNP16OV` — breakeven payroll
    growth above all — must either exclude January or use the
    population-control-smoothed research series at
    <https://www.bls.gov/cps/smoothed_emp.xlsx>.

15. **A series on the BLS API has no vintage history.** ALFRED is the only free
    source of vintages. BLS-only series (diffusion indexes, `LNS16000000`, real
    earnings, SA marginal attachment) can only accumulate vintages from the day
    ingestion starts, so `vintage_mode` must record that and the page must never
    offer a revision overlay on them. `ingest.py` selects `WHERE source='fred'`;
    that has to become a dispatch before any non-FRED series is added.

16. **`delta0` and `index100` baseline on the first value of the WHOLE series,
    and transforms run BEFORE the trailing window.** This has now produced two
    live charts whose captions did not match them: Table 3 said "change over 5
    years" while plotting change since 1948, and the two-survey panel said
    "5 years ago = 100" while indexing to 1939 and plotting 531. Two series far
    from 100 look enough like an index that nobody queries it; a third gave it
    away. On any panel with a window use the series option **`rebase`** — `true`
    subtracts the window's first value, `"index"` divides by it — which runs
    after the window, where the caption's "5 years ago" actually exists.

## How it runs

```
FRED/ALFRED --> macro (Postgres) --> data/v1/*.json --> static page
```

`refresh.py` polls the keyless CSV endpoint first (free; diff-on-write writes
nothing when unchanged). Only a real change pays for the ALFRED re-fetch,
validation and re-export.

**Validation runs BEFORE export and a failure skips it deliberately** — the
previous bundles keep serving rather than publishing figures that disagree with
the source. That failure is invisible on the page, so it also writes
`status.json` (the index reads it) and pushes an ntfy alert.

Cron windows: 08:25–09:45 ET for Employment Situation and Claims, 09:55–10:45 ET
for JOLTS, plus a 01:40 ET full sweep.

## Commands

```bash
# on the VPS
cd ~/dashboards/macro && set -a && . ../.env && set +a
../venv/bin/python validate.py            # 24 assertions against the releases
../venv/bin/python refresh.py --force     # re-export without waiting for data
../venv/bin/python add_series.py --release bls.employment_situation \
    --category employment --importance 6 SERIESID
tail -f ~/dashboards/logs/refresh.log

# after changing site/assets/*
cd ~/dashboards && python3 tools/stamp_assets.py
```

Compose (never edit `docker-compose.core.yml`):

```bash
cd ~/bigricebowl
docker compose -f docker-compose.core.yml -f docker-compose.essays.yml \
               -f docker-compose.dashboards.yml ps
```

## Guardrails

Do not touch, restart, recreate or rebuild: `caddy`, `everos`, `everos_mcp`,
`litellm`, `linkding`, `postgres`. Do not edit `docker-compose.core.yml` or any
*existing* Caddy site block — appending a new one is fine, and the Caddyfile is a
single-file bind mount, so **append in place** (`>>`) to preserve the inode, then
validate *inside* the container and `caddy reload`, never restart.

## State as of 3 September 2026

- 53 series, 6 releases, ~231,000 vintage rows, 24/24 validations passing.
- Three dashboards live; CPI is the next to build and the real test of whether
  the engine generalises beyond employment.
- Alerting is ntfy.sh (public relay). **William prefers to self-host** — swap
  `NTFY_URL` for an own instance behind Caddy when convenient.
- Cron cannot catch up a missed run. The retired stack used **systemd timers**
  (`Persistent=true`, `RandomizedDelaySec`) for exactly this reason; move to
  timers with catalog-driven scheduling (`pub_lag_days`, `staleness_mode` are
  already in `macro_series_meta`) when the second country arrives.
- The retired `investment` stack's code survives at `~/bigricebowl/workers/` and
  `~/bigricebowl/postgres/migrations/` — 25,078 series across many countries.
  Its data is gone; `FINDINGS_revision_handling.md` and `MACRO_FINDINGS.md` are
  worth reading before extending the pipeline.
