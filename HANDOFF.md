# Handoff — 5 September 2026, end of day

**Read `CLAUDE.md` first.** It is the authority: 39 traps, the settled
decisions, the running state, the guardrails. This file is only the part that
would be stale by the time you read it. Nothing here overrides CLAUDE.md; where
they disagree, CLAUDE.md is right and this file is old.

Everything lives on the VPS: `ssh strawer@bigricebowl.cloud`, then
`~/dashboards`. Nothing of substance is on the laptop.

---

## Where it stands

**2,641 series across 8 releases, ~2,851,000 vintage rows over ~919,000
observations, 36/36 validations, and 100% coverage on all five dashboards.**

Every release is now complete at the level its news release publishes it, and
what is held is deliberately separated from what is drawn:

| Release | Published | Analysis-only | Total |
|---|---|---|---|
| `bls.ppi` | 28 | 611 | 639 |
| `bls.jolts` | 12 | 528 | 540 |
| `bls.cpi` | 40 | 429 | 469 |
| `bls.eci` | 2 | 402 | 404 |
| `bls.employment_situation` | 92 | 205 | 297 |
| `bls.productivity` | 2 | 280 | 282 |
| `eta.claims` | 6 | 3 | 9 |
| `frb.wage_tracker` | 1 | 0 | 1 |

**No dashboard changed.** All five bundles are the size they were before any of
this, because 2,344 series carry `publish=false`.

**Ingestion is automatic for all of it.** Seven of eight releases have forward
calendar rows and `macro-refresh-due` resolves per release; the Atlanta Fed
tracker correctly has none and rides the 01:40 sweep. Trap 35 was fixed
earlier today, so every source — BLS included — now reaches ingest.

Next firings worth watching: **PPI and claims on 10 September** (two releases in
one day, the case the old grouped gate would have mishandled) and **CPI on
11 September**, which will be the first release to exercise 304 BLS-sourced
series through the new year-window logic.

---

## The one thing to do next

**Design what to draw.** Nothing is blocking. Promoting a series is a spec-file
exercise — name it in `include_series`, or set `publish=true` — and the rule
for deserving a panel is unchanged: large by weight, persistently volatile, or
a direct input to something else that matters.

Two cautions before that starts:

- **The CPI and PPI item structures are far too big to stack.** Trap 21 stops
  the categorical palette at six, and a stack is only honest for a partition.
- **665 series have no vintage history** and carry `vintage_mode='fetch_date'`.
  None of them may be offered a revision overlay. Check the column rather than
  assuming, especially in CPI detail, where 267 of 338 categories are BLS-only.

---

## Loose ends, none blocking

- **66 analysis-only series are dead at source** — 45 Productivity, 19 PPI,
  2 ECI — confirmed against the BLS API rather than only against FRED. What is
  held for them is the complete history; there is nothing to recover. None is
  drawn, but check the last observation before building a panel on any.
- **Eight that looked identical were not dead, and are fixed.** FRED had
  silently stopped updating them while BLS kept publishing: six ECI series were
  stuck at October 2017 against BLS's April 2026, nearly nine years missing,
  plus two CPI series a year behind. They are now `source='bls'`, and the two
  sources agree to within 0.1 index point where they overlap. See trap 40 —
  the check is to ask the other source, because "FRED agrees with us" answers
  a different question from "this series is current".
- **PPI commodity detail is not ingested.** The FD-ID system is complete, but
  FRED carries 12,323 PPI series in total against the 639 held. The same is
  true of CPI's regional and city-level series (4,609 on FRED, 469 held). Both
  are a repeat of the same pass if ever wanted.
- **Production and non-supervisory workers** (Employment Situation Tables B-5
  to B-8) and the **NSA counterparts** of Table B-1 are still not ingested.
- **The one-off scripts are in `~/ingest_run/`** with their logs. Nothing in
  the repo depends on them.
- **Everything is uncommitted.** `dashboards-push` pushes only committed work —
  it logs "working tree is dirty" and moves on. The 03:00 restic backup covers
  the working tree, so nothing is at risk of loss, only of being absent from
  the repository history. Changed: `macro/export.py`, `macro/ingest.py`,
  `macro/add_series.py`, `macro/refresh.py`, `macro/schema.sql`, `CLAUDE.md`,
  `HANDOFF.md`, plus a `publish` column added to `macro_series_meta`.
- **`~/bigricebowl` still has an unpushed commit** (`5995cf5`, the EverOS pin)
  and, from before, `10e2850` plus uncommitted deletions that are not mine.
- **The dead-man's switch `/fail` path is still unproven.**
- **`pub_lag_days` and `staleness_mode`** remain columns with no consumer.

---

## What this session did

- **Completed the establishment survey** — all 174 Table B-1 industries plus
  B-2 hours and B-3 earnings, 205 series, every id verified against the
  published August figure before ingestion.
- **Completed CPI, PPI, JOLTS, ECI and Productivity** — 2,250 further series,
  including all 338 CPI Table 2 categories with none unmapped.
- **Fixed trap 35** — the orchestrator had never passed a BLS series to ingest.
  Verified through the archive manifest, because the data was already current
  and no row could prove a fetch had happened.
- **Fixed 28 series that had never been backfilled** and were sitting on
  provisional rows despite ALFRED holding real history for them.
- **Added the `publish` column** (trap 37), which is what let the database grow
  seven-fold without a single byte reaching a page.
- **Cut BLS API usage from 35 calls per run to 7** (trap 39), without which
  304 BLS series would have risked the 500/day cap on a release morning.
- **Made `ingest.py` refuse an uncatalogued id** (trap 38) after a warning that
  did not change an exit code hid a nine-series hole behind RC=0.

The recurring shape, unchanged: **every one of these was found by comparing the
thing against its source.** The big ingest returned RC=0 on the step that had
silently dropped nine series, and it was `validate.py`'s structural check —
not the run's own report — that gave it away.
