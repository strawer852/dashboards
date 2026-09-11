# Handoff — 11 September 2026, after CPI

**Read `CLAUDE.md` first.** It is the authority: traps 1-65, 67 and 68 on master
(trap 66 lives on the `bls-provisional` branch until it is merged), the settled
decisions, the running state, the guardrails. This file is only the part that
would be stale by the time you read it; where the two disagree, CLAUDE.md is
right. The audit's record is `AUDIT_FINDINGS_2026-09-09.md`, section 4.7
covers the 10 September releases and 4.8 the 11 September CPI morning.

**Nobody is watching.** Friday's CPI and state claims both settled on the
timers, after two faults were fixed mid-morning (trap 68). Next up: national
claims on Thursday 17 September, state claims on Friday 18 September, JOLTS
on 29 September. The checklist below is what a good release morning looks
like.

## Where to run

Everything of substance lives on the VPS: `ssh strawer@bigricebowl.cloud`,
then `cd ~/dashboards`. The database, the timers, the docker network the
screenshot tools use, and the FRED, BLS and BEA keys are all there. The laptop
clone (`C:\Bigricebowl\dashboards`) can read and edit code and documents and
run `tools/keycheck.py`, but nothing that touches Postgres or renders a page.

Run Claude Code on the VPS **inside tmux**: a session started from a plain SSH
shell dies at logout.

```bash
tmux new -s audit            # or: tmux attach -t audit
cd ~/dashboards && claude --continue
# detach: Ctrl-B then D; come back with tmux attach -t audit
```

From inside the session, `pstree -s -p $$` must show `tmux: server` above
`claude`. Commits push nightly at 23:30 via `dashboards-push`;
`git log --oneline origin/master..HEAD` lists what the laptop cannot see yet.

## A release morning, as checked on Friday 11 September

Both at 08:30 ET. The first CPI through three changes made on the 10th: the
per-source gate (trap 65), the settle rule (trap 67), and FRED pacing (trap
67). What good looks like in `logs/refresh.log`:

**On the 11th it went this way:** BLS-API items exported at 08:37 ET, state
claims at 08:49 and settled at 08:55, FRED's CPI in two waves exported at
09:48 and 09:58, and `settled: bls.cpi` at 10:07. Two polls failed on FRED's
403 block before the 09:35 fix. Findings 4.8 has the figures.

1. **01:40 ET sweep**: `release dates rc=0`; ingest inserts nothing or
   little.
2. **From 08:35 ET**: `refresh start (bls.cpi,eta.state_claims)`. The first
   poll inserts the 270 BLS-API CPI items, which publish at the embargo, with
   fetch-time vintages.
3. **Polls keep naming `bls.cpi` until FRED posts its 199 CPI series**, an
   hour or more later. A poll saying "nothing outstanding" before `CPIAUCSL`
   has an August value is trap 65 back.
4. **When FRED posts**: `changed:` with many series, then a backfill that
   takes minutes, not seconds, because FRED calls are now paced at 110 a
   minute. A 429 is waited out, not fatal. Then `validate rc=0`, `export`,
   and a push naming `bls.cpi`.
5. **One more poll finds nothing** and logs `settled: bls.cpi`. After that:
   "nothing outstanding; not polling". State claims settle the same way; FRED
   posted last week's state report at 08:39 ET.

Then look, not just read:

- **CPI page**: stamp released 11 September for August; Table 1 and the
  median draw August and label "Aug 26".
- **Weekly Claims**: Tables 8 and 9 reach 5 September; the state claims
  release reads 11 September. Tables 2, 3 and 7 stay at 29 August until
  Thursday 17 September, by design: continuing claims publish a week behind.
- **Checks**: `validate` 38/38, `coverage`, `keycheck`, `clipcheck` at both
  widths. When the Wayback Machine has the new CPI tables, run
  `tools/reconcile.py` against them and record it as findings 4.8.
- **Calendar**: both of Friday's rows should read `settled`:

```sql
SELECT release_id, status FROM macro_release_dates
WHERE (release_at AT TIME ZONE 'America/New_York')::date = '2026-09-11';
```

**If a release fails halfway** -- `backfill rc=1`, or validate or export
failing -- the next poll now retries it: look for `backfill left over from an
earlier run:` or `previous run failed; validating and exporting again`, then
`settled:`. If that does not clear it, finish it by hand the way PPI was
restored on the 10th:

```bash
cd ~/dashboards/macro && set -a && . ../.env && set +a
../venv/bin/python backfill.py --series <ids still on fred_csv rows>
../tools/refresh.sh --releases bls.cpi --force     # takes the refresh lock, logs as a timer run does
```

The release timer polls every ten minutes from 08:35 to 14:55 ET and every
thirty from 15:25 to 20:55 ET. Since 11 September FRED's CSV downloads are
spaced 0.6 seconds apart (trap 68), so a CPI poll takes about two and a half
minutes and the 01:40 sweep about twenty-five. A `403 You don't have
permission to access` from FRED is its edge refusing a burst: the poll
fails, alerts, and the next one retries. A late FRED is normal; look again in the
evening before calling anything broken.

## What changed on 9, 10 and 11 September

**9 September, the audit's second half** (2f75988, d160b72, 08e921a,
ccde9eb, b685260, b9b8c86):

- **Reconciled every release to its news release by value**, zero
  disagreements: CPI 513 rows, PPI 897, ECI 385, Productivity 132 columns,
  PCE 210 weights and levels. `tools/reconcile.py`; tables from the Wayback
  Machine because bls.gov blocks the VPS (trap 62).
- **Claims split into two releases**: the 106 state and territory series are
  `eta.state_claims` (FRED 469, Fridays); the national nine stay `eta.claims`
  (FRED 180, Thursdays). Trap 61.
- **359 FRED series backfilled** that the backfill had wrongly filed as
  vintage-less; every FRED series is now `from_row` (trap 63).
- **By-date alignment** changed the CPI median in 30 months and breadth in
  164; two sparse inputs swapped for their Table 2 parents (trap 60).
- **Every table looked at** at 1280px and 430px; label collisions fixed in the
  engine (trap 64); every numeric caption recomputed, six corrected.

**9 September, another session's forecast work** (96dd138, 266c5f1, 48e569b,
e348f2d, with asset stamps): the landing page became the map alone with a
hover card per region; the PPI and CPI pages carry a forecast record scored
against the first print; `PPIFID` joined the catalogue; and
`macro-forecast-reminder`, a daily 08:00 timer, was added. See those commits
before touching the forecast panels.

**10 September, the PPI and claims releases:**

- **3692130 -- the gate judges each source separately** (trap 65). It had
  called a release landed on any row dated today, which would have stopped
  CPI polling on the BLS-API rows an hour before FRED's headline.
- **db60d8e -- evening polling** to 20:55 ET every thirty minutes, sized to
  the BLS key's 500 calls a day.
- **31278bc -- the success alert names the releases that changed**, not
  those polled. Claims landed at 11:16 ET and match the Labor Department
  exactly: initial claims 206,000, continuing 1,774,000, insured rate 1.2%.
- **0c1f095 -- every date axis labels its newest period** (trap 64 addendum).
  William reported Weekly Claims Tables 7 to 9 as not updating; the data was
  current, but only 5 of 164 charts labelled their newest period. `clipcheck`
  now fails any that does not, at both widths. Tables 2, 3, 7, 8 and 9 say in
  their notes why they end a week before Table 1.
- **ef118be -- a release is polled until it settles; leftover work is
  retried; FRED calls are paced** (trap 67). PPI landed at 12:53 ET, the
  backfill hit FRED's rate limit, the refresh failed before export, and the
  gate stood down with the page on July and `PPIFIS` itself still missing.
  Restored at 13:19 ET by hand, fixed, and proven live when the 13:25 ET
  poll logged `settled: bls.ppi, eta.claims`. FRED matches BLS exactly:
  final demand 157.411 for August.

**11 September, the CPI morning** (a0d3ebe, trap 68, findings 4.8):

- **FRED's CSV downloads are spaced 0.6 seconds apart.** They had been
  unpaced, up to 23 a second. FRED's edge answered 403 to the 09:05 and
  09:25 ET polls, each failing with a false "Dashboard refresh failed" push.
  The next poll recovered each time through trap 67's retry. The first
  paced poll made 198 downloads, at most 3 a second, with no 403.
- **The stamp's period comes from the rows that date it.** From 08:37 ET the
  BLS-API items put CPI's `ref_period` at August while `released_at` stayed
  on July's 12 August, so the page read "August 2026, Released 12 Aug 2026".
  It now reads July until FRED's August lands, confirmed by screenshot.
- **State claims landed at 08:48 ET and settled at 08:55**, 106 rows.

## Where it stands

**3,127 series across 10 releases and three sources; 3,447,358 vintage rows
over 1,368,446 observations, 1913 to 5 September 2026; 38/38 validations;
100% coverage; clipcheck clean at both widths.**

| Release | Sources | Publishes | Next | Status |
|---|---|---|---|---|
| `bls.cpi` | 270 BLS, 199 FRED | 08:30 ET | 14 Oct | settled 11 Sep |
| `eta.state_claims` | 106 FRED | Fridays | 18 Sep | settled 11 Sep |
| `eta.claims` | 9 FRED | Thursdays | 17 Sep | settled 10 Sep |
| `bls.ppi` | 640 FRED | 08:30 ET | 15 Oct | settled 10 Sep |
| `bls.jolts` | 144 BLS, 540 FRED | 10:00 ET | 29 Sep | |
| `bea.personal_income` | 210 BEA, 25 FRED | 08:30 ET | 30 Sep | |
| `bls.employment_situation` | 36 BLS, 261 FRED | 08:30 ET | 2 Oct | |
| `bls.eci` | 6 BLS, 398 FRED | 08:30 ET | 30 Oct | |
| `bls.productivity` | 282 FRED | 08:30 ET | 5 Nov | |
| `frb.wage_tracker` | 1 FRED | no calendar | | swept daily |

`vintage_mode`: all 2,461 FRED series are `from_row`; the 456 BLS and 210 BEA
series are `fetch_date` and may never be offered a revision overlay.

`macro_release_dates.status` is new: `scheduled` until a poll after the
release landed finds nothing new and has no work left, then `settled`, and
only unsettled releases are polled. To make a settled release poll again,
set its row back to `scheduled`.

Timers: `macro-refresh-due` (release windows), `macro-refresh-sweep` 01:40 ET,
`macro-forecast-reminder` 08:00 local, `dashboards-push` 23:30 local,
`dashboards-timer-check` 06:30 ET.

## Built, tested, not deployed: branch `bls-provisional`

Commit 0dd3406, worktree `~/dashboards-bls-provisional`. On release mornings
the BLS API's figure stands in for FRED's, under the FRED series id and only
for dates FRED does not yet carry, until FRED's own copy replaces it; the
page says the figures are early. The BLS id of each of the 324 drawn FRED
series in BLS releases is verified by value (`tools/bls_map.py`); 11 were not
what their FRED name suggested. Trap 66 on the branch has the rules.

**Deploy only after Friday's CPI has settled cleanly**, and in this order:
merging before the column exists fails every refresh.

```bash
cd ~/dashboards && set -a && . .env && set +a
# 1. As the table's owner, the role trap 54 names (macro_app has no DDL rights):
#      ALTER TABLE macro_series_meta ADD COLUMN bls_id TEXT;
# 2. Re-verify every BLS id by value on the day, then store them.
./venv/bin/python ../dashboards-bls-provisional/tools/bls_map.py --apply \
    ../dashboards-bls-provisional/tools/research/bls_map_$(date +%F).csv
# 3. Merge, resolve the conflicts below, restamp.
git merge bls-provisional
python3 tools/stamp_assets.py
# 4. Prove it.
./venv/bin/python -m macro.validate && ./venv/bin/python macro/export.py
./venv/bin/python tools/coverage.py && python3 tools/keycheck.py
~/.venvs/shot/bin/python tools/clipcheck.py
git worktree remove ../dashboards-bls-provisional
```

**The merge will conflict in three places, and needs one change that will
not show as a conflict:**

- **`macro/refresh.py`**: both sides rewrote `_OUTSTANDING` and the main
  loop after the branch was cut. Keep all of it: the branch's
  `o.source <> 'bls_provisional'` exclusion, per-source fetching
  (`series_for_pairs`) and `--provisional`; and master's settle state
  (`status`, `landed_unsettled`, `settle`), `pending_backfill`, the
  failed-run retry, and `releases_of` in the alert. Then re-run the branch's
  twelve provisional scenarios and master's five settle scenarios, both in a
  rolled-back transaction.
- **The eight pages' `?v=` stamps**, because both sides changed the engine:
  take either side and rerun `tools/stamp_assets.py`.
- **`CLAUDE.md`**: both insert traps before "## How it runs"; keep trap 66
  from the branch, then 67 and 68 from master, in that order.
- **`macro/export.py`, no textual conflict, a real one in meaning.** Master
  now takes a release's `ref_period` from publication vintages only (trap
  68), so the stamp's period and date come from the same rows. The branch
  dates a provisional release from the calendar. Merged as they stand, a
  morning with early BLS figures would read "July 2026 · Released 11 Sep":
  July's period against August's release. Where the branch sets
  `released_at` from `provisional_releases`, set `ref_period` from the
  newest `bls_provisional` observation too (add `max(o.observation_dt)` to
  `PROVISIONAL_SQL`), and add that case to the scenarios before merging.

The first release that exercises it is JOLTS on 29 September: look for
`provisional from the BLS API, pending FRED:` on the first poll, "Early
figures from the BLS API, pending FRED" in the stamp, polls continuing, then
`changed:` and `backfill rc=0` for the same series once FRED posts.

## Recorded, not changed — decisions for William

- **CPI and PPI Table 1 draw the twelve-month change from the seasonally
  adjusted index** and say so, while BLS headlines the unadjusted: July 2026
  read 3.3 on the page against 3.4 in the release. `CPIAUCNS` and
  `CUUR0000SA0L1E` are held, and `PPIFID` now is too, so switching is a page
  change, not an ingest.
- **A single transient FRED error fails a poll and pushes an alert** that the
  next poll clears, as a 404 on `WPUFD4232` did at 11:55 ET on the 10th and
  FRED's 403 block did twice on the 11th, at 09:05 and 09:25 ET. Proposed:
  push only when the same series fails on two consecutive polls.
- **The settle rule assumes FRED posts a release in one go, and it does
  not.** On the 11th FRED posted CPI in two waves ten minutes apart; a
  longer pause would have settled CPI with 129 series, core among them, on
  July, with nothing polling again until the 01:40 sweep. A stricter rule
  settles only when no published FRED series in the release is behind the
  newest period its FRED series have reached. It needs a careful definition
  of "behind", because sparse and dead series exist. Findings 4.8. Decide
  before the Employment Situation on 2 October.
- **`bls-provisional` replaces a disagreeing BLS figure silently.** Proposed
  before deploying: count those replacements and push an alert naming the
  series and both values, since FRED copies BLS exactly (64 of 64 drawn CPI
  series identical for August) and a disagreement means a wrong id mapping.
- **A FRED 403 is retried on the short backoff** and fails the poll; the next
  poll retries. Waiting a minute per retry would hold the lock past an hour
  during a block. Findings 4.8.
- **Nine SA rows of ECI Tables 1–3 and the unadjusted PPI headline
  groupings other than `PPIFID` are not held**; none is drawn.
- Labour Costs draws 24–25 years with no window in its headers; claims
  Table 9 lists states in postal-code order; payroll Table 21's grey line is
  deliberate and Table 28's title wraps.

## Loose ends, none blocking

- **August CPI is not yet reconciled against the news release tables.** The
  Wayback Machine's newest `cpi.t01.htm` and `cpi.t02.htm` snapshots were
  from 3 and 8 September at 10:00 ET on the 11th, the July release. When an
  11 September snapshot exists, run `tools/reconcile.py` (command in
  CLAUDE.md) and add the result to findings 4.8.
- **74 series are dead at source** (45 Productivity, 23 PPI, 4 CPI, 2 ECI),
  confirmed against BLS; none is drawn.
- **Two dead CPI series still hold provisional rows** from 5 September,
  `CUUR0000SEHP` and `CUUR0000SEHP04`; both unpublished. The two-day window
  in `pending_backfill` leaves them alone on purpose.
- **The scenario tests of 9 and 10 September are not in the repo**: they ran
  from the session scratchpad against rolled-back transactions, and findings
  4.7 and traps 65 to 67 describe what each proved. Worth turning into a
  `tests/` directory before the next change to the gate.
- **`frb.wage_tracker` has no calendar rows, correctly.** The flatness check
  is calibrated, with three panels marked `data-span="intended: …"`.
- **The dead-man's switch is proven**; re-test with
  `MAX_AGE_HOURS=0 ops/dashboards-timer-check`, then run it bare.
- **`~/bigricebowl` still has an unpushed commit** (the EverOS pin) plus
  older uncommitted deletions that are not mine.
- Screenshots are in `logs/shots/` (`review/`, `labelfix/`, `labelfix2/`,
  `ppi0910/`), gitignored.

## October 2025 is permanently empty, and that is settled

The shutdown stopped field collection and BLS will not collect October 2025
retroactively: all 59 household-survey series and 439 of 469 monthly CPI
series lost it; 201 of 202 establishment series kept it. Nothing interpolates
across it. Expect it again in **October 2026**, when the hole becomes the base
of the twelve-month change. Traps 4 and 22.

## Commands

```bash
cd ~/dashboards && set -a && . .env && set +a
./venv/bin/python -m macro.validate                 # 38/38
./venv/bin/python macro/export.py                   # re-export without ingesting
./venv/bin/python tools/coverage.py                 # 100% on all seven
python3 tools/keycheck.py                           # static, runs anywhere
~/.venvs/shot/bin/python tools/clipcheck.py         # overflow, collision, newest label; both widths
~/.venvs/shot/bin/python tools/shoot.py --path us/inflation/cpi [--element t1]
./venv/bin/python tools/staleness.py                # 74 overdue, 0 actionable
tools/refresh.sh --releases bls.cpi --force         # complete a release by hand, under the lock
tail -f logs/refresh.log
systemctl --user list-timers 'macro-*'
```

A BLS news release table for `reconcile.py` (bls.gov refuses the VPS):

```bash
curl -sL --compressed -o cpi.t02.htm \
  "https://web.archive.org/web/2026id_/https://www.bls.gov/news.release/cpi.t02.htm"
```

Before committing any document, read `git diff --stat` (trap 56). This file
is written whole and is about 15 KB; if it is ever megabytes, that is the
trap, not a handoff.
