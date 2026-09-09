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
