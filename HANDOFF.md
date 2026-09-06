# Handoff — 6 September 2026, end of day

**Read `CLAUDE.md` first.** It is the authority: 43 traps, the settled
decisions, the running state, the guardrails. This file is only the part that
would be stale by the time you read it. Where they disagree, CLAUDE.md is right
and this file is old.

Everything lives on the VPS: `ssh strawer@bigricebowl.cloud`, then
`~/dashboards`. Nothing of substance is on the laptop.

---

## Where it stands

**2,891 series across 8 releases, ~3,130,000 vintage rows over ~1,189,000
observations, 36/36 validations, 100% coverage on all five dashboards, and no
label overflowing its chart.**

| Release | Drawn | Held | Bundle |
|---|---|---|---|
| `bls.employment_situation` | 138 | 297 | 964 KB |
| `bls.cpi` | 178 | 469 | 1,060 KB |
| `eta.claims` | 59 | 115 | 791 KB |
| `bls.ppi` | 61 | 639 | 222 KB |
| `bls.jolts` | 44 | 684 | 171 KB |
| `bls.eci` | 2 | 404 | — no dashboard |
| `bls.productivity` | 2 | 282 | — no dashboard |
| `frb.wage_tracker` | 1 | 1 | — |

Every release is complete at the level its news release publishes. **815 series
carry `vintage_mode='fetch_date'`** and have no revision history — 312
BLS-sourced plus 503 FRED series ALFRED holds no vintages for. None of them may
ever be offered a revision overlay; check the column rather than assuming.

**There is now a browser on the box.** `tools/shoot.py` screenshots a page from
inside the docker network, where Authelia is not in the way, and reports what
each chart actually drew. `tools/clipcheck.py` asks whether any label overflows
its chart. Both found real defects on their first run. Use them; four green
checks have passed over an empty chart before.

---

## The one thing to watch

**Thursday 10 and Friday 11 September.** PPI and claims land on the same day,
then CPI. This is the first release since a great deal changed, and it
exercises all of it at once: BLS series reaching ingest on a release day at
all (trap 35), the year-window change across 312 BLS series (trap 39),
`truncate_history` in a real export, and six new derived measures.

What good looks like in `logs/refresh.log`: `refresh start (bls.ppi,eta.claims)`
after 08:35 ET, `BLS: ... series from <a recent year>` rather than 1939,
`validate rc=0`, `export`, an ntfy push — and the following windows saying
nothing outstanding rather than refetching.

Then **look at the pages**, which is no longer difficult.

---

## The open decision

**PCE as dashboard #6.** FRED release 54, *Personal Income and Outlays*: 144
monthly series with a forward calendar, so it needs a calendar row and nothing
else. The site has CPI and PPI but not the measure the Fed targets, and the PPI
page already explains which producer prices feed it while pointing at nothing.

Two things to know before starting. FRED's 144 series give a headline and
composition dashboard, **not a distributional one** — PCE's ~200 NIPA item
categories live in BEA's tables, so the CPI median does not transfer without
the BEA key. And **ECI and Productivity are already ingested and undrawn**;
they are quarterly and thin alone, but together they are unit labour costs,
which is the wage measure that bears on inflation. That is a more coherent
dashboard than either separately.

---

## Loose ends, none blocking

- **7 commits unpushed**; `dashboards-push` runs at 23:30 and verifies by hash.
- **66 series are dead at source** — 45 Productivity, 19 PPI, 2 ECI —
  confirmed against the BLS API, not just against FRED. Nothing to recover.
- **CLAUDE.md's claim that intermediate demand carries no weights is too
  strong.** PPI Table 1 publishes relative importances for ID5 (147 rows) and
  ID6 (55); what is true is that they are shares of their own group rather than
  of a common total, so they cannot be pooled.
- **PPI has no distributional measure and should not get one.** Table 1 is the
  only PPI table with weights, and its finest split of final demand leaves a
  single 34% leaf. Table 23 counts components instead.
- **`~/bigricebowl` still has an unpushed commit** (`5995cf5`, the EverOS pin)
  plus older uncommitted deletions that are not mine.
- **The dead-man's switch `/fail` path is still unproven.**
- **`pub_lag_days` and `staleness_mode`** remain columns with no consumer.
- **The one-off scripts are in `~/ingest_run/`** with their logs.

---

## What the 5th and 6th did

Ingestion went from 183 series to 2,891 and every dashboard gained depth.

- **The establishment survey completed** — all 174 Table B-1 industries plus
  B-2 hours and B-3 earnings, each id verified against the published August
  figure before ingestion.
- **CPI, PPI, JOLTS, ECI and Productivity completed** — 2,250 series, including
  all 338 CPI Table 2 categories, and later 144 JOLTS series FRED does not
  carry at all.
- **Six new derived measures**: a weighted median and a breadth measure for
  CPI, a counted breadth for PPI, state breadth and distance-off-the-low for
  claims, and the arity and weighting machinery to express them.
- **Depth on every page**: payroll sub-sectors under Table 7, JOLTS by industry
  and region, state-level claims, CPI's median, PPI's component heatmaps.

The recurring shape, and the reason so much of this file is about verification:
**every defect this session was found by comparing the thing against its
source, or by looking at it.** Validation passed 36/36 while 28 series had no
revision history, six ECI series were eight years stale, a breadth line lost
eight of its ten years, and a chart's numbers were wrong by a factor of a
thousand. None of those moved a single check.
