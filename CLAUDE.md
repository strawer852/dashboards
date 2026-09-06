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
| `tools/clipcheck.py` | Asks the browser whether any axis label overflows its chart. A guess at character width is what made them too narrow |
| `tools/shoot.py` | Screenshots a dashboard as it renders, from inside the docker network so Authelia is not in the way. The answer to trap 13 |
| `tools/staleness.py` | Every catalogued series against its own frequency — and against BLS before calling one dead. Covers the ~2,350 that reach no bundle, which `coverage.py` cannot see |
| `tools/build_nav.py` | Generates the rail from the specs into every page. **Run after adding a dashboard** |
| `ops/dashboards-timer-check` | Alarms when the refresh timers stop firing. Daily, 06:30 ET |
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
- **`publish` decides what a bundle carries, and it is a column.** The database
  holds far more than the dashboards draw -- the whole establishment survey, the
  CPI item structure, the PPI FD-ID system, all of JOLTS and ECI -- because
  depth is worth having for analysis before anybody designs a panel for it.
  `publish=false` means hold and refresh this series but never sweep it into a
  bundle. It is a property of the *series*, so it lives in a column rather than
  as a list in a spec; a spec naming one in `include_series` still gets it,
  because an explicit request beats a default. Default TRUE, so nothing that
  predates the column changed behaviour.
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
  `--pos #3aa0c9` and `--neg #8c2f27`.
  The positive was lifted twice: off slate, which had no chroma at all, and
  then off a dark blue that still read as one mark under a near-black
  overlay line and sat only dE 3.8 from `--s2`, the series blue. It is now
  dE 47.6 from ink and 18.9 from `--s2`. The pair is deliberately **not**
  balanced in weight: every brighter red collides with `--s1` or `--s6`,
  since the categorical palette already holds two, so a negative bar reads
  heavier than a positive one. A known trade rather than an oversight. *Identity* — which series a line is — is
  the six categorical slots `--s1..--s6`, taken in order and **never cycled**;
  past six, fold the tail into an "other" bucket or use small multiples. The two
  were conflated until 4 September 2026, when the line panel's default ladder ran
  slate → gold → **oxblood**, i.e. the loss colour identifying "series 3".
  Every slot is validated against this site's own paper rather than a generic
  white: worst adjacent colourblind ΔE 11.5, normal-vision 18.2, all ≥3:1
  contrast. Re-run the check before changing any of them — ordering is the
  colourblind-safety mechanism, not decoration.
- **Charts in a row share a baseline.** `.row` is a two-column grid and the two
  cells rarely carry the same amount of prose, so the charts used to start at
  different heights -- which defeats the only reason to put them side by side.
  A cell is a flex column, `.chart` takes `margin-top: auto`, and the legend
  takes it instead when there is one so the key travels with its chart. Where a
  pair still disagrees the two charts have different declared heights, which is
  a page bug, not a layout one -- five rows on the payroll page do.

- **A panel must answer a question that stays worth asking.** The releases name
  their movers each month — portfolio management led July, fresh vegetables and
  thermoplastic resins fell — and building panels around those produces a page
  that is stale the day the next release lands. Items earn a permanent place on
  three grounds only: large by weight, persistently volatile, or a direct input
  to something else that matters. The PPI detail panels were chosen that way,
  which is why they do not match the release's own emphasis.

- **Chart type follows structure, and the structure is measured.** For a
  decomposition the choice between a stack and ranked bars is not taste. A
  stack needs two things: the parts must partition the whole, and there must be
  at most six of them, because that is where the categorical palette stops
  (trap 21). Both are testable. Eleven of the fourteen payroll supersectors
  reconcile to their parent with six or fewer children and are drawn stacked;
  retail's nine and transportation's ten reconcile too but exceed the palette,
  so they are ranked contribution bars, where colour encodes sign instead of
  identity and the count does not matter. Utilities has no children in Table
  B-1 at all and gets a note saying so rather than an invented chart.

  Getting the child set right needed three attempts and none of them was
  guesswork: display level alone gives Utilities no children and Construction
  five that double-count to 13,635 against a parent of 8,359, because B-1 skips
  levels and lists some children beside their own parent. Walking spans fixes
  Mining; the industry-code tier fixes Construction. **The test that settles it
  is reconciliation to the parent** -- the same test validate.py already applies
  to the supersectors against PAYEMS -- and every one of the fourteen now passes
  it, worst residual 0.5k.

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

4. **The October 2025 gap is household-survey only, and it is PERMANENT.**
   The federal shutdown that began 1 October 2025 stopped CPS field collection,
   and BLS has said the October reference period will not be collected
   retroactively: a monthly unemployment rate published continuously since
   January 1948 now has one empty month, for good. `UNRATE`, `CIVPART`,
   `EMRATIO`, `U6RATE` and every other CPS series are genuinely null; `PAYEMS`
   carries 158,408, because the establishment survey ran on electronically
   filed employer records and BLS merged October into November's report.
   Measured across the catalogue: **59 of 59 household-survey series lost
   October, 201 of 202 establishment series kept it.**

   **The rule that predicts the shape, and the one worth remembering: a survey
   that had to be taken during the month is gone; a record that could be
   collected later survived.** It also explains the single establishment
   casualty -- `CES0500000013`, average hourly earnings in 1982-84 dollars,
   which is deflated by a CPI that does not exist for October.

   So a blanket "October 2025 is missing" rule punches a false hole in the
   payroll line, and a blanket "the payroll release is fine" rule invents a
   household survey that was never taken. Two consequences that outlive the
   event: **never wait for this month to arrive** (it is not late, it is
   absent -- trap 49), and **never interpolate across it**. The transforms in
   `brb-dash.js` return null when either endpoint is null, and the bundle
   encodes months as `start` + `step` with a dense `values` array, so the hole
   survives export as a null slot rather than a dropped one. That is not
   incidental: if the exporter ever compacted nulls away, every date after
   October 2025 would silently shift by a month.

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

8. **Panels need a trailing window, and one outlier can defeat the window you
    chose.** Two versions of the same trap. Without a window at all, payrolls
    plot from 1939 and the war years put the axis at +/-5,000k, flattening
    everything recent to a line. The window is applied *after* transforms so a
    3-month average at the left edge still uses real prior data.

    The second version is subtler and only a picture catches it. The JOLTS
    separations mix was drawn stacked over 120 months, and April 2020 -- when
    layoffs took nearly every separation and the bar reached 15.9m against a
    normal 5.5m -- squashed nine years of composition into the bottom third.
    Every check passed: the panel drew 371 marks, coverage was 100%, validation
    36/36. The chart was simply useless for the one question it existed to
    answer. Sixty months excludes the spike and the note carries the figure
    instead. **Check the range of what you are plotting against the range you
    care about**, and look at it.

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
    trap 4.** Measured across all 469 monthly CPI series: **439 are null in
    October and fine again in November**, and only 20 were priced at all --
    new vehicles, used cars and gasoline among them, from administrative
    sources that needed no field visit (trap 4's rule again). A further **10
    went null in October 2025 and have not returned since**, which is a
    different fault wearing the same shape and must not be counted as shutdown
    damage; find those by last non-null value, not last row (trap 49). So a blanket "October
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

28. **A discontinued series passes every check and draws nothing.** `WPS3012`,
    truck transportation of freight, stopped in December 2011; FRED still serves
    it. It had observations, so the exporter was content. It had a panel, so
    `coverage.py` reported it drawn at 100%. Its acceptance tests pin old
    vintages, so validation passed 36/36. Every number in every report was
    correct and the chart was empty, because a panel shows the recent past and
    the series had left it fifteen years earlier. **Before trusting a new
    panel, check the last non-null observation against today.** `coverage.py`
    now does this for every series; the replacement is `WPS301`, the live SA
    parent. A dead series is recorded in the spec's `exclude_series` with the
    reason, not deleted in silence.

29. **Weeks are not short months.** The first version of that staleness check
    treated every step as a whole number of months, so a weekly series computed
    a last observation two years in the FUTURE, returned a negative gap, and
    could never be flagged -- a silent exemption for the dashboard that updates
    most often. Weekly is date arithmetic. And the grace period scales with the
    period: a fixed six months condemns every healthy annual series, since 2025
    is the latest an annual series can carry for most of 2026.

30. **A guard that has never fired is not known to work.** Both defects above
    were found by feeding the new check seven synthetic series -- dead monthly,
    live monthly, quarterly, weekly current, weekly dead, annual healthy,
    annual dead -- rather than by running it once on data that happened to be
    clean. It passed the real bundles before either bug was found.


31. **A dashboard without a timer is a dashboard a day stale.** CPI and PPI were
    built, validated and shipped with no release-morning refresh: the only job
    that touched them was the 01:40 ET sweep, seven hours BEFORE the 08:30
    embargo, so each release would have been picked up the *following* night.
    Nothing was broken and no check complained — the employment timer had been
    fixed months earlier and simply never extended to the dashboards added
    since. The fix was first another typed unit file; that is now
    `macro-refresh-due`, which asks the calendar instead. See trap 33.

32. **The watchdog had a typed list of what to watch.** `dashboards-timer-check`
    named its four timers inline, so the day `macro-refresh-inflation` was added
    it was invisible to the check whose entire purpose is noticing a timer going
    quiet — within a day of being written. The list now comes from the repo's
    own `systemd/*.timer` files. Note what it is deliberately *not*: asking
    systemd which timers are running and then checking those are running is a
    tautology that passes whatever the machine happens to be doing. The repo
    says what should exist; the machine is asked whether it does, and the check
    tests `is-enabled` as well as `is-active`.


33. **The schedule is a question, not a list.** Three windowed timers named five
    release ids between them, so a new dashboard needed somebody to remember a
    unit file — and twice nobody did. `refresh.py --due` asks
    `macro_release_dates` which releases are dated today, are past their
    embargo, and have nothing stored under today's vintage, then fetches
    exactly those. One timer, `macro-refresh-due`, 08:35–14:55 ET on weekdays;
    a new release needs a calendar row and nothing else. Two properties are
    load-bearing: it resolves **per release**, where the old grouped gate asked
    `_ALREADY_LANDED` for a whole list and would have gone quiet on the second
    of two releases sharing a day (10 September 2026 carries PPI *and* claims);
    and it respects each release's own embargo, so JOLTS at 10:00 ET is not
    polled at 08:35. An empty forward calendar is treated as a fault and
    notified, because `--due` with no calendar would poll nothing, for ever,
    in silence.

34. **The already-landed guard had never once fired.** It compared an ALFRED
    vintage in `America/New_York`, and ALFRED stores a vintage at **midnight of
    its realtime date** — so `2026-09-04 00:00+00`, the 4 September vintage,
    reads as 3 September in Eastern and never matched today. The log says it
    plainly: the release landed at 13:35Z and the windows at 13:45Z and 13:55Z
    each refetched all 64,220 observations. The vintage side is now read on the
    **UTC** calendar and the release-date side stays Eastern, which looks
    inconsistent and is not: `export.py` already identifies these rows the same
    way, by their `00:00:00` UTC time. Scoped to the 103 rows the release itself
    wrote, the old predicate returns 0 and the fixed one 103.

35. **The orchestrator has never once passed a BLS series to ingest.**
    `refresh.py`'s `series_for()` selects `WHERE source='fred'` in **both**
    branches, so every scheduled run -- windowed and sweep alike -- fetches only
    the FRED catalogue. `ingest.py` grew its source dispatch long ago and
    handles the BLS batch correctly; the filter in the *caller* was never
    removed. This is the loose end trap 15 named -- "that has to become a
    dispatch before any non-FRED series is added" -- finished in the callee and
    missed in the caller.

    The symptom is the quietest one this system produces. On 5 September the
    sweep logged `ingest rc=0 fetched 128897 observations; inserted 0 rows`
    while six BLS-only series sat a month behind data the API was serving right
    then. A run that fetches everything and inserts nothing is
    indistinguishable from a healthy day on which nothing changed. Nothing
    alarmed, and validation passed 36/36, because every assertion pins a
    published figure rather than a freshness.

    **37 series were affected** -- 36 in the Employment Situation and
    `CUSR0000SETE` in the CPI. **Fixed 5 September 2026**: the filter is gone
    from both branches and the docstring says not to reintroduce one, because
    if a source ever does need excluding from a scheduled run that is a
    property of the series and belongs in a column, not in a literal in the
    orchestrator.

    Proving it took more than reading the diff. The data was already current,
    so diff-on-write inserted nothing and the database could not show whether a
    fetch had happened. The **archive manifest** could: it is append-only and
    records every fetch whether or not the bytes deduplicate. A forced run over
    the Employment Situation added 266 manifest entries -- 261 FRED plus
    **5 BLS**, exactly the five 20-year spans that 36 BLS series chunk into.
    Before the fix that number was 0. Verify a fetch where fetches are
    recorded, not where rows would land if they happened to be new.

36. **A FRED id derived from a BLS industry code 404s on exactly the biggest
    aggregates.** The CES id is `CES` + 8-digit industry code + 2-digit data
    type, and it resolves for all the fine industry detail -- then fails for
    goods-producing, durable goods, nondurable goods and
    trade/transportation/utilities, which FRED carries **only** as `USGOOD`,
    `DMANEMP`, `NDMANEMP` and `USTPU`. Every one of the 19 average-weekly-hours
    series is the same shape (`AWHAETP`, `AWHAEGP`, ...): data type `02` 404s
    universally, while `03`, `04` and `11` resolve normally. So a derivation
    script succeeds on 140 small industries and silently drops the five that
    carry the most employment.

    A further **29 of the 174 Table B-1 industries are not on FRED at all** --
    mostly health-care and professional-services detail -- and are reachable
    only through the BLS API, hence without vintages, hence trap 15.

    The method that works: take the industry list from BLS's own `ce.industry`
    file, take FRED's ids from `fred/release/series` for a release id
    *discovered* from a series already held, then **verify every candidate by
    checking it reproduces the published figure** in the news release table.
    Titles alone do not catch the mnemonic cases; values do.

37. **The bundle takes the whole release, so cataloguing a series ships it.**
    `export.py` builds each bundle from the spec's `include_releases`, i.e.
    every catalogued series for that release. The design assumes you only
    catalogue what you intend to draw, and that held until 5 September, when
    205 series were ingested for analysis rather than display. The payroll
    bundle went 906 KB / 106 series to **1933 KB / 311 series** in one export,
    and `coverage.py` fell from 100% to **34.1%**.

    Note which check noticed. `export.py` asserts the *other* end -- every
    catalogued series lands in some bundle -- and printed "all catalogued
    series are consumed by at least one dashboard" while 205 of them were dead
    weight in the payload. Only `coverage.py`, which reads the page, saw it.

    nginx gzips `application/json`, so the wire cost was 535 KB rather than
    1.9 MB, which made this a degradation rather than a breakage. It still had
    to be settled, because **a permanently red check is a disabled check**:
    left at 34.1%, `coverage.py` stops being the thing that catches the next
    real defect.

    **Fixed 5 September** by the `publish` column above. The release sweep
    reads `WHERE publish`, and so does the orphan check -- that second half
    matters, because an unpublished series is intentionally consumed by nothing
    and counting it as an orphan fails the export, which `refresh.py`
    escalates into a failed refresh and an alert. All five bundles returned to
    their pre-ingest size and coverage to 100% while 2,344 analysis-only series
    sat in the database untouched.

38. **`ingest.py` warned about an unknown series id and exited zero.** A
    one-off driver built its list with `cat` over six files that had been
    written without trailing newlines, so the last id of each was glued to the
    first of the next: five nonsense tokens, ten real series never fetched.
    Ingest printed `!! not in catalog`, ingested the other 2,240, and returned
    **0**. The step logged RC=0 and the hole surfaced only at
    `validate.py`'s structural check -- "catalogued series with no
    observations: 9" -- which on a normal release would have been a whole
    release later.

    It now **refuses**: an id the caller named that is not catalogued means the
    caller built its list wrongly. The orchestrator only ever passes
    `series_for()` output, which cannot contain an unknown id, so nothing
    legitimate is refused. The general form is the one worth keeping: *a
    warning that does not change the exit code is invisible to everything
    downstream.*

39. **BLS was refetching ninety years of history on every routine run.** The
    API caps at 50 series and 20 years per call, so 300 BLS-sourced series is
    7 x 5 = 35 calls -- every ingest, against a 500/day key limit. A release
    morning with several windows could reach it, and a cap breach fails ingest,
    which fails the refresh and alerts. `ingest.py` now asks what it already
    has: a series with nothing stored still gets the full history, otherwise
    five years back from the batch's oldest last-observation, which is wider
    than any seasonal-factor revision BLS applies (trap 25) and one call
    instead of five.

40. **FRED can stop updating a series that BLS still publishes, and it looks
    exactly like a discontinued one.** Trap 28 was a series dead at source.
    This is the opposite and is not visible from FRED at all: FRED's
    `observation_end` simply stops, the title carries no "DISCONTINUED" marker,
    and every check that compares us against FRED agrees we are current --
    because we are. We are faithfully mirroring a stale mirror.

    Found by asking the *other* source. Of 74 series holding nothing newer than
    a year old, all 74 ended exactly where FRED ended them, so nothing was
    behind. But **six ECI series were stuck at October 2017 while BLS had data
    to April 2026** -- eight and a half years missing -- plus two CPI series a
    year behind. They are now `source='bls'`, and where the two sources overlap
    they agree to within 0.1 index point, which is ECI's own revision
    granularity rather than a difference of basis.

    The remaining 66 are genuinely dead: the BLS API returns nothing at all for
    the 19 PPI and 45 Productivity ids, and agrees with FRED on the last 2 ECI.
    `WPS3012` -- trap 28's series -- still returns rows to 2011, which is what
    proves the probe works rather than the ids being malformed.

    **The check is cheap and worth repeating** whenever a series looks frozen:
    compare the last observation against BLS as well as FRED, because "FRED
    agrees with us" answers a different question from "this series is current".

41. **A ratio across two sources is wrong by their unit gap, and looks
    perfectly healthy.** Trap 7 says units differ by source -- claims arrive in
    persons, JOLTS levels and the household survey in thousands. Side by side
    that is survivable. Divided, it is fatal: continuing claims over the
    unemployment level computed 1,900,000 / 7,000 = 271 where the answer is
    0.27. The panel drew, `coverage.py` counted it, `validate.py` passed 36/36,
    and the number was out by three orders of magnitude. Only the picture
    showed it. Series specs now take **`scale`**, applied last, after any
    transform and any `over`, as the one place to reconcile units.

    In the same panel, **`over:` matched dates exactly**, so a weekly numerator
    over a monthly denominator missed on every date and produced an empty
    chart -- silently, since the one prior use divided two monthly series both
    dated on the first. It now uses `alignAsOf`, which is trap 6 applied where
    nobody had looked: a coarser denominator means the most recent value at or
    before this date.

42. **Measured, nothing in this repo's data leads payrolls.** JOLTS peaks at a
    lead of nought on every measure (openings, quits, hires, layoffs, and
    hires-less-separations at +0.97, which is the accounting identity rather
    than a forecast) and publishes a month *later* besides. Initial and
    continued claims also peak at nought, in every era: the insured
    unemployment rate against twelve-month payroll growth runs -0.66 in the
    1970s and 80s, -0.78 in the 1990s, -0.96 in the 2000s, all at a lead of
    nought, weakening to -0.67 in the 2010s and turning **positive** at +0.60
    since 2021 -- almost certainly both series falling together after the
    reopening rather than a relationship, on 62 observations.

    What claims have is **timeliness, not lead**: weekly, and three to four
    weeks before the payroll print covering the same month. Say that instead.
    And the "claims off the cycle low" rule is a confirming measure at best --
    at the 1990, 2007 and 2020 peaks it read +9%, +9% and +10% against a median
    week of +6%.

    Correlations here are always computed twice, with and without
    Feb 2020 - Jun 2021. A shock that moves everything at once manufactures
    correlation at every lag; including it collapses every JOLTS figure to
    about 0.1 and would have hidden all of the above.

43. **A bundle is a rendering cache; the database is the archive.** They had
    been the same thing, so 53 state claims series shipped 112,529
    observations to draw a 52-week heatmap. `truncate_history` in a spec ships
    a recent window instead. It discards nothing: every observation and every
    vintage stays in Postgres and the next export can widen the window
    straight from it. The claims bundle went 1,769 KB to 791 KB with no
    visible change to the page.

    **The guard is the whole of it, and mine had the exact hole it existed to
    prevent.** Cutting a series below what its panel needs empties the chart
    silently, so the requirement is read from the PAGE rather than trusted from
    the spec: for each truncated series, the panels naming it, their window (or
    months) plus any transform lookback. That gave 104 for the state series --
    the heatmap draws 52 weeks of a year-on-year change -- and 156 looked
    generous.

    It was wrong, because a requirement can arrive **through a derived
    measure**. Those same 53 series feed a breadth line drawn over 520 weeks
    that compares each state with itself 52 weeks earlier, needing 572. The
    line lost eight of its ten years, still drew, and tripped nothing;
    `coverage.py` already knew the rule -- a drawn derived series consumes
    whatever it was built from -- and the guard did not. What gave it away was
    the axis losing half its tick labels between two screenshots.

    So: follow `derived_from` before believing a requirement.

    Two further things the first version got wrong, both now fixed. The check
    **"no series lost observations against the shipped bundle" went quiet on
    exactly these series**, since a deliberately short bundle is a weak thing to
    compare the database against -- it could only ever have seen loss below the
    kept window. The exporter now records `full_n`, the untruncated non-null
    count, and the check reads that: `AKICLAIMS` ships 624 observations and is
    still checked against 2,115.

    And the lookback was counted from explicit `periods:` alone, which misses
    both a moving average (declared as a series-level `window`) and a bare
    `diff` (one observation). All three are now counted, generously: the
    panel's own window is the largest in the block, any other window in it is a
    transform width, and the presence of a transform costs one more. A few
    observations of payload against a chart that renders short rather than
    empty -- which is the failure nothing else here would catch.

44. **A BEA hierarchy cannot be recovered from the numbers.** The 210 series
    behind PCE are a tree -- line items under aggregates under the total -- and
    the API returns them as a flat list. Reconstructing the tree by testing
    which children sum to which parent failed **twice, in both directions**: a
    loose tolerance made nested items look like siblings of their own parent,
    and an exact one found no children at all, because published rounding means
    a parent rarely equals its children to the last decimal. The structure is
    not in the values and no tolerance will find it. **BEA publishes the
    hierarchy as indentation in the downloadable workbook** -- read it from
    there. The general form: when a shape is documented somewhere, do not infer
    it from data that merely reflects it.

45. **`add_series.py` recorded SAAR as unadjusted.** Its adjustment flag had two
    branches, seasonally adjusted and not, and BEA returns a third thing --
    seasonally adjusted at annual rates. That fell through to the `else` and was
    filed `NSA`. Nothing failed: the series ingested, drew and validated, while
    the catalogue recorded the opposite of the truth about them. It is the kind
    of error that surfaces only when someone later compares an SA series with an
    NSA one and cannot see why the shapes disagree. **Record what the source
    states, not the nearest of the options already coded for.**

46. **A format name the engine does not have fails silently to the default.**
    `format: "pct1"` was invented in a spec on the assumption that it meant one
    decimal place. `fmtFor` has no such name, matched nothing, and returned the
    default formatter -- so the chart rendered, with the wrong number of
    decimals, and nothing anywhere reported an unknown name. Compare `derive`,
    which **throws** on an unknown transform. The formatter should do the same;
    until it does, check a format name against `fmtFor` before using it. **Any
    lookup that falls back instead of failing will hide a typo forever.**

47. **A cloned page keeps the original's contents list.** The PCE dashboard was
    built by copying the PPI page and replacing the body. The replacement ran
    from the first table heading downwards, so everything above it survived --
    including the in-page contents nav, which listed PPI's tables on the PCE
    page and linked to anchors that did not exist. **The user found this, and no
    check did**, which is the whole lesson: nothing validated the page against
    itself. `tools/clipcheck.py` now resolves every in-page link, and the
    contents list is **generated from the tables actually present** rather than
    written by hand. Build a nav from the document, never in parallel with it.

48. **The engine could only draw a series, and a composition is not one.** Every
    panel type read a series from the bundle and plotted it against time.
    Comparing what the CPI and PCE baskets are *made of* has no time axis at
    all -- a weight is a fact about a moment. There was no way to express it,
    and the temptation was to hand-write a chart into the page. That is exactly
    the defect the second project rule names: **if a dashboard needs new
    JavaScript, the engine is missing a panel type.** `PANELS.compare` is that
    panel -- two named baskets, any number of rows -- and it is generic, not a
    CPI-versus-PCE special case. Note what it deliberately does not do: it takes
    its numbers from the spec, because they are published weights from two
    agencies rather than series in the database, and the page states the source
    beside them.

49. **A published null is still a row, so freshness read from the last ROW is a
    lie.** `tools/staleness.py` measured currency as `max(observation_dt)`,
    which counts months in which the source published nothing but a hole. Two
    CPI items whose last real figure was **September and October 2024** carried
    null rows forward to October 2025 and so read as a year fresher than they
    were -- and I repeated that error to the user, describing them as October
    2025 stops when October 2025 was merely their last empty row. Changing the
    check to `max(observation_dt) FILTER (WHERE value IS NOT NULL)` moved the
    overdue count from 62 to 74: **twelve series had been hiding behind their
    own nulls.** Wherever currency matters, ask when the source last said
    something, not when it last said nothing.

50. **A title outlives the fact it states.** Six ECI series carried
    "(DISCONTINUED)" in their titles, captured from FRED, while running current
    to 2026 Q2 off the BLS API -- they were re-sourced under trap 40 and the
    *data* was fixed while the *label* was not. All six were `publish=false`, so
    the lie had never reached a page and no check looks at titles. It would have
    shipped on the labour costs dashboard as a caption reading DISCONTINUED
    under a line running to last quarter. **When you re-source a series, the
    title is part of what you re-source.** Found by reading the catalogue before
    drawing from it, which is the habit to keep: a title is a claim, and this
    repo verifies ids by value (trap 36) precisely because names lie.

51. **When one series flattens a panel, measure the rest before splitting it
    out.** Table 5's four-line price decomposition was unreadable because unit
    profits ranges -20% to +51%. Splitting profits into its own panel and
    looking again showed the panel *still* flat: unit non-labour costs swings
    -20% to +21% too, and the assumption that the loudest series was the only
    loud one cost a second pass. **The honest split turned out to follow the
    economics rather than the axis** -- the labour side in one panel, the
    non-labour side in another -- which is both readable and a better answer to
    the question than a four-line chart would have been. The general rule: a
    crowded axis is a symptom, and the fix is a grouping that means something,
    not the removal of whichever line is currently worst.

52. **A panel that hard-codes a frequency works until the first series of
    another one.** `PANELS.heatmap` formatted its axis and tooltip with a
    literal `"M"`. Every heatmap on the site had been monthly, so nothing was
    visibly wrong for as long as that held; the first quarterly heatmap would
    have labelled 2026 Q2 as "Apr 26", on the axis and again in the tooltip,
    with nothing raised. `label()` had handled `Q`, `W` and `D` since it was
    written -- the heatmap simply never passed the frequency it already had.
    Fixed generically: it now takes the frequency from the same series it takes
    the date axis from, so the two cannot disagree. **Anywhere a default stands
    in for a property the data already carries, it is waiting for the first
    case that differs.**

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

`tools/refresh.sh` takes a **non-blocking lock** on fd 9, held through the exec
into python, so a manual run and a timer's cannot ingest at once. A run that
finds the lock held logs the skip rather than exiting silently — a collision
that looks like "nothing to do" is worse than one that says so.

**`dashboards-timer-check` watches that the timers are still firing**, daily at
06:30 ET. It exists because the calendar gate removed an accidental heartbeat:
before it, a windowed run fetched every series every time, so a quiet
`refresh.log` meant something was wrong. Now a quiet log is normal, and a dead
timer looks exactly like a quiet day. The check looks at the mechanism instead —
lingering, every timer active, no unit failed, the sweep triggered within 26
hours, `status.json` fresh, and since 5 September **no series quietly stopped
publishing** — and alarms over Telegram, which is the ops channel rather than
the pipeline's ntfy.

That last one is `tools/staleness.py`, and two of its properties are the
point. It **only reports a fault**: 74 series are dead at source and nothing
can be done about them, so those exit 0, because alarming daily on the
unfixable trains everyone to ignore the alert. Non-zero means our source is
stale while another has newer data, a dead series has reached a page (trap 28
with an alarm attached), or something is catalogued with no observations at
all. And its own failure is **logged and swallowed** — it makes a BLS API
call, and a monitoring call that can fail the job it monitors is worse than no
monitoring. All three fault paths were fired with synthetic rows and a
substitute bundle directory before it was trusted; the grace policy is
imported from `coverage.py` rather than restated, so traps 29 and 30 have one
definition.

On its own it cannot catch the user manager being gone, a dead box, a dead
network or a full disk — all of which produce **silence**, and silence is
indistinguishable from a healthy quiet day when every alert originates on the
machine being watched.

That is what **`HEALTHCHECK_URL`** closes. Set it in `.env` to a ping URL from
any external service and the daily check pings it on success and hits
`URL/fail` on failure; that service alarms when the pings stop. The absence of a
signal becomes the alarm and the watching happens off-box. **Dormant until set**
— unset, nothing is sent and nothing breaks — and it must never point at
anything running on this VPS, since a dead-man's switch hosted on the machine it
watches is not one.

The ping can never change the check's outcome: every failure in it is logged and
swallowed, because a monitoring call that can fail the job it monitors is worse
than no monitoring. Verified across all six paths on 4 September — dormant,
reachable, unreachable, genuine success, the failure path, and the `/fail`
suffix.

**On self-hosting ntfy** (long an open wish): it would move the pipeline's alert
path onto the machine the alerts are about, so it would go down exactly when it
is needed. Both current paths — ntfy.sh and Telegram — are deliberately
external. If ntfy is self-hosted for other reasons, keep the ops alerts
(backup check, timer check) off-box.

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

## State as of 6 September 2026, end of day (second pass)

**3,126 series across 9 releases and three sources, 3,442,990 vintage rows
over 1,367,052 observations spanning 1913-01-01 to 2026-08-29, 37/37
validations, and every *published* series drawn by its page on all seven
dashboards.** Nonfarm Payroll runs to 33 numbered tables, CPI 33, PPI 23, PCE
15, Labour Costs 15, JOLTS 11, Weekly Claims 10 -- 140 in all. **818 series are on a page and
2,308 are held for analysis**, which is the split the `publish` column exists to
make (trap 43).

Every release is now complete at the level its news release publishes, and the
split between what is held and what is drawn is explicit:

| Release | Published | Analysis-only | Total |
|---|---|---|---|
| `bls.jolts` | 44 | 640 | 684 |
| `bls.ppi` | 61 | 578 | 639 |
| `bls.cpi` | 176 | 293 | 469 |
| `bls.eci` | 2 | 402 | 404 |
| `bls.employment_situation` | 138 | 159 | 297 |
| `bls.productivity` | 2 | 280 | 282 |
| `bea.personal_income` | 232 | 3 | 235 |
| `eta.claims` | 59 | 56 | 115 |
| `frb.wage_tracker` | 1 | 0 | 1 |

**Labour Costs is the seventh dashboard**, built 6 September and the first to
need **no ingestion at all** -- ECI and Productivity had been in the database
and drawn by nothing since 5 September. It names its 39 series in
`include_series` rather than taking a release whole, because between them the
two releases hold 686 and the page draws 39; an explicit list overrides
`publish=false` without touching the catalogue, which is what that path in
`export.py` exists for. It is also the **first page fed by two releases that
publish a week apart** (ECI 30 October, Productivity 5 November), so one half is
routinely fresher than the other and the lede says so. Nothing special is needed
to keep it current: `export.py` writes every spec on every run.

CPI is the whole of news release Table 2 -- all 338 expenditure categories,
mapped to item codes with none unmatched. PPI is the entire Final
Demand-Intermediate Demand system. JOLTS, ECI and Productivity are their whole
national catalogues.

**FRED does not carry most CPI detail.** Only 71 of the 338 published Table 2
categories are on it; 267 come from the BLS API and therefore have no vintage
history at all, the same shape as the 29 CES industries. In total **456 series
are BLS-sourced, 210 are BEA-sourced, and 359 FRED series have no ALFRED history
either** -- all 1,025
carry `vintage_mode='fetch_date'`, corrected in bulk on 5 September from the
`from_row` they were added with, by asking which series still held only
provisional `fred_csv` rows after a backfill.

**74 analysis-only series are dead at source** -- 45 Productivity (annual PRS
lines ending 2022), 23 PPI, 4 CPI, 2 ECI -- confirmed against the BLS API, not just
against FRED (trap 40). What is held for them is the complete history; there is
nothing to recover. Eight others that looked identical were not dead but
stale-on-FRED, and were re-sourced. None of the 74 is drawn, so none can
produce trap 28's empty chart, but check the last observation before building a
panel on any of them. The 4 CPI ones are the household-operations family and
legal services, which BLS stopped publishing during 2024 and which read as
current until the freshness check was taught to ignore null rows (trap 49); they
are in no spec and no bundle.

The Employment Situation went from 92 series to **297** on 5 September: the
establishment survey is now complete at the level the news release publishes it
-- **all 174 Table B-1 industries**, plus B-2 average weekly hours and overtime
and B-3 average hourly and weekly earnings for all 19. Every id was verified
against the published August 2026 figure before ingestion (trap 36), and all
174 reproduce from the database afterwards. 176 came from FRED with full ALFRED
history; 29 exist only on the BLS API and so carry no vintages at all.

Two pre-existing defects surfaced during that verification. **28 series had
never been backfilled** and still sat on provisional `fred_csv` rows with one
vintage each, although ALFRED held real history for them (`LNS14000003` depth
1.19, `CES9091000001` 1.98) -- mostly the household-survey unemployment cuts and
government employment. That is fixed: the release now carries **zero**
provisional rows. The second is trap 35 -- the orchestrator had never once passed a BLS
series to ingest -- and it was **fixed the same day**. The trap records how
the archive manifest proved it, the database being unable to: a run that
fetches everything and inserts nothing looks exactly like a healthy one.

Deliberately not ingested, each a straightforward repeat of the same pass: NSA
counterparts of the 174; production and non-supervisory workers (Tables B-5 to
B-8); and the Table B-4 aggregate-hours indexes, which are derivable from
employment times hours.

Every release now carries real ALFRED vintages: CPI and PPI were both backfilled
on 4 September, 66,152 and 16,194 vintage rows, and both stamps picked up their
true publication dates — 12 and 13 August — with no code change, which is what
deriving a date instead of typing one buys.

PPI also carries the detail that feeds **PCE** — physician care, hospital
inpatient care and portfolio management — because the national accounts source
those from producer prices rather than from the CPI, which is the durable reason
to read PPI detail at all. Portfolio management is published **unadjusted only**
(no SA version exists on FRED, unlike the two health series) so it has its own
panel, dashed and captioned: it is on a different basis *and* swings −20% to
+25%, which on a shared axis flattened the others into a line.

Both inflation dashboards carry contributions. PPI news release **Table 1** has
a relative-importance column, dated Dec. 2025, exactly as CPI Table 1 does — the
weights reconcile (goods 29.028 + services 68.338 + construction 2.634 =
100.000) which is how you know they are the published ones. What was said here about
**intermediate demand** was too strong, and 6 September corrected it: Table 1
publishes relative importances for ID5 (147 rows) and ID6 (55). What is true is
that they are shares of their OWN group rather than of a common total -- each
stage index is its own aggregation base at 100.000 -- so they cannot be pooled
with final demand or with each other, and the chain is still drawn as rates
rather than stacked.

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

**Three sources.** FRED/ALFRED for anything it carries; the BLS API for what
it does not — the diffusion indexes, `LNS16000000`, real earnings and seasonally
adjusted marginal attachment, and most CPI detail; and the **BEA API** for the
PCE underlying detail, which exists nowhere else. Neither the BLS nor the BEA
API serves vintages, so all 666 of their series carry `fetch_date` and have no
point-in-time history at all (trap 15). A release fed by two of the three can be
half updated with every check green, which is why `tools/staleness.py` compares
sources *within* a release.

Scheduling is systemd **user** timers, wall-clock in `America/New_York`, all with
`Persistent=true`. Lingering is on; without it none of them run.

| Timer | Fires | Runs |
|---|---|---|
| `macro-refresh-due` | 08:35–14:55 ET, weekdays | whatever the calendar says is outstanding |
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

The repo has a remote, pushed nightly and verified by comparing hashes rather
than trusting an exit code. A second clone sits at `C:\Bigricebowl\dashboards`
on the laptop.

**Access is by per-repository deploy key**, narrowed from an account key on
4 September 2026. Two things make this work and both are easy to get wrong:

- A public key can be registered **once across the whole of GitHub** — as an
  account key *or* as a deploy key on *one* repo, never both. Trying to reuse
  the existing key as a deploy key fails with "Key is already in use". Two new
  keys were generated, one per repo (`~/.ssh/id_deploy_dashboards` and
  `id_deploy_bigricebowl`), and each needs **Allow write access** ticked or the
  nightly push fails read-only.
- Both repos are on `github.com`, so one `Host github.com` block could name only
  one key. `~/.ssh/config` defines the aliases **`github-dashboards`** and
  **`github-bigricebowl`**, and the remotes use them:
  `git@github-dashboards:strawer852/dashboards.git`. **`IdentitiesOnly yes`** is
  the line that matters — without it ssh offers every key it has, the account
  key is accepted first, and GitHub authenticates at account level while
  everything appears to work.

The check that tells a real narrowing from one that only looks right:
`ssh -T git@github-dashboards` must answer **"Hi strawer852/dashboards!"**. If
it says "Hi strawer852!" the account key is still doing the work.

- **The dead-man's switch is live.** `HEALTHCHECK_URL` is set and the ok
  ping returns 2xx; `dashboards-timer-check` runs daily at 06:30 ET and
  pings on success, `URL/fail` on failure. **Both paths are now proven against
  the real hc-ping.com URL, 6 September 2026.** The `/fail` half fired twice
  that day: once unplanned at 10:30Z, when the scheduled run caught two dead
  CPI series still in the exported bundle and alarmed correctly, and once
  deliberately at 13:10Z. Success pings at 13:09Z and 13:10:31Z recovered it
  each time, and the ping-failure count in `logs/timer-check.log` did not move,
  which is how you know a ping was accepted rather than merely attempted.

  Induce a fault without touching anything: `MAX_AGE_HOURS=0
  ops/dashboards-timer-check`. It is read as `${MAX_AGE_HOURS:-26}`, so the
  real script takes its real failure path over real data, sends a real Telegram
  alarm and a real `/fail`, and exits 1. Then run it again with no override to
  recover. **Exit 1 is the alarm having been sent, not a fault in the check** --
  the unit records that as `SuccessExitStatus=0 1`.

  One caution learned from the 10:30Z firing: `shipped()` reads the *exported
  bundles*, so its verdict changes the moment an export runs. That alarm was
  right when it fired and stale forty minutes later, which is correct
  behaviour, not a flap -- but do not conclude a check was wrong because a
  later run disagrees. Check what the bundle held at the time.
- Alerting is ntfy.sh for the pipeline and Telegram for ops. **William prefers to
  self-host ntfy** — swap `NTFY_URL` when convenient. The Telegram path has been
  fired and confirmed delivered, and **ntfy fired for real on 4 September**
  when the August payroll release landed — both paths are now proven.
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

**`planned.yml` is empty, every release has its vintage history, and nothing
blocks.** The BEA key is in place and PCE shipped on it. What is left is
design.

0. **Design what to draw.** Ingestion is finished and nothing is blocking.
   2,308 series sit in the database at `publish=false`, drawn by nothing. The
   rule for promoting one has not changed -- large by weight, persistently
   volatile, or a direct input to something else that matters -- and the
   mechanics are now a spec-file exercise: name it in `include_series`, or set
   `publish=true`, then give it a panel.

   Two things to weigh when that starts. The CPI and PPI item structures are
   far too big to stack (trap 21 stops at six colours, and a partition is the
   only honest stack, per the settled decisions). And a `fetch_date` series
   must never be offered a revision overlay -- there are now **1,025** of them,
   so check `vintage_mode` rather than assuming, especially anywhere in CPI
   detail, where 267 of 338 categories are BLS-only, and anywhere in PCE, where
   all 210 BEA lines are.

   **The concrete candidate is a labour costs dashboard.** ECI (404 series) and
   Productivity (282) are ingested and drawn by nothing. Quarterly and thin
   apart, together they are unit labour costs -- the wage measure that bears on
   inflation, and the one thing the site discusses without showing. It needs no
   ingestion at all: a spec file and catalogue rows. 45 of the Productivity
   series are dead at source, so check the last observation before putting any
   of them on a panel (traps 28 and 49).

   Still true and worth rechecking as the catalogue grows: each ingest makes
   BLS API calls against a 500/day key limit. Trap 39 cut that from 35 calls
   per run to 7 by fetching only the years not already held, which is what
   made 456 BLS series affordable at all.

1. **Do not self-host ntfy.** Asked and answered, 4 September 2026. The
   alerting exists to say the pipeline broke; running the notifier on the box
   it watches means one machine failing silences both the pipeline and the
   thing that would tell you. Off-box is the right shape for this role and
   ntfy.sh already is, as healthchecks.io is for the dead-man's switch. It
   would also need a Caddy route, which is guardrailed. The real concern —
   an ntfy.sh topic is readable and writable by anyone who learns it — was
   checked rather than assumed: no module builds `FRED_API_KEY` into a URL
   string (it travels in `params`), and the only raised FRED error carries the
   path plus 200 characters of body, so nothing secret transits the topic.
   What does transit it is release ids, series lists and counts, and up to 600
   characters of stderr on failure. If that ever needs narrowing, an
   access-controlled topic is the cheap answer, not a container.

2. **EverOS runs v1.2.3 since 4 September 2026**, bumped from `d3a9f9e`
   (14 July, reporting 1.1.2). 1.1.2 was inside the affected range of
   `GHSA-grm3-hcqf-hm28` — CVSS 8.2, path traversal in knowledge document
   upload, fixed in 1.2.1. It was **not reachable**: 8000 is `expose`d but
   never published to the host, Caddy proxies `everos_mcp:8001` and not
   `everos:8000`, and `mcp_server.py` calls only the four `/api/v1/memory`
   endpoints. Fixed anyway, because the argument for leaving it was an
   argument about the perimeter rather than about the flaw.

   The upgrade is a one-line `ARG EVEROS_REF` in `everos/Dockerfile` plus
   `docker compose -f docker-compose.core.yml build everos` and `up -d`.
   Three things worth keeping:

   - **A host-user `tar` of `everos-data` silently produces a partial
     archive.** The container writes as root, so `strawer` cannot read the
     `_indices`, `_transactions` and `_versions` files; `tar` reports each one
     and exits 2, which is easy to skim past when the tarball exists and looks
     plausible. Snapshot from a root container instead —
     `docker run --rm -v .../everos-data:/data:ro -v ~/backups:/out alpine:3
     tar czf /out/<name>.tar.gz -C / data` — and **count the files both ways**
     before allowing a one-way migration. 79 against 79 is what made it safe.
   - **Dockerfile comments are only comments at the start of a line.** An
     inline `# v1.2.3` after `ARG EVEROS_REF=<sha>` becomes part of the ref.
     Caught before building; it would have failed at `git checkout`.
   - `/api/v1` is a permanent alias from 1.2.0, so the MCP wrapper needed no
     change. Verified after: version 1.2.3, `table_schema_migration_done
     version=2`, 22 markdown files intact, capabilities all true with no
     disabled features (so no `cascade backfill`), cascade healthy, and the
     same search returning the same three episodes on `/api/v1`, on `/api/v2`,
     and through Caddy and the MCP wrapper from outside.

   Upstream `main` is ~12 commits past v1.2.3 and they are almost all
   documentation. The pre-upgrade snapshot is
   `~/backups/everos-data-pre-1.2.3-20260904.tar.gz`; delete it once 1.2.3 has
   run a while.

   The `everos/Dockerfile` change is committed in `~/bigricebowl` but **not
   pushed**: that repo was already one commit ahead with unrelated
   uncommitted deletions, and pushing would have carried someone else's
   unreviewed work with it.

   Separately: the everos tarball in the user crontab (03:15 daily, 14-day
   retention) is **redundant rather than load-bearing** — restic backs up
   `/home/strawer/bigricebowl` whole, `everos-data` included. Worth knowing
   before anybody prunes it thinking it is the only copy.

3. **`pub_lag_days` and `staleness_mode` are now dead columns.** Both were
   the retired stack's way of guessing when data should have arrived. This
   repo answers that with a real forward calendar instead — `--due` reads
   `macro_release_dates`, and `coverage.py` catches a series that has stopped
   publishing. All 182 rows are NULL and nothing reads either column. Drop them
   or leave them, but do not build on them thinking they are wired up.
