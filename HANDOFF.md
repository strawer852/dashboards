# Handoff — 4 September 2026, end of day

**Read `CLAUDE.md` first.** It is 778 lines and it is the authority: 34 traps,
the settled decisions, the running state, the guardrails. This file is only the
part that would be stale by the time you read it — where things stand right
now, what is pending, and what the next decision is. Nothing here overrides
CLAUDE.md; where they disagree, CLAUDE.md is right and this file is old.

Everything lives on the VPS: `ssh strawer@bigricebowl.cloud`, then
`~/dashboards`. Nothing of substance is on the laptop.

---

## Where it stands

**183 series across 8 releases, ~389,000 vintage rows, 36/36 validations, and
100% coverage on all five dashboards.** Every exported series is drawn by its
page and still published by its source.

| Dashboard | Tables | Charts |
|---|---|---|
| `us/employment/nonfarm-payroll` | 33 | 33 |
| `us/inflation/cpi` | 31 | 38 |
| `us/inflation/ppi` | 20 | 24 |
| `us/employment/jolts` | 7 | 7 |
| `us/employment/weekly-claims` | 6 | 6 |

Two timers, both armed:

| Timer | Fires | Runs |
|---|---|---|
| `macro-refresh-due` | 08:35–14:55 ET weekdays | whatever the calendar says is outstanding |
| `macro-refresh-sweep` | 01:40 ET daily | everything, catch-all |

Plus `dashboards-push` (23:30) and `dashboards-timer-check` (06:30 ET).

---

## The one thing to watch

**Thursday 10 and Friday 11 September are the first live test of this
session's scheduling work**, and they test two things that have never run for
real:

- `macro-refresh-due` replaced three hand-written timers. It has been proved
  against seven simulated moments but has never fired on a release day.
- The already-landed guard **had never once fired** before it was fixed. It
  compared an ALFRED vintage in `America/New_York`, and ALFRED stores vintages
  at midnight UTC — so the 4 September vintage read as 3 September and never
  matched. The log shows the release landing at 13:35Z and the 13:45Z and
  13:55Z windows each refetching all 64,220 observations.

10 September carries **two releases on one day** — `bls.ppi` and `eta.claims`
— which is exactly the case the old grouped gate would have mishandled. That
makes it the most informative day available.

What good looks like in `logs/refresh.log`: a `refresh start (bls.ppi,eta.claims)`
after 08:35 ET, `ingest` inserting rows, `validate rc=0`, `export`, an ntfy
push — and then the *following* windows saying nothing outstanding rather than
refetching. If they keep refetching, the guard is still wrong.

Then **look at the rendered pages**, which is not optional and not the same as
a DOM probe. Yesterday every chart drew perfectly while a contents list had
been deleted; today a series that had been dead since 2011 sat on the PPI page
drawing nothing while validation, coverage and export all reported success.

---

## The open decision

Nothing structural is outstanding — the backlog in CLAUDE.md's "Open right
now" is down to a note about two dead columns. Two reasonable directions:

1. **Hold until the 10th/11th** and verify the release runs. Costs nothing and
   is the highest-information event available.
2. **Build dashboard #6.** The strongest candidate is **PCE** — it is what the
   Fed actually targets, the PPI dashboard now explains at length which
   producer prices feed it (physician care, hospital inpatient care, portfolio
   management), and there is no dashboard for the measure itself. Retail
   sales, industrial production or housing starts would also fit.

   The rule for a new dashboard, from CLAUDE.md and worth restating: **a spec
   file plus catalogue rows and no new JavaScript. If it needs any, that is an
   engine defect, not a special case.** That rule found four real engine gaps
   this session.

---

## Loose ends, none blocking

- **`~/bigricebowl` has an unpushed commit of mine** (`5995cf5`, the EverOS
  pin) and, from before, `10e2850` plus uncommitted deletions that are not
  mine. I did not push, because pushing would have carried unreviewed work.
  William's call.
- **`~/backups/everos-data-pre-1.2.3-20260904.tar.gz`** is the pre-upgrade
  snapshot. Delete it once 1.2.3 has run a while.
- **The dead-man's switch `/fail` path is unproven.** The ok ping returns 2xx
  and healthchecks is receiving. `/fail` has only ever fired against a
  placeholder URL. Firing it for real sends a genuine down-alert and then
  recovers on the next run — needs William's say-so.
- **`pub_lag_days` and `staleness_mode`** are columns with no consumer, all
  182 rows NULL. Superseded by the forward calendar and the coverage
  staleness check. Drop them or leave them, but do not build on them.
- **A bearer token was printed into the previous session's transcript** while
  reading the Caddy config. Nothing leaked — it is William's own secret in his
  own session — but rotate it if that log is ever shared.
- **ntfy self-hosting is closed as a no**, with reasons, in CLAUDE.md. Do not
  reopen it without a new argument: the notifier must not live on the box it
  watches.

---

## What this session did

Seven commits, `2dee011..9f81a75`, all pushed to `origin/master` via the
`github-dashboards` deploy key.

- **PPI detail panels paired year|month** in the CPI convention — one row per
  topic, twelve-month left, one-month right, right half unnumbered.
- **Found a dead series.** `WPS3012` stopped in December 2011 and FRED still
  serves it. It had observations, so export was content; it had a panel, so
  coverage reported it drawn at 100%; its tests pin old vintages, so
  validation passed. Every number correct, the chart empty. Replaced with
  `WPS301`, the live SA parent. `coverage.py` now checks that everything it
  ships is still published, and testing that check against seven synthetic
  series found **two bugs in the check itself**.
- **Scheduling became a question asked of the catalogue.** `refresh.py --due`
  reads `macro_release_dates`; three typed timers became one. Resolves per
  release, respects each embargo, treats an empty calendar as a fault.
- **Four engine gaps closed** rather than worked around: `PANELS.line` had no
  `axisFormat`; `export.py` could not express "discontinued" (now
  `exclude_series`); `install-timers.sh` could add a unit but never retire
  one; `dashboards-timer-check` watched a **typed list** of timers and so was
  blind to the one added that same day — its watch list now derives from
  `systemd/*.timer`.
- **Charts in a row now share a baseline**, and five payroll rows whose charts
  had different declared heights were equalised.
- **EverOS upgraded 1.1.2 → v1.2.3**, closing `GHSA-grm3-hcqf-hm28` (CVSS
  8.2). It was not reachable — 8000 is never published to the host, Caddy
  proxies `everos_mcp:8001`, and the MCP wrapper calls only four
  `/api/v1/memory` endpoints — but fixed rather than relied upon.

The recurring shape, and the reason so much of this file is about verification
rather than features: **every one of these was found by looking at the thing
itself, not at a report about it.** Four separate green checks — validation,
coverage, export, and a DOM probe — all passed over a chart that drew nothing.
