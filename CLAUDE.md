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
| `macro/archive.py` | Tier 2: every source response, gzipped and deduplicated |
| `macro/bls.py` | BLS API v2 client. Second source; **no vintage history** |
| `macro/derived.py` | Derived measures, shipped as ordinary series |
| `macro/export.py` | Bundles → `data/v1/dashboards/*.json` |
| `macro/refresh.py` | The orchestrator cron runs |
| `macro/release_dates.py` | Forward release calendar, FRED -> `macro_release_dates` |
| `dashboards/*.yml` | One spec per dashboard — the only per-dashboard data file |
| `site/assets/brb-dash.js` | The shared rendering engine |
| `site/us/employment/*/index.html` | Pages. Each is a panel list, nothing more |
| `tools/refresh.sh` | Timer entry point; loads `.env`, rotates the log |
| `tools/stamp_assets.py` | Content-hashes asset URLs. **Run after any asset change** |
| `systemd/` | The refresh timers. Wall-clock ET, `Persistent=true` |
| `tools/install-timers.sh` | Installs and enables them as user units. Idempotent |
| `tools/coverage.py` | Bundle series no page draws. The exporter checks the other end only |
| `tools/build_nav.py` | Generates the rail from the specs into every page. **Run after adding a dashboard** |
| `planned.yml` | Dashboards in the rail but not yet built. At the root, NOT in `dashboards/` |
| `.env` | `MACRO_DSN`, `FRED_API_KEY`, `BLS_API_KEY`, `NTFY_URL`. Mode 600, gitignored |
| `archive/` | The raw archive. Gitignored, and **the only copy of the BLS vintages** |
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
- **Style: Statistical Abstract.** Cool paper `#f7f7f4`, ink `#14161a`. Source
  Serif 4 for figures, Archivo for labels, JetBrains Mono for axes.
  **The cursor is ink and never encodes a value** — it marks the current period,
  so it can never be mistaken for data.
- **Colour does two different jobs and they use different scales.** *Sign* — a
  bar coloured by whether it is a gain or a loss — is the diverging pair
  `--pos #1f6091` and `--neg #8c2f27`. *Identity* — which series a line is — is
  the six categorical slots `--s1..--s6`, taken in order and **never cycled**;
  past six, fold the tail into an "other" bucket or use small multiples. The two
  were conflated until 4 September 2026, when the line panel's default ladder ran
  slate → gold → **oxblood**, i.e. the loss colour identifying "series 3".
  Every slot is validated against this site's own paper rather than a generic
  white: worst adjacent colourblind ΔE 11.5, normal-vision 18.2, all ≥3:1
  contrast. Re-run the check before changing any of them — ordering is the
  colourblind-safety mechanism, not decoration.
- **A stack is only honest for a partition.** `PANELS.stacked` draws the
  aggregate as a line over the bars so any residual shows as daylight instead of
  being absorbed. Food, energy, medical care and both unemployment cuts qualify;
  shelter is 95.1% of itself and the caption says so; a list of overlapping items
  does not qualify at all. Twelve stacked categories is not a chart — the
  categorical palette stops at six for the reason in trap 21.

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

12. **`CRON_TZ` does nothing on this box, and the schedule silently ran five
    hours early for it.** The embargoes are 08:30 and 10:00 ET, so the crontab
    carried `CRON_TZ=America/New_York`. Ubuntu's cron 3.0pl1 does not implement
    it — the string is not in the binary, and `crontab(5)` states the daemon
    runs with one configured timezone, does not support per-user timezones, and
    that a `TZ` in the file "will affect only the commands executed in the
    crontab, not the execution of the crontab tasks themselves". Every job
    therefore ran in `Europe/London`: the 08:25–09:45 windows fired at
    **03:25–04:45 ET**, five hours *before* the release, in summer and winter
    alike. Nothing errored, nothing alerted, and no scheduled run had ever
    happened after a release — the data only ever arrived via the next daily
    sweep, half a day late. **Scheduling is now systemd user timers**
    (`~/dashboards/systemd/`, installed by `tools/install-timers.sh`), which take
    the timezone in `OnCalendar` and were verified with
    `systemd-analyze calendar`. Verify a schedule against the wall clock it is
    meant to track; do not assume a timezone directive is implemented.

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
    away, and a third turned up on the weekly claims page, captioned the same
    way and indexing to 1967. On any panel with a window use the series option
    **`rebase`** — `true` subtracts the window's first value, `"index"` divides
    by it — which runs after the window, where the caption's "5 years ago"
    actually exists. `tools/coverage.py` will not catch this one; only looking
    at the chart will.

17. **A mixed-frequency panel must lead with its finest series.** The line panel
    builds its axis, and applies `window`, from the FIRST series listed. Led by
    a quarterly ECI, `window: 60` meant sixty *quarters* — fifteen years against
    five everywhere else — and `alignAsOf` sampled the monthly Atlanta Fed
    tracker down to quarter ends, discarding two readings in three. Monthly
    first; coarser series then forward-fill onto it as the steps they are.

18. **An acceptance test that reads the CURRENT vintage asserts figures the next
    release is supposed to change.** `validate.py` pinned July 2026's payroll
    change at −23,000 and average hourly earnings at $37.62, read from
    `macro_observations_current`. The establishment survey revises the two prior
    months, so the 4 September release would have failed those checks — and a
    validation failure deliberately skips the export, so the dashboards would
    have frozen and ntfy fired over data that was perfectly correct. May's
    hourly earnings already read 37.53 → 37.51 → 37.49 across three vintages.
    **Every published figure is now asserted AS OF the vintage that published
    it** (`val_asof`, `vintage_dt::date <= asof`), which is permanently true and
    needs no maintenance at a release. Note the cast: ALFRED vintages are stored
    at midnight but a fetch-date vintage carries a time of day, so a bare
    `<= '2026-09-03'` excludes the very day it landed.

    That leaves nothing checking data published this morning, so three
    invariants do instead: order-of-magnitude sanity on the newest value (tuned
    to catch a units change, not an economic shock — see trap 7), no series
    losing observations against the bundle already on disk, and freshness
    measured from the last *vintage* rather than the last observation date.

19. **The stamp reported a re-fetch as a release.** `released_at` came from
    `max(vintage_dt)` over every series in a release. A BLS-API series carries a
    *fetch-time* vintage rather than a publication date, so a daily sweep
    outranked the real one: the July payroll page read "released 3 Sep" for
    figures published on 7 August, and the new CPI page read "released 4 Sep"
    for July data published on 12 August. It now reads **only midnight
    vintages** — an ALFRED vintage *is* the publication date, a fetch-date
    vintage carries a time of day — and a release with none shows **no date at
    all** rather than when we last looked. It corrected itself the moment the
    CPI backfill landed, to 2026-08-12, with no code change.

20. **"Next release" was a literal, and went stale at 08:30 on the day it
    named.** `NEXT_RELEASE = {"bls.employment_situation": "2026-09-04T12:30:00Z"}`
    was right until the embargo lifted; from 08:31 the page advertised the
    release printed on it as still to come. It now reads from
    `macro_release_dates`, filled from FRED's forward calendar by
    `macro/release_dates.py` — the FRED release id is *discovered* from a series
    we already hold, not typed — and filtered `release_at > now()`, which is what
    makes it self-correcting. Six of seven releases have a FRED calendar; the
    Atlanta Fed tracker has none and correctly shows nothing. FRED gives dates
    only, so the times are the ones the releases themselves state: 08:30 ET, and
    10:00 ET for JOLTS.

    Traps 18, 19 and 20 are one trap wearing three hats: **a fact hard-coded
    once is correct once.** Anything that must be retyped at a release will be
    wrong at most releases. Derive it, or show nothing.

21. **A colour can pass a separation test and still read as one line.** Ink
    against slate measured ΔE 24, comfortably clear of the floor — yet the
    month-and-year panels looked like a single series with two identical legend
    swatches. The reason is the *chroma* floor, not the distance: slate `#35566b`
    measures 0.052 against a 0.1 minimum. It is not a colour, it is a dark
    neutral, and the eye files it with ink. Fixing the line beside it does not
    help; when one mark reads grey, everything mid-toned collides with it (green
    and plum both failed at 13.9 and 14.8). The bar had to gain real chroma.

22. **October 2025 in the CPI is a PARTIAL hole, and the opposite shape from
    trap 4.** 34 of 37 series are null; only **new vehicles, used cars and
    gasoline** were priced, from administrative sources. So a blanket "October
    2025 is missing" rule blanks three series that have data, and a blanket "the
    CPI is fine" rule keeps 34 that do not. One missing month costs exactly one
    month of the twelve-month change — and a second in **October 2026**, when
    the hole becomes the base rather than the current value. On a contribution
    heatmap a near-white cell is a *small* contribution, not a missing one; the
    hole is the column blank in every other row.

23. **`tools/coverage.py` matches a drawn series by its QUOTED ID in the page
    file.** An id assembled at runtime — `"CPI.i_" + key` inside a loop — is
    invisible to it, and every such series is reported shipped-but-undrawn.
    Write ids out in full even where a loop would be shorter; the DRY version
    silently defeats the only check that looks at the page end.

24. **Two ECharts defects with the same signature — the option was accepted and
    ignored.** `label.position` takes a string, not a callback: the callback was
    dropped and every bar label fell back to `inside`, printing muted grey on a
    dark bar (this is why the payroll contribution labels looked clipped for
    weeks). And the shared `yAxis` helper sets `scale: true`, which lets the axis
    begin wherever the data does — right for a line, wrong for a stack, where a
    truncated baseline makes every segment's height a lie about its share.
    `PANELS.stacked` forces zero onto the axis; nothing else should.

25. **A CPI "revision" is a seasonal factor or a rebasing, and never new data.**
    The published index is final the day it prints: the unadjusted CPI has not
    moved on a **single one of the 66 months since 2021**. The seasonally
    adjusted index moved on **59** of those same months, because BLS
    recalculates seasonal factors each January across the prior five years — so
    an SA revision changes the adjustment, never the price data underneath, and
    the current year reads exactly zero until next January reaches back and
    touches it. Do not reason about CPI revisions using payroll intuitions;
    they are different mechanisms wearing the same word.

    Separately, **a level revision spanning 1988 measures the rebasing, not a
    revision.** The CPI moved from 1967=100 to 1982-84=100, so December 1987
    reads 345.900 as first published and 115.600 now — a −230.3 "revision" to a
    figure that never changed. Any revision measure on an index needs a trailing
    window, or it reports the change of base as the largest revision in history.

26. **PPI transmission is attenuation, not delay — and the chain everyone
    reaches for is discontinued.** Two things to know before drawing a
    producer-price pass-through chart.

    First, the familiar crude → intermediate → finished chain (`PPICRM`,
    `PPIITM`, `PPIFGS`) is **DISCONTINUED** on FRED. The live framework is
    Final Demand–Intermediate Demand, launched 2014, whose production-flow
    system runs stage 1 → 2 → 3 → 4 → final demand. That is why the data starts
    in November 2009 and not the 1940s.

    Second, and more important: **there is no measurable lag.** Correlating each
    stage's monthly change against final demand's at leads of nought to six
    months, every stage peaks at **nought** — stage 1 +0.78, stage 2 +0.59,
    stage 3 +0.81, stage 4 +0.83. On twelve-month changes the peak is at one
    month for all four, which is smoothing rather than transmission. A cost
    shock upstream reaches the finished end in the *same month*.

    What changes down the chain is amplitude. Standard deviation of the
    twelve-month change, 2010–2026: **stage 1 6.80, stage 2 8.59, stage 3 6.48,
    stage 4 3.33, final demand 2.69**, with the range compressing from −9.3% ..
    +22.4% to −1.5% .. +11.6%. Note stage 2 is the most volatile, not stage 1 —
    the chain is not monotone at the top, because stage 2 carries the most
    energy and metals. And the asymmetry is real: the raw end went through
    outright deflation in 2023 that final demand never saw.

    So a chart implying a diagonal — a wave moving down the stages over months
    — asserts something this data does not support. Draw the amplitude, not the
    delay.

27. **Each release revises for a different reason, and the intuitions do not
    transfer.** Three dashboards, three mechanisms, measured rather than
    assumed:

    - **Employment Situation** — more survey responses arrive. Two scheduled
      monthly revisions plus an annual benchmark. On 4 September 2026 July
      moved −23,000 → +21,000, a swing of 44,000, which is ordinary.
    - **CPI** — the index does not revise at all. The unadjusted series has not
      moved on any of the 66 months since 2021. Only the *seasonal adjustment*
      moves, each January across the prior five years (trap 25).
    - **PPI** — late reports. Substantial and routine: 120 of the 139 months
      since 2015 moved, median 0.13 index points, largest 0.78. The timing is
      bimodal, 50 first moving at +1 month and 52 at +4 — the four-month one
      being the single scheduled revision BLS documents — while the two groups
      are alike in magnitude, so the split is in when rather than how much.

    Reading one of these through another's expectations gets it wrong in both
    directions: it treats a CPI seasonal-factor tweak as though new data had
    arrived, and it under-reacts to a PPI revision that genuinely reflects new
    reports. Each dashboard's revision panel says which kind it is.

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

Windows, as **systemd user timers** in `America/New_York`: 08:35–12:55 ET for
Employment Situation and Claims, 10:05–13:55 ET for JOLTS, and a 01:40 ET full
sweep. All three carry `Persistent=true`, so a window missed while the machine
or the user manager was down runs once on start-up — which cron could not do.

The windows are **wide because a run outside a release is nearly free**.
`refresh.py` asks `macro_release_dates` two questions before its first FRED
call — is anything due today, and has it already landed — and stops at a query
if either answer says so. It **fails open**: with no usable calendar rows it
declines to judge and runs anyway, because a gate that can silence the pipeline
when its own inputs are missing is worse than no gate. `--force` skips it.

They were 09:55 and 10:55 until 4 September, when FRED published an hour after
the embargo and the 09:35 firing caught the release with twenty minutes to
spare. On a slower morning it would have waited for the 01:40 sweep.

User units, so they need lingering (`loginctl enable-linger`, already on);
without it the user manager exits at logout and nothing fires. Inspect with
`systemctl --user list-timers 'macro-refresh-*'`.

The **full sweep also refreshes the release calendar** (`release_dates.py`, trap
20) — once a day, not every window, because it changes rarely and each run costs
one FRED call per release. A failure there is logged and does not abort the
refresh: the calendar is auxiliary, and a stale future date is caught anyway by
export refusing to show one that has already passed.

**`tools/refresh.sh` has no lock.** Nothing stops a manual run colliding with a
timer's; on 4 September this was hand-timed around twice, into the gaps between
firings. That works only while somebody is watching.

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

## The raw archive

`macro/archive.py`, written at the client layer so every caller gets it without
knowing. FRED and ALFRED will re-serve anything, but **the BLS API has no
point-in-time history at all** — 2,735 vintage rows across seven series existed
only as rows in Postgres, and nothing upstream could return them. The claim that
the database is rebuildable and therefore disposable was false from the day the
BLS adapter landed until this was built.

- **Content-addressed and deduplicated.** The daily sweep re-fetches every series
  whether it changed or not. A blob is named by a hash of its data and written
  once; the append-only `manifest.ndjson` records every fetch either way. The
  whole catalogue is 856 KB across 81 blobs.
- **BLS stamps every reply with `responseTime` in milliseconds**, so raw-byte
  addressing deduplicated nothing — 15 fetches, 14 blobs. Blobs from BLS are
  addressed by the response minus that field; the manifest still records the
  exact byte hash of every fetch.
- **`archive.py --verify` reassembles a series from the blobs and compares it
  with the database.** An archive nobody has read back is a hope, not a backup.
  It handles the BLS batch responses too, which is where it matters most.
- A write failure **raises**. Losing the archive silently puts the system back
  to the database being the only copy, without anyone knowing.

## Guardrails

Do not touch, restart, recreate or rebuild: `caddy`, `everos`, `everos_mcp`,
`litellm`, `linkding`, `postgres`. Do not edit `docker-compose.core.yml` or any
*existing* Caddy site block — appending a new one is fine, and the Caddyfile is a
single-file bind mount, so **append in place** (`>>`) to preserve the inode, then
validate *inside* the container and `caddy reload`, never restart.

## State as of 4 September 2026, end of day

**172 series across 8 releases, ~379,000 vintage rows over ~129,000
observations, 36/36 validations, and every exported series drawn by its page on
all five dashboards.** Nonfarm Payroll runs to 33 numbered tables, CPI 31,
PPI 13, JOLTS 7, Weekly Claims 6.

Every release now carries real ALFRED vintages: CPI and PPI were both backfilled
on 4 September, 66,152 and 16,194 vintage rows, and both stamps picked up their
true publication dates — 12 and 13 August — with no code change, which is what
deriving a date instead of typing one buys.

PPI carries no contributions, deliberately. Contributions need published
weights and the PPI news release has no relative-importance column — CPI Table 1
does, which is what made the CPI ones possible. `contribution` and
`relative_importance` generalise to any weighted index and would need no change
if the PPI weights are ever sourced properly from the detailed report.

The 4 September Employment Situation was the first release to run through the
rebuilt pipeline, and it held. The timer fired at **08:35 ET** — the first
scheduled run in this repo's history to land *after* a release rather than five
hours before it — found nothing for an hour because FRED had not yet published,
and caught it on the 09:35 retry: ingest, backfill, `validate rc=0 35/35`,
export and an ntfy push. **July's payroll change moved −23,000 → +21,000 in
that same run and the vintage-pinned assertions held**, which is the whole
purpose of trap 18. August printed +162,000 against a prior-12-month average of
+31,000.

FRED's own clock is **US Central**, and it published roughly an hour after the
08:30 ET embargo on both the July and August releases. The 08:35–09:55 window
covers that, but only just — see the calendar note under Open right now.

Two sources. FRED/ALFRED for anything it carries; the BLS API **only** for what
it does not — the diffusion indexes, `LNS16000000`, real earnings and seasonally
adjusted marginal attachment. Those carry no vintage history at all (trap 15).

Scheduling is systemd **user** timers, wall-clock in `America/New_York`, all with
`Persistent=true`. Lingering is on; without it none of them run.

| Timer | Fires | Runs |
|---|---|---|
| `macro-refresh-employment` | 08:35–12:55 ET, weekdays | Employment Situation + Weekly Claims |
| `macro-refresh-jolts` | 10:05–13:55 ET, weekdays | JOLTS |
| `macro-refresh-sweep` | 01:40 ET daily | everything, catch-all |
| `dashboards-push` | 23:30 local daily | push to GitHub, then verify by hash |

Root-owned system timers: `bigricebowl-backup` 03:00, `bigricebowl-backup-check`
11:00. `systemctl --user list-timers` and `systemctl list-timers` show them.

> **Backups, fixed 3 September 2026.** They had not run since 18 June: nothing
> scheduled `/usr/local/bin/bigricebowl-backup` any more — no root crontab, no
> timer, nothing in `/etc/cron*` — and had it run it would have died on
> `pg_dump ... investment`, a database dropped in the July teardown, with
> `fail()` exiting before restic. Its paths never included `~/dashboards`, and
> this repo still has **no git remote**.
>
> Now: a systemd timer at 03:00 with `Persistent=true`, dumping every live
> database (enumerated, never named), backing up `~/bigricebowl` and
> `~/dashboards` as **directories** — the original named individual files and
> six of ten had been reorganised away, which restic skips with a warning while
> exiting 0, so a run reported success having stored 7.4 MiB against June's 232.
> Every source is now checked before restic is called. `bigricebowl-backup-check`
> runs at 11:00 and alarms over Telegram if the newest snapshot exceeds 48
> hours, because a script reports its own failure but nothing reports its
> absence. Sources live in `ops/`; the alarm path has been fired and confirmed
> delivered.
>
> **The repository has a 77-day hole, 18 June to 3 September 2026.** Everything
> before it survived — `forget --prune` had not been running either.

The repo **does** now have a remote: `git@github.com:strawer852/dashboards.git`,
pushed nightly and verified by comparing hashes rather than trusting an exit
code. A second clone sits at `C:\Bigricebowl\dashboards` on the laptop. The
GitHub key is an **account** key, not a repo deploy key, so it can write to every
repository on the account — narrow it if that ever matters.

- Alerting is ntfy.sh for the pipeline and Telegram for ops. **William prefers to
  self-host ntfy** — swap `NTFY_URL` when convenient. The Telegram path has been
  fired and confirmed delivered, and **ntfy fired for real on 4 September**
  when the August payroll release landed — both paths are now proven.
- Catalog-driven scheduling (`pub_lag_days`, `staleness_mode`, already columns in
  `macro_series_meta`) is still open, and is what the retired stack converged on.
- The retired `investment` stack's code survives at `~/bigricebowl/workers/` and
  `~/bigricebowl/postgres/migrations/` — 25,078 series across many countries. Its
  data is gone; `FINDINGS_revision_handling.md` and `MACRO_FINDINGS.md` are worth
  reading before extending the pipeline.
- n8n is dormant, not gone: 22 MB of workflows in `~/bigricebowl/n8n`, its own
  `n8n` database, no container running. Not the right tool for scheduling this
  pipeline (the code lives on the host and n8n has no catch-up), but a real
  option if a broader automation surface is ever wanted.

### Open right now

Dated deliberately: this block is the only part of this file that is about a
moment rather than about the system, and it should look stale when it is.

**`planned.yml` is empty and every release has its vintage history.** What is
left is small, and none of it is blocking.

1. **PPI weights, if they are wanted.** The detailed report publishes relative
   importances for the FD-ID structure; the news release does not, which is why
   PPI has no contribution panels where CPI does. With them, `contribution` and
   `relative_importance` would carry over unchanged.

2. **Self-hosting ntfy** is low-risk now that the path has fired for real.

3. **The GitHub key is an account key, not a repo deploy key** — it can write
   to every repository on the account. Narrow it if that ever matters.

4. The everos tarball in the user crontab (03:15 daily, 14-day retention) is
   **redundant rather than load-bearing**: restic backs up
   `/home/strawer/bigricebowl` whole, `everos-data` included. Worth knowing
   before anybody prunes it thinking it is the only copy.

5. Worth a look when convenient: the calendar gate now suppresses most windowed
   runs, so `logs/refresh.log` has become much quieter. That is the intent, but
   it also means a genuinely broken timer would look the same as a quiet day.
   The 11:00 backup check has an equivalent for backups; nothing yet watches
   that the refresh timers are still firing at all.
