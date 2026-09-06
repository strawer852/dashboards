# Audit — terms of reference

Written 6 September 2026, for a session that will review the whole of
data.bigricebowl.cloud before any new country is ingested.

**Read `CLAUDE.md` first** — 55 traps, the settled decisions, the guardrails —
then `HANDOFF.md` for the running state. This file is neither: it is what to
check, why, and what a failure looks like.

---

## The premise

**Everything is green right now, and that is the reason for the audit.**

```
validate      37/37 checks passed
coverage      100% on all seven dashboards
clipcheck     no label overflows, every in-page link resolves
staleness     74 overdue, 0 actionable, 74 dead at source
shoot         161 charts, 0 suspicious
```

Across 5–6 September roughly fifteen real defects were found **while every one
of those checks was passing**: 37 series the scheduler had never once
refreshed, 28 series with no revision history, six ECI series eight years
stale, a breadth line that had silently lost eight of its ten years, a chart
wrong by a factor of a thousand, a page advertising a dashboard that shipped
three days earlier, and a title reading DISCONTINUED over a live series.

Every single one was found by **comparing the thing against its source, or by
looking at it**. Not one moved a check.

So the audit's job is not to run the checks. It is to do the things the checks
cannot do.

---

## What the system holds

| | |
|---|---|
| Series | **3,126** across **9 releases**, **3 sources** |
| By source | 2,460 FRED · 456 BLS · 210 BEA |
| Observations | 1,367,052, spanning **1913-01-01 → 2026-08-29** |
| Vintage rows | 3,442,990 |
| Revision history | **2,101 series have it. 1,025 do not** (`vintage_mode='fetch_date'`) |
| Published | 715 marked `publish`; bundles draw 818 including derived |
| Held for analysis | 2,411 drawn by nothing |
| Dashboards | 7, **140 numbered tables** |
| Dead at source | 74 — 45 Productivity, 23 PPI, 4 CPI, 2 ECI |

Dashboards: Nonfarm Payroll (33 tables), CPI (33), PPI (23), PCE (15),
Labour Costs (15), JOLTS (11), Weekly Claims (10).

---

## The audit, in priority order

### A. Reconcile against the published news release — **do this first**

The single highest-value check, and the one nothing automated does. Take a
release's actual PDF or HTML from the agency, and confirm the database
reproduces its headline table.

- Payroll: BLS Employment Situation Table B-1 — all 174 industries.
- CPI: news release Table 1 and Table 2 — 338 categories.
- PPI: Table 1 relative importances (goods 29.028 + services 68.338 +
  construction 2.634 = 100.000 is how you know they are the published ones).
- PCE: BEA Table 2.4.5U against the 210 underlying-detail lines.
- Labour Costs: Productivity and Costs, and the ECI news release.

**Precedent:** every one of the 174 payroll ids was verified this way before
ingestion, and all 174 reproduced afterwards. That has NOT been done for CPI,
PPI, PCE or Labour Costs at the same depth.

A failure looks like: a figure that differs, an id that maps to the wrong row,
or a category present in the release and absent from the database.

### B. Vintage integrity

- **1,025 series carry `fetch_date` and have no revision history at all.** Is
  each one genuinely a source that serves no vintages? Every BLS and BEA series
  should be (neither API serves them); a FRED series marked `fetch_date` should
  be one ALFRED genuinely has nothing for. Trap 15.
- No `from_row` series should be sitting on a single vintage — that was trap 35
  and is **currently 0**, so this is a regression check.
- Spot-check a revision: pick a payroll month, confirm the first print and the
  current value differ and that both are stored. July 2026 moved −23,000 →
  +21,000 in one run; that is what the archive is for.

### C. Derived measures reconcile to their parents

Six exist: CPI weighted median and breadth, PPI counted breadth, claims state
breadth and distance-off-the-low, plus the arity/weighting machinery.

- Do the weights sum to what they should?
- Does a contribution set reconcile to its parent index?
- Is the completeness floor still right? The floor was once a hard-coded
  `total < 50`, which with unit weights blanked an entire measure.
- Does a truncation still leave every derived input its full lookback? A
  breadth line silently lost eight of its ten years this way.

### D. Every chart against its own caption

140 tables. A caption that says "twelve-month change" over a panel drawing
three-month annualised is invisible to every check in the repo — `shoot.py`
counts marks, it does not read.

Check: transform matches the caption, window matches the stated period, units
match the axis, and the key colours match the series order.

### E. Units — the 1000× class

Trap 7. Claims arrive in **persons**, JOLTS in **thousands**. A recipiency
ratio was wrong by a factor of a thousand and looked perfectly plausible. Any
panel dividing one series by another from a different release is a candidate.

### F. Seasonal adjustment labels

`add_series.py` filed **SAAR as NSA** because its flag had only two branches
(trap 45). Audit `seasonal_adjustment` against what each source actually
states, especially the 210 BEA series.

### G. The permanent nulls

October 2025 is empty for ever: 59 of 59 household-survey series, 439 of 469
monthly CPI series. Traps 4 and 22.

Confirm nothing interpolates across it, nothing waits for it, and every chart
that spans it shows a break. Also confirm the **October 2026** consequence is
understood: next month the hole becomes the *base* of the twelve-month change
rather than the current value.

### H. What is held but never drawn

**2,411 series are drawn by nothing.** That is deliberate — the `publish`
column exists for it — but the audit should ask, per release, whether what is
held is complete and whether anything held is worth promoting. 74 are dead at
source and must never reach a panel (trap 28).

### I. Presentation

- Read every page at 1400px and at 430px.
- `tools/clipcheck.py` for overflow and dangling anchors; three panels carry
  `data-span="intended"` and are deliberate.
- The landing page's index, map and scope line are **generated** — trap 55.
  Never hand-edit them.

---

## Tools

```bash
cd ~/dashboards && set -a && . .env && set +a
./venv/bin/python -m macro.validate          # 37 assertions against the releases
./venv/bin/python tools/coverage.py          # every exported series drawn?
./venv/bin/python tools/staleness.py         # vs each series' own frequency, and BLS
~/.venvs/shot/bin/python tools/clipcheck.py  # overflow + dangling anchors
~/.venvs/shot/bin/python tools/shoot.py --path us/inflation/cpi   # render and count marks
psql "$MACRO_DSN"                            # the archive itself
```

`tools/shoot.py` cannot take an empty `--path`; screenshot the landing page
with a short Playwright snippet instead.

---

## Traps an auditor must know before starting

Read all 55, but these decide whether a query is right or wrong:

- **An observation has many vintages.** The current value is the latest vintage
  per `(series_id, observation_dt)`. A naive `SELECT` returns the wrong print.
- **A published null is still a row.** Freshness must be measured from the last
  non-null value; measuring from the last *row* reported twelve dead series as
  current (trap 49).
- **A title is not evidence** (traps 36, 50). Verify ids by value.
- **A stack is only honest for a partition**, and the palette stops at six.
- **`shipped()` reads the exported bundles**, so its verdict changes the moment
  an export runs — an alarm can be right when it fires and stale an hour later.

---

## What not to do

- **Do not trust a green check.** That is the whole premise.
- **Do not ingest anything.** This audit precedes the next country; adding data
  mid-audit invalidates it.
- **Do not hand-edit a generated block** — the rail, the landing index, the
  map, the scope line, `catalog.sql`.
- **Do not touch** `caddy`, `everos`, `everos_mcp`, `litellm`, `linkding`,
  `postgres`, `docker-compose.core.yml`, or existing Caddy site blocks.

---

## Done looks like

A written finding list, each item either fixed or recorded with a reason, and:

1. Every release reconciled against its published news release at least at the
   headline-table level, with the method written down so it can be repeated.
2. Every one of the 140 tables read against its caption.
3. The vintage story confirmed for all 1,025 `fetch_date` series.
4. A statement of what is held and not drawn, per release, and whether that is
   deliberate.
5. Any new trap added to `CLAUDE.md`, and `HANDOFF.md` refreshed.

Then, and only then, the next country.
