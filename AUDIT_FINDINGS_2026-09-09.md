# Audit findings — 9 September 2026

Terms of reference: `AUDIT.md`. This session ran as Claude Code on the web,
which **cannot reach the VPS, the site, BLS, BEA or FRED** (SSH has no egress,
and the HTTPS proxy refuses every one of those hosts). So it audited what the
repository holds — the specs, the engine, the pages, the pipeline code, the
docs — and could not audit what only the database holds. Section 3 says
exactly what is left and how to do it. **Nothing was ingested.**

Everything below is on branch `claude/data-bigricebowl-audit-a7bbms` of
`strawer852/dashboards`. Master was left alone so the nightly `dashboards-push`
from the VPS cannot collide with it.

---

## 1. Findings, each fixed or recorded

Numbering continues the trap list: the first five are now traps 56–60 in
`CLAUDE.md`.

### Fixed

1. **`HANDOFF.md` was 15 MB.** The commit that added `AUDIT.md` (c4082ef)
   rewrote the handoff as the "Loose ends" block repeated 228 times; 152 lines
   of real content were gone. Restored from 5e89a13 and refreshed. Whatever
   edited it appended in a loop; `git diff --stat` before committing a doc
   would have caught a +252,000-line change. Trap 56.
2. **Twenty-four legends drew the ink series in grey.** The PCE, Labour Costs
   and CPI Table 32 keys use `<i class="kink">`, which no stylesheet rule
   defines; the swatch inherited `--muted`. Added `.key .kink`. Trap 57.
3. **Heatmap rows rendered bottom-up.** ECharts puts category 0 at the bottom.
   Two panels (PPI Table 10, Labour Costs Table 10) had been listed in reverse
   to compensate; the 33-row PPI Tables 21–22, the payroll supersector and
   sub-sector heatmaps, the JOLTS industry heatmap and the 53-state claims
   heatmap had not, so they read upwards against their own prose. The engine
   now sets `inverse: true` so rows read top-down as listed; the two
   compensated lists were put back in reading order. Trap 58.
4. **Captions quoting the current print.** Fourteen notes carried a figure
   from the July or August 2026 release with no date — "+35,000 in August",
   "led final demand services in July at +6.5%", "energy contributed nearly as
   much as food and core goods combined this month" — every one of which is
   wrong from the next release on. The prose form of traps 18–20. Rewritten
   to state the mechanism; the few figures kept are dated. Trap 59.
5. **Set-valued derived measures aligned inputs by position, not date.**
   `_weighted_rates` (CPI and PCE median and breadth) and
   `share_above_year_ago` (state claims breadth) zipped `v[i]` across series
   whose histories start in different years, contrary to the module's own
   docstring. It gave the right answer only because `truncate_history` had
   cut every input to end on the same period. Now aligned by date on the
   first input's axis; `axis()` also handles weekly and daily series and
   normalises explicit date arrays to the same shape as generated ones (the
   two shapes never matched, so a monthly series with one irregular date
   would have matched nothing). Proven with synthetic inputs of different
   starts: 0 mismatches against an independent by-date computation, 67 months
   different from the old positional answer, identical to it when the inputs
   are aligned. Trap 60.
6. **JOLTS Tables 1, 2 and 5 were titled for series they do not draw.**
   "Openings, hires, quits and layoffs" draws no layoffs; "Quits rate" draws
   quits and layoffs; "Hires against total separations" draws hires, quits and
   layoffs and its note said "the gap between these two lines is the payroll
   change". Titles and notes now describe what is drawn.
7. **Weekly Claims Table 6 sat after Table 10.** Moved to its numbered place.
8. **CPI and PPI source footers sat mid-page** with two and three tables below
   them; PCE and Labour Costs had no footer at all. Footers are now the last
   block on every page, and name the BLS/BEA APIs where the page draws from
   them (the CPI footer said "via FRED" over a page whose median is built
   from BLS-API series).
9. **PPI Table 22's row was opened inside Table 21's cell** (an unclosed div).
10. **JOLTS Table 11 header said "ten years"** over a five-year window that
    the note explains at length.
11. **Payroll retail and transport headers said "latest month"** over 48-month
    heatmaps.
12. **CPI Table 32 said the median is built on 137 items.** The spec lists
    135, summing to 98.52; the spec's own comment said 137 and 99.81. Caption
    and comment corrected. PCE's 210 items summing to 99.658 checked out.
13. **Factual slips in prose.** PCE Table 3: "CPI reweights every two years"
    (annual since 2023) and "PCE reweights every quarter" (it is a chain
    index); Table 2 "lags rents by two years" (a year or more); Table 6 "a
    quarter of the basket has no market transaction" (unverified, removed).
    CPI Table 1 "BLS priced only three items" in October 2025 (trap 22
    measured 20); Table 25 "two of the three series that survived"; Table 30
    "the only panel carrying an unadjusted series" (Tables 31 and 32 do).
    Claims lede and blurb "five weeks ahead of the payroll report" (three to
    four; trap 42).
14. **Legends missing a drawn series.** Payroll Table 1 (3-month average),
    Table 4 (the bars), Table 8 (the bars), Table 27 (weekly earnings in the
    note); PCE Table 3 dashed series unmarked.
15. **Payroll Table 7 had no note**, and its eleven sub-sector panels repeated
    one identical 40-word note. One shared note now carries it.
16. **The line panel's colour ladder stopped at three** and fell back to `s4`
    for every later series, so a fourth, fifth and sixth unnamed series would
    share a colour. Every current page names its colours; fixed anyway.
17. **A static page check now exists**: `tools/keycheck.py` — legend classes
    defined, tables numbered in order, footer last, divs balanced, chart divs
    and panels one-to-one, contents list complete. It fired on 11 findings
    before the fixes and 0 after.

### Recorded, not changed

- **Labour Costs draws 24–25 years** (`window: 96` quarters on ECI panels,
  100 on productivity) where every other page draws five or ten, and its
  headers do not say so. Table 4 leads with the quarterly ECI on purpose,
  sampling monthly earnings at quarter ends — the author's comment accepts
  trap 17's cost. Defensible for a page whose point is the long run; the
  headers should state the window.
- **JOLTS Table 5** could draw the total separations rate (`JTSTSR`) beside
  hires, which is what its old title promised; whether it is in the bundle
  cannot be checked from here. The note now points to Table 7 instead.
- **The claims state heatmap lists states by FRED id**, which is postal-code
  order, so Alaska precedes Alabama and Iowa precedes Idaho. Harmless;
  alphabetical by name would read better.
- **Captions still carry measured historical statistics** (correlations,
  standard deviations, "8.1% in April 2023"). These are stable facts, not
  current prints, and were left; the median's peak date could not be
  verified without the database.
- **PCE Table 14's BEA-side shares** (15.572, 17.217, …) and the "Recreation
  services 3.154" CPI weight are not in any spec and could not be checked.
  The CPI-side figures that are in the spec all reconcile.
- **`export.page_requirements` undercounts by one** for panels whose default
  transform is `diff` (contribution, heatmap) when the word "transform" is
  absent, and cannot see ids in a bare array (`SECTORS`). Neither bites today:
  the affected series are not truncated, and an unseen truncated series is
  refused rather than cut.
- **`share_above_year_ago` keeps an absolute floor of 20 series** where the
  weighted measures use half the weight. With 53 states it is 38%; fine, but
  it is the same class as the `total < 50` floor the audit brief names.

## 2. What was read, area by area

- **D — every table against its caption.** All 140 numbered tables and the
  22 unnumbered sub-panels were read against their panel spec: transform,
  window, periods, format, units header, key order against series order and
  colour slot. Key/series order matched on every stacked and line panel;
  the mismatches found are items 6–14 above. Units headers match the format
  on every panel (`k_units` for persons, `millions` for thousands, `pp` for
  contributions, `pt2` for index-point revisions).
- **E — units.** The two cross-release ratios (claims recipiency, vacancies
  per jobseeker) carry the right scale; nothing else divides across a unit
  gap.
- **F — seasonal adjustment.** `add_series.py` now records the source's own
  short flag (SAAR included); the 210 stored BEA rows themselves need the
  database to confirm.
- **G — the permanent nulls.** Every transform in the engine and every
  derived kind returns null when an endpoint is null; `alignAsOf` lands on
  the published null; `connectNulls` is off unless a panel asks. Nothing
  interpolates. The October 2026 consequence is stated on CPI Table 1.
- **C — derived measures.** Weights: CPI four-way 100.000, core split
  100.000, food/energy/medical/shelter sub-splits 100.000 or 95.075 as
  captioned, twelve items 79.448, seven core items 74.354, PPI five-way
  100.000 — all reproduced from the spec. Completeness floors are shares of
  the weight supplied (the `total < 50` bug is gone). Truncation lookback
  follows `derived_from`. Alignment was the defect (item 5).
- **H — held and not drawn.** From the 6 September state, per release:
  JOLTS 640 of 684, PPI 578 of 639, CPI 293 of 469, ECI 402 of 404,
  Employment Situation 159 of 297, Productivity 280 of 282, BEA 3 of 235,
  claims 56 of 115 are `publish=false`. That is deliberate under the publish
  column; 74 are dead at source and none reaches a panel. No promotion is
  proposed here — the rule (large by weight, persistently volatile, a direct
  input to something that matters) needs the data to apply.
- **I — presentation.** Every page rendered at 1400px and 430px in Chromium
  against synthetic bundles: 169 charts drew, none empty, no panel errors, no
  horizontal scroll. That checks layout, legends and orientation, not
  values; `shoot.py` and `clipcheck.py` on the VPS still have to run over the
  real bundles.
- **Landing page.** Generated blocks untouched by hand; the map's covered
  territory now links to the region's own page rather than an anchor, and so
  does the index heading. The `.idx` row styles moved to the shared
  stylesheet so the landing index and region pages are one component.
- **Region pages (new).** `tools/build_nav.py` now writes
  `site/<prefix>/index.html` for every region with a live dashboard
  (`/us/` today), whole, from the specs: masthead, dashboard count, agencies,
  the dashboards by topic with each release's own freshness, under the rail
  with that region open. Breadcrumbs on every dashboard link back to it.
  Adding a country's first spec creates its page.

## 3. Not done here, and how to do it on the VPS

Run Claude Code **on the VPS** (`ssh strawer@bigricebowl.cloud`, `cd
~/dashboards`), not on the web: the web session has no route to anything
this audit needs.

```bash
cd ~/dashboards
git fetch origin && git checkout claude/data-bigricebowl-audit-a7bbms   # review, then merge to master
set -a && . .env && set +a
./venv/bin/python -m macro.validate                  # must still be 37/37
./venv/bin/python macro/refresh.py --force           # re-export: derived.py changed
./venv/bin/python tools/coverage.py                  # must still be 100%
python3 tools/keycheck.py                            # static page checks, new
~/.venvs/shot/bin/python tools/clipcheck.py          # real render
~/.venvs/shot/bin/python tools/shoot.py --path us/inflation/ppi   # look at Tables 21-22 top-down
```

Then, in the order `AUDIT.md` gives:

- **A. Reconcile against the news releases.** CPI Table 1 and Table 2 (338
  categories), PPI Table 1 (relative importances 29.028 + 68.338 + 2.634),
  PCE Table 2.4.5U (210 lines), Productivity and Costs, ECI. Method that
  worked for the 174 payroll ids: verify every id by reproducing the
  published figure, never by title.
- **B. Vintages.** Confirm each of the 1,025 `fetch_date` series is a source
  with no vintages; `from_row` on a single vintage still 0; spot-check July
  2026 payrolls −23,000 → +21,000 in the archive.
- **Watch 10 and 11 September.** `logs/refresh.log`: `refresh start
  (bls.ppi,eta.claims)` after 08:35 ET Thursday, `validate rc=0`, `export`,
  ntfy; CPI Friday. Then look at the pages. Note the CPI page's Table 11 and
  the PPI page's notes no longer describe July, so nothing in prose needs
  retyping.

---

## 4. Second half, on the VPS, 9 September

Run as Claude Code on the VPS with the merged branch on master. Nothing was
ingested. Every figure below was read from the database or the agency's
own table; the raw runs are in `tools/reconcile.py`'s output and the
scripts under `tools/research/`.

### 4.1 The merge proved (section 1 of `NEXT_SESSION_2026-09-09.md`)

| Check | Result |
|---|---|
| `validate.py` before and after the re-export | 37/37, then 38/38 once `eta.state_claims` existed |
| `refresh.py --force` | ingest 1,203,129 observations, 0 inserted; validate rc=0; export rc=0 |
| `coverage.py` | 100% on all seven |
| `keycheck.py` | 7 pages, 0 findings |
| `build_nav.py --check` | 0 pages would change |
| `clipcheck.py` on the real bundles | no label overflows, every in-page link resolves, 3 deliberate flat panels |
| `shoot.py`, all seven pages and `/us/` | 176 charts, 0 suspicious |
| `staleness.py` | 74 overdue, 0 actionable, 74 dead at source |

Looked at, not just counted: PPI Tables 21 and 22 read top-down from
consumer foods to construction; payroll Table 6 runs mining to government;
claims Table 9 starts at Alaska; the PCE Table 3 and Labour Costs keys draw
the ink series in ink; `/us/` renders with the rail open on United States
and the map's United States links to it.

**The derived comparison was not zero, and the handoff's prediction was
wrong.** Against the bundles from the 6th:

| Series | Months changed | Example |
|---|---|---|
| `CPI.median` | 30 of 180 | Aug 2016: 2.529 → 2.787 |
| `CPI.share_above3` | 164 of 180 | Apr 2023: 76.024 → 73.875 |
| `PCE.median`, `PCE.share_above3`, `STATE.ic_breadth`, everything else | 0 | |

Three of the 135 CPI inputs end early -- `CUUR0000SS53031` intracity mass
transit at April 2026, `CUUR0000SSFV031A` food at elementary and secondary
schools at May with April missing, `CUUR0000SEMC04` other medical
professionals at June with gaps -- confirmed against the BLS API directly.
Truncated to their last 180 observations they ended one to three months
before the other 132, so by position they were a different month. An
independent by-date computation from `macro_observations_current` agrees
with the **new** bundle in all 168 months. The first two are sparse
children of monthly Table 2 rows that carry the same weight (0.355 and
0.064), and the spec now uses the parents, `CUUR0000SETG03` and
`CUUR0000SEFV03`; that moved the median in 3 months (max 0.17) and the
breadth in 57 (max 0.39), and the independent computation agrees again in
all 168. Trap 60 carries it. The 10 inputs with no published relative
importance are all exact residuals: nine single unpriced children carrying
their parent's weight, and other medical professionals = professional
services 3.408 − (1.660 + 0.917 + 0.317) = 0.514.

### 4.2 Area A -- reconciled against the news releases, by value

bls.gov refuses the VPS on every route (trap 62), so the tables came from
the Wayback Machine at full fidelity, snapshots of 19 August to 8 September.
Method: `tools/reconcile.py`, which reads every series in the release as of
the vintage that published the table and matches each printed row to the
series that reproduce every one of its figures (percent changes recomputed
from stored indexes, tolerance 0.051; index levels to three decimals). The
expected id comes from the agency's own code (`cu.item`; the group and
item codes PPI prints), so a held series that does not reproduce its row
is reported as `VALUE!`.

| Release, table(s) | Rows reproduced | VALUE! | Not held |
|---|---|---|---|
| CPI Tables 1, 2 (338 categories), 3 | 513 | 0 | 39, all FRED-mnemonic aliases (`CPIAUCSL` = `CUSR0000SA0`, …) or Table 3 special aggregates never catalogued |
| PPI Tables 1 and 3 (323 groupings each) | 897 | 0 | 30: the 10 headline groupings SA are held as `PPIFIS`, `PPIDGS`, … and reproduce; their 10 NSA counterparts (`WPUFD4`…, on FRED as `PPIFID`) are not held |
| ECI Tables 1-13 | 385 | 0 | 9 SA rows of Tables 1-3 (civilian service occupations, civilian construction, state and local W&S and benefits totals, …) exist on FRED only under the 13 `ECI…` mnemonic aliases, none catalogued; 17 MULTI are civilian = private identities and `ECIALLCIV` = `CIS1010000000000I` |
| Productivity Tables 1-6 | 132 columns, every one to a unique series | 0 | none; Tables 1-5 as of 2 September (the 6 August preliminary), Table 6 as of 8 September (the 3 September revision) |

PCE against the BEA API: the 210 July 2026 price levels in the database
equal the API's; all 210 median weights are July 2026 nominal shares of
`DPCERC` to five decimals, 205 under `…RC` codes and five (`IA001081`,
`IA001083`, `IA000630`, `IA000233`, `IA000232`) under BEA's `LA…` lines;
the page's Table 14 BEA-side shares are `DHSGRC` 15.572, `DHLCRC` 17.217,
`DFXARC`+`DFSARC` 14.104, `DNRGRC` 3.822, `DRCARC` 3.945, `DCLORC` 2.695,
`DPCCRC` 89.119, all July 2026. CPI spec weights: 246 checked against the
published relative importances, 0 mismatches; "Recreation services 3.154"
is Table 2's figure. Three DB titles differ cosmetically from BEA's
(`DNPHRG`, `DNPNRG` apostrophes; `DCHCRG` "Market-based PCE child care").

### 4.3 Area B -- vintages

- `from_row` series on a single vintage: **0**.
- `PAYEMS` July 2026: 158,858 at vintage 2026-08-07, 158,913 at 2026-09-04.
- **All 359 FRED `fetch_date` series have ALFRED histories** (trap 63):
  87 CPI (145-184 vintage dates, from April 2011), 271 ECI (46-48, from
  October 2014), `WPUID621` (138). Each held exactly one provisional
  `fred_csv` row per observation, because `backfill.py` had called them
  vintage-less on a test -- one row per observation -- that a never-revised
  series also passes. **Backfilled the same afternoon** at William's
  request: 89,711 observations replaced by 89,994 ALFRED rows (the 283
  extra are `WPUID621`'s revisions; the other 358 never revise and gained
  publication dates only), 4 rate-limited and re-run, 0 still provisional,
  all 359 set to `from_row`. Proof the dates matter: `reconcile.py cpi
  --asof 2026-08-12` now reproduces the 185 FRED-held rows of Tables 1-2,
  and `--asof 2026-08-11`, the day before publication, reproduces none.
  Validate 38/38; every bundle's values and stamps unchanged; the CPI
  bundle grew 23 KB as 27 series gained revision metadata no panel draws.
  The list stays in `tools/research/unbackfilled_fred_2026-09-09.txt` as
  the record.

### 4.4 Fixed

1. **Claims were one release spanning two FRED releases** (trap 61). The
   stamp read "released 4 Sep" for the 3 September report, and the calendar
   was filling with Fridays from `AKCCLAIMS`. All 115 series were asked
   their FRED release: 106 in 469, 9 in 180. `eta.state_claims` created;
   the 106 moved; the spec draws both; the 33 stale future rows deleted and
   re-synced (16 Thursdays plus the 25 November Wednesday for national, 16
   Fridays for state). `release_dates.py` now probes two series per
   release and stores both calendars, loudly, if they disagree. Simulated
   `--due`: Thursday polls `bls.ppi` and `eta.claims`; Friday `bls.cpi` and
   `eta.state_claims`.
2. The two sparse CPI median inputs replaced by their Table 2 parents
   (4.1); `publish` flipped accordingly; the "137 inputs" and "14 residuals"
   comments corrected to 135 and 10.
3. PCE Table 14 "Excluded from core" CPI side 20.955 → 20.953 (100 − 79.047).
4. Claims Table 9 labels "the District of Columbia" and "the U.S. Virgin
   Islands" lose their article.
5. `tools/reconcile.py` added and documented in `CLAUDE.md`.
6. `backfill.py` classifies a series as vintage-less only when its ALFRED
   response carries a single distinct `realtime_start`, and the 359 series
   it had skipped are backfilled and on `from_row` (4.3).

### 4.5 Recorded, not changed

- **CPI Table 1 and PPI Table 1 draw the twelve-month change from the
  seasonally adjusted index** (`CPIAUCSL`, `PPIFIS`), and their headers say
  s.a. BLS's headline twelve-month figure is unadjusted: July 2026 CPI reads
  3.30 from `CPIAUCSL` where the release prints 3.4 from `CPIAUCNS`
  (3.36); PPI 4.66 against 4.7. A reader comparing the page with the news
  will see a different number about one month in three. Arguable: the
  caption is honest and FRED's own charts do the same. Switching Table 1 to
  `CPIAUCNS`/`CUUR0000SA0L1E` (both held) would match the release; PPI
  would need `PPIFID`, not catalogued.
- **Nine SA rows of ECI Tables 1-3 and the ten NSA PPI headline groupings
  are not held**; none is drawn. Adding them is an ingest.
- The three lagging CPI items stay `publish=false` and out of every
  measure; `SEMC04` stays in the median as the only representation of its
  residual, with gaps handled by date.
- Everything in section 1's "Recorded, not changed" stands.

### 4.6 Area I -- every page looked at, at 1280px and 430px

Every one of the 140 numbered tables (and the JOLTS small multiples) was
rendered from the real bundles at 1280px and looked at as its own image;
every page, the landing page and `/us/` were rendered whole at 430px, none
scrolls horizontally, and the first four tables of each were looked at.

- **Axis labels collided, and no check saw it.** On the weekly claims axes
  in half-width cells (Tables 2 and 3) and over ten years (Tables 8 and 10)
  the date labels ran into each other at desktop width; at 430px nearly
  every panel did -- ten-year monthly, four-year monthly, 25-year quarterly
  -- because `tick`, the ECharts label interval, is a per-panel constant
  chosen for a desktop cell. Fixed in the engine three ways (trap 64):
  `hideOverlap` on every axis; the interval computed at render as the
  smallest multiple of the page's `tick` whose labels, measured with
  `measureText` in the axis font, fit the chart's actual width with a gap;
  and rendering deferred until the webfonts are in, since ECharts had been
  measuring the fallback monospace and drawing JetBrains Mono. The four
  claims panels also got a sane desktop interval. `clipcheck.py` now
  measures label collision at both widths, counting touching labels as
  colliding, and was proven to fire on the old claims Table 2 (7 pairs) and
  go quiet after.
- **A quarterly reference period read "April 2026"** on the Labour Costs
  stamp, the landing index and the region page: the formatter had monthly
  and weekly branches only (trap 52's shape). Now "2026 Q2" in all three.
- **Payroll Table 21** draws prime-age participation in the muted grey by
  design (`color: "muted"`, a reference line; the same device on Tables 1
  and 31). Recorded as deliberate.
- **Payroll Table 28**'s title wraps under its number in a half-width cell.
  Cosmetic; left.
- Nothing else. Every key matches its lines, every stack is a partition
  with the total drawn over it, every rebased index starts at 100, every
  October 2025 gap shows as a gap, and every heatmap reads top-down.

