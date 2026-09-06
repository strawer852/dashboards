# Handoff — 6 September 2026, end of day

**Read `CLAUDE.md` first.** It is the authority: 49 traps, the settled
decisions, the running state, the guardrails. This file is only the part that
would be stale by the time you read it. Where they disagree, CLAUDE.md is right
and this file is old.

Everything lives on the VPS: `ssh strawer@bigricebowl.cloud`, then
`~/dashboards`. Nothing of substance is on the laptop.

---

## Where it stands

**3,126 series across 9 releases and three sources, 3,442,990 vintage rows over
1,367,052 observations spanning 1913 to August 2026, 37/37 validations, 100%
coverage on all six dashboards, and no label overflowing its chart.**

| Release | Published | Held | Bundle |
|---|---|---|---|
| `bls.employment_situation` | 138 | 297 | 964 KB |
| `bls.cpi` | 176 | 469 | 1,052 KB |
| `eta.claims` | 59 | 115 | 791 KB |
| `bea.personal_income` | 232 | 235 | 586 KB |
| `bls.ppi` | 61 | 639 | 222 KB |
| `bls.jolts` | 44 | 684 | 171 KB |
| `bls.eci` | 2 | 404 | — no dashboard |
| `bls.productivity` | 2 | 282 | — no dashboard |
| `frb.wage_tracker` | 1 | 1 | — |

Every release is complete at the level its news release publishes. **1,025
series carry `vintage_mode='fetch_date'`** and have no revision history — 456
BLS-sourced, 210 BEA-sourced, and 359 FRED series ALFRED holds no vintages for.
None of them may ever be offered a revision overlay; check the column rather
than assuming.

**PCE shipped as dashboard #6**, 15 tables, including a median built from BEA's
210 underlying-detail lines and a `compare` panel showing why the two indexes
disagree: shelter is 35% of the CPI and 16% of PCE, health care the reverse.

---

## The one thing to watch

**Thursday 10 and Friday 11 September.** PPI and claims land together, then CPI.
This is the first release since a great deal changed and it exercises all of it
at once: BLS series reaching ingest on a release day at all (trap 35), the
year-window change across 456 BLS series (trap 39), `truncate_history` in a real
export, and six derived measures.

What good looks like in `logs/refresh.log`: `refresh start (bls.ppi,eta.claims)`
after 08:35 ET, `BLS: ... series from <a recent year>` rather than 1939,
`validate rc=0`, `export`, an ntfy push — and the following windows saying
nothing outstanding rather than refetching.

Then **look at the pages**. `tools/shoot.py` screenshots from inside the docker
network, where Authelia is not in the way, and reports what each chart actually
drew; `tools/clipcheck.py` asks whether any label overflows and whether every
in-page link resolves. Both found real defects on their first run. Four green
checks have passed over an empty chart before.

**30 September is the first BEA release through the pipeline**, and the one to
watch after that. PCE is fed by two sources — the headline from FRED, the 210
detail lines from BEA — so it can be half updated with every check green. That
is what `source_split` in `tools/staleness.py` now watches for.

---

## October 2025 is permanently empty, and that is settled

The federal shutdown that began 1 October 2025 stopped field collection, and BLS
has said the October reference period will not be collected retroactively. The
data shows exactly the shape that implies, and it will never fill:

- **All 59 household-survey series lost October** — unemployment rate,
  participation, U-6 — in a series continuous since January 1948.
- **439 of 469 monthly CPI series lost it**; 20 were priced from administrative
  sources that needed no field visit.
- **201 of 202 establishment series kept it.** `PAYEMS` reads 158,408, because
  employer records were filed electronically and BLS merged October into
  November's report.

The rule worth carrying: **a survey that had to be taken during the month is
gone; a record that could be collected later survived.** It even explains the
one establishment casualty, real average hourly earnings, which is deflated by a
CPI that does not exist for October.

Nothing needs fixing — the transforms return null when either endpoint is null,
and the bundle's dense `start`/`step` encoding keeps the hole as a null slot
rather than a dropped month. Two things follow anyway: never treat that month as
late, and expect the gap again in **October 2026**, next month, when the hole
becomes the *base* of the twelve-month change rather than the current value.
Traps 4 and 22 carry the detail.

---

## The open decision

**A labour costs dashboard.** ECI (404 series) and Productivity (282) are
already ingested and drawn by nothing. Quarterly and thin apart, together they
are unit labour costs — the wage measure that bears on inflation, and the one
thing the site discusses without showing. **Zero ingestion required**; it is a
spec file and catalogue rows. 45 of the Productivity series are dead at source,
so check the last observation before putting any of them on a panel (trap 28).

---

## Loose ends, none blocking

- **Commits sit unpushed until 23:30**, when `dashboards-push` runs and
  verifies by hash. A count was written here twice and was stale within the
  hour both times; `git log --oneline @{u}..HEAD` is the answer.
- **74 series are dead at source** — 45 Productivity, 23 PPI, 4 CPI, 2 ECI —
  confirmed against the BLS API, not just against FRED. Nothing to recover. The
  4 CPI ones (household operations, legal services) stopped during 2024 and read
  as current until the freshness check stopped counting null rows (trap 49).
- **`frb.wage_tracker` has no rows in `macro_release_dates`**, so `--due` never
  fires for it; it refreshes only on the 01:40 sweep. One series, so it has not
  mattered, but it is a gap in a mechanism that is otherwise complete.
- **`fmtFor` falls back silently on an unknown format name** where `derive`
  throws on an unknown transform. Trap 46. Making it throw is a five-line change
  and would have caught `pct1` immediately.
- **`pub_lag_days` and `staleness_mode`** remain columns with no consumer.
- **The dead-man's switch `/fail` path is still unproven.**
- **`~/bigricebowl` still has an unpushed commit** (`5995cf5`, the EverOS pin)
  plus older uncommitted deletions that are not mine.
- **The one-off scripts are in `~/ingest_run/`** with their logs.

---

## What the 5th and 6th did

Ingestion went from 183 series to 3,126, a third source was added, and every
dashboard gained depth.

- **The establishment survey completed** — all 174 Table B-1 industries plus
  B-2 hours and B-3 earnings, each id verified against the published August
  figure before ingestion.
- **CPI, PPI, JOLTS, ECI and Productivity completed** — including all 338 CPI
  Table 2 categories and 144 JOLTS series FRED does not carry at all.
- **BEA became the third source** — a new client with the 100 MB/minute limit
  enforced at the client layer, and 210 PCE underlying-detail lines whose
  hierarchy had to be read from BEA's indented workbook because it is not
  recoverable from the numbers (trap 44).
- **PCE shipped**, and with it `PANELS.compare`, which exists because the engine
  could draw a series and nothing else — a composition has no time axis
  (trap 48).
- **Six derived measures**: a weighted median and a breadth measure for CPI, a
  counted breadth for PPI, state breadth and distance-off-the-low for claims,
  and the arity and weighting machinery to express them.
- **`refresh.py` had never refreshed a BLS series** — `series_for()` filtered
  `WHERE source='fred'` in both branches, so 37 series were scheduled and
  silently skipped. That is the single most consequential fix of the two days.
- **The `publish` column** separated what the database holds from what a page
  draws, which is what lets 2,308 series be kept for analysis without any of
  them reaching a bundle.

The recurring shape, and the reason so much of this file is about verification:
**every defect across these two days was found by comparing the thing against
its source, or by looking at it.** Validation passed 36/36 while 28 series had
no revision history, six ECI series were eight years stale, a breadth line lost
eight of its ten years, and a chart's numbers were wrong by a factor of a
thousand. None of those moved a single check. The last one of the two days fits
the pattern exactly: a freshness check that read the last *row* instead of the
last *value* reported twelve dead series as current, and reported four live ones
as fixable against a date that was itself an empty row.
