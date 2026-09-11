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

**The prose, by value.** Every sentence in the 140 notes that carries a
number -- 147 of them -- was read, and the 45 that state a measurement were
recomputed from `macro_observations_current` or the bundles (the rest are
cross-references, definitions, or figures already documented as measured in
the traps). Thirty-nine reproduce exactly, among them the Beveridge-curve
averages (4.49, 6.88, 4.34), the JOLTS net-flow gap (mean 3.4k, sd 936k over
308 months), the supersector sums (3.0k worst on 5,510k; 1k on 5,715k), the
quits-share extremes (73.3% April 2022, 17.3% April 2020), 70.9% of months
since 1990 clearing ±122,000, the claims revision medians (+1,000 recent,
16,000 and 7.5% at three to five years), the CPI weight ratios, the 8.1%
median peak in April 2023, the PPI cap covering 92% of cells, and the
±122,000 interval against the August technical note. Six did not, and are
fixed:

| Page, table | Said | Measured |
|---|---|---|
| JOLTS 11 | April 2020 bar 15.9m | March 2020, 16.3m (April 11.5m) |
| PCE 8 | saving rate "record low in 2022" | 2.2% June 2022; the record is 1.4%, July 2005 |
| CPI 18 | shelter "thirteen times gasoline" | 35.304 / 3.852 = 9.2 |
| PPI 18 | portfolio management "−20% to +25%" | −14.1% to +33.3% since 2010 |
| PPI 22 | sign agreement 60%, autocorrelation 0.02; 80% and 0.62 | 63% and 0.09; 83% and 0.67, pooled over 2010–2026 |
| Payroll 20 | teen rate three to four times adult "at all times" | 1.75× in April 2020; "in normal times" |

Two counts that drift by one every month -- "66 months since 2021" (CPI 31)
and "139 months since 2015" (PPI 20) -- now name their end dates (trap 59).

### 4.7 The release watch, 10 September: PPI and national claims

- **The 01:40 ET sweep** logged `release dates rc=0` and inserted 0 rows.
- **From 08:35 ET every window named exactly `bls.ppi,eta.claims`**, the
  pair the simulation predicted; `eta.state_claims` correctly waited for
  Friday. Each fetched 217,373 observations and inserted none, because FRED
  had not published: at 09:50 ET `PPIFIS` still ended at July and `ICSA` at
  29 August. The BLS API already had August final demand (`WPSFD4`
  157.411) at 09:46 ET.
- **That lag exposed a defect due to fire on Friday** (trap 65): the gate
  would have called CPI landed from its BLS-API rows alone and stopped
  polling before FRED published the headline. Fixed and deployed at
  09:55 ET, with an atomic rename so no running window could load a partial
  file, and verified against the live module: `releases_due_now()` still
  returned `bls.ppi, eta.claims`.
- **FRED missed the morning entirely.** At 10:34 ET it had updated 17
  series all day, none of them PPI or claims, though the Labor Department's
  claims report was posted at 08:29:59 ET and the BLS API had August PPI.
  The Labor Department's own figures were saved for the cross-check: initial
  claims 206,000 for the week to 5 September, the prior week revised to
  207,000, four-week average 206,000, unadjusted 176,567, continuing claims
  1,774,000 for the week to 29 August, insured rate 1.2%.
- **The release window was extended** to poll every thirty minutes from
  15:25 to 20:55 ET, so a release FRED posts in the afternoon lands the same
  day rather than at the 01:40 sweep. Thirty minutes rather than ten keeps a
  CPI day on which FRED never publishes at 316 BLS API calls of the key's
  500, measured from the archive manifest.
- **Recorded for after Friday's CPI**: use the BLS API as a provisional early
  value for FRED-sourced series in BLS releases, replaced by ALFRED's dated
  vintages exactly as the FRED CSV rows are now. It needs a value-verified
  FRED-to-BLS id map (this audit's reconciliation supplies most of it), the
  backfill clearing BLS provisional rows too, a gate that does not count a
  provisional row as landed, and a stamp that can date a release before
  ALFRED does. Claims cannot use it: they are the Labor Department's.
- **Claims landed on FRED at 11:16 ET**, two hours and 46 minutes after the
  Labor Department, and the 11:25 ET poll took them all the way: 16 rows
  across the nine national series, backfill rc=0 with 16 dated vintages,
  validate 38/38, export, push. The claims bundle reads released
  10 September for the week to 5 September, next 17 September; state claims
  correctly still read 4 September, next 11 September.
- **FRED reproduces the Labor Department exactly**, as stored and as drawn:
  initial claims 206,000, four-week average 206,000, unadjusted 176,567,
  continuing claims 1,774,000, insured rate 1.2%, each on a
  `2026-09-10 00:00` publication vintage. The prior week's revision is
  history, not an overwrite: 206,000 as first printed, 207,000 now.
- **The rewritten gate stood down for claims**: once claims landed it listed
  only `bls.ppi` as outstanding. Clipcheck at both widths, coverage and
  keycheck were clean on the new bundles, and the claims page drew all ten
  charts with the fixed labels.
- **The success alert named the wrong releases.** It read "New data:
  bls.ppi,eta.claims" because it printed the releases polled, not those that
  changed. It now names the releases of the changed series, deployed by
  atomic rename. The PPI bundle's extra series that same export was
  `PPIFID`, added by the forecast work of 9 September, not by the release.
- **The BLS provisional layer is built on branch `bls-provisional`**
  (0dd3406): 324 of 324 drawn FRED series mapped to BLS ids by value, 11 of
  them not what their name suggested, and eighteen scenarios passed in
  rolled-back transactions. Not deployed; the handoff has the order.
- **One transient FRED error failed a whole poll and sent a failure push.**
  At 11:55 ET FRED's CSV endpoint answered HTTP 404, an HTML page, for
  `WPUFD4232` on all four attempts `fred.get_observations_csv` makes over
  about fifteen seconds. `ingest.py` exited 1 on that one series of 640,
  `refresh.py` stopped before validation and pushed "Dashboard refresh
  failed". The 12:05 ET poll fetched the same series normally and finished
  rc=0, so nothing was lost. **Recorded, not changed**: failing loudly is the
  rule here (trap 38), but a push for a fault the next poll clears on its own
  trains the reader to ignore the channel. The middle course is to keep the
  exit code and `status.json` as they are and push only when the same series
  fails on two consecutive polls. Not done mid-release.
- **Reported by William: Tables 7, 8 and 9 on Weekly Claims looked stale.**
  They are current. Tables 2, 3 and 7 end at 29 August because the Labor
  Department publishes continuing claims a week behind initial claims; 8 and
  9 end at 29 August because the 53 state series come in Friday's separate
  state report. What made them look stale is real and site-wide: the engine
  counts date labels from the LEFT edge, so the newest period is almost never
  labelled. Measured in the browser, 159 of the 164 date-axis charts at
  1280px leave their last period unlabelled; on Weekly Claims the last label
  on Tables 2, 3 and 7 is 4 October 2025 for a line ending 29 August 2026,
  and Table 9's newest column is 29 August with its last label 22 August, or
  18 July on a phone. The label-spacing change of 9 September stopped the
  collisions and kept the left anchor, and clipcheck passed because it tests
  collisions, not the end label. **Proposed, not applied until asked**: count
  the label spacing back from the right-hand end in the engine, extend
  `clipcheck.py` to fail any date axis without its last period labelled, and
  optionally say in those headers that they run a week behind initial claims.
- **Fixed at William's request, the same afternoon.** Date labels are now
  spaced back from the newest period, which is right-aligned and always
  labelled; the spacing allows one and a half label widths, because the
  first version allowed one and the overlap rule then dropped the newest
  label on a phone. `clipcheck.py` gained the newest-period test and a
  right-edge overflow test, and was proven on the unfixed engine: 159 charts
  flagged at 1280px, 162 at 430px, 341 problems in all. The right-edge test
  also found six small clips, the breadth charts' "50" marker and the PPI
  heatmap's scale on a phone, fixed by measured placement. The final engine
  passes with 0 problems at both widths. Weekly Claims Tables 2, 3 and 7 now
  say continuing claims are published a week behind initial claims, and
  Tables 8 and 9 that the state report comes the day after the national one,
  so from Thursday to Friday they end a week before Table 1 -- the lags
  measured from first-publication vintages, not assumed.
- **PPI landed on FRED at 12:53 ET and the release failed halfway** (trap
  67). The 12:55 ET poll inserted 2,987 rows and changed 614 series; the
  ALFRED backfill hit FRED's rate limit at `WPUID632` and exited 1, so no
  validation, no export, and a failure push. The 13:10 ET poll stood down,
  calling PPI landed. That poll had also missed `PPIFIS` and `PPIFES`, whose
  CSV still read July. Restored at 13:19 ET: `backfill.py --series
  WPUID632`, then `tools/refresh.sh --releases bls.ppi --force`, which
  inserted the 10 missing rows, backfilled them, validated 38/38, exported,
  and pushed "New data: bls.ppi" -- the alert fix of 31278bc on its first
  real release.
- **FRED reproduces BLS exactly for PPI**: final demand 157.411 for August
  and 156.784 for revised July, unadjusted 157.604 and 157.155, identical on
  the BLS API. The bundle reads released 10 September for August; Tables 1
  and 2 draw and label August; Table 6's weights have re-drifted to August
  prices. Coverage 100%, keycheck 0, clipcheck clean at both widths.
- **Fixed before Friday's CPI**, which changes several hundred series and
  would have hit both faults: FRED calls paced under the limit with 429s
  waited out; releases polled until settled; leftover backfill and a failed
  export retried by the next poll. Deployed at 13:21 ET under the refresh
  lock and proven live: the 13:25 ET poll fetched claims and PPI, inserted
  nothing and logged `settled: bls.ppi, eta.claims`; both calendar rows read
  `settled`; the 13:35 ET poll said "nothing outstanding; not polling".

### 4.8 The release watch, 11 September: CPI and the state claims report

- **State claims landed and settled on the timers alone.** The 08:35 ET
  poll's 262 changed series held no state series. The 08:45 ET poll inserted
  106 rows at 08:48, backfilled 106 vintage rows, validated 38/38, exported
  and pushed "New data: eta.state_claims". The 08:55 ET poll inserted
  nothing and logged `settled: eta.state_claims`. `AKICLAIMS` now ends
  2026-09-05, so Weekly Claims Tables 8 and 9 reach the same week as
  Table 1.
- **The BLS-API CPI detail landed at the embargo; FRED's headline did not.**
  The 08:35 ET poll inserted 262 rows (`CUUR0000SA0`, `CUUR0000SA0L1E`,
  `CUSR0000SETE` and the other BLS-sourced items, all at August), stored no
  vintage rows in the backfill, validated 38/38, exported at 08:37, and
  pushed "New data: bls.cpi". At 09:22 ET FRED's CSV for `CPIAUCSL` still
  ended `2026-07-01,332.813`. The gate kept polling, as trap 65 intends:
  the calendar row stayed `scheduled` because the FRED source had not
  landed.
- **Fixed: the CPI stamp read "August 2026, Released 12 Aug 2026"** from
  08:37 ET, confirmed by screenshot. `ref_period` came from the newest row
  of any source and `released_at` from publication vintages only, so the
  period was August's (BLS API) and the date July's (ALFRED). Per release,
  at 09:21 ET:

  | release | newest row, any source | newest with a publication vintage | released_at |
  |---|---|---|---|
  | `bls.cpi` | 2026-08-01 | 2026-07-01 | 2026-08-12 |
  | the other nine | equal to the next column | | |

  The period now comes from publication vintages too (trap 68). A scratch
  export changed exactly one field across all seven bundles: `bls.cpi`
  `ref_period`, 2026-08-01 to 2026-07-01, carried by the CPI and PCE
  bundles.
- **Fixed: FRED's edge blocked the VPS for bursting the keyless CSV
  endpoint.** Downloads per poll, measured from the archive manifest:

  | poll (ET) | downloads | most in one second | most in ten seconds | outcome |
  |---|---|---|---|---|
  | 08:55 | 305 in 24 s | 23 | 189 | fine |
  | 09:05 | 148, then 403s | 22 | 148 | `ingest rc=1`, 13 series 403, push "Dashboard refresh failed" |
  | 09:15 | 227 | | | recovered: "previous run failed; validating and exporting again", 38/38, export |
  | 09:25 | 140, then 403s | | | `ingest rc=1`, a second false failure push |
  | 09:35, paced | 198 in 2 min 12 s | 3 | 18 | `ingest rc=0`, no 403; re-validated 38/38 and exported, `bls.cpi` `ref_period` 2026-07-01 |

  The error body was FRED's edge page, `You don't have permission to access
  "http://fred.stlouisfed.org/..."`, the first 403 in the log's history. A
  single curl from the box returned 200 at 09:20 ET and 403 at 09:28. The
  CSV path now spaces downloads 0.6 seconds apart (trap 68), proven offline
  with a fake client before install so no test request reached FRED during
  the block. Both files were installed at 09:35:42 ET under the refresh
  lock, the moment the failing 09:25 poll released it.
- **Recorded, not changed: a 403 is retried on the short backoff.** Five
  retries over about 25 seconds cannot outlast a ten-minute block, so each
  blocked series fails and the next poll retries. Treating a 403 like a 429,
  with a 65-second wait, would stretch one blocked run past an hour while
  holding the lock. With the trigger removed and the trap 67 retry
  recovering on the next poll, failing fast is the better trade.
