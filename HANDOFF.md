# Handoff — 9 September 2026, end of the audit's second half

**Read `CLAUDE.md` first.** It is the authority: 67 traps, the settled
decisions, the running state, the guardrails. This file is only the part that
would be stale by the time you read it. Where they disagree, CLAUDE.md is right
and this file is old. The audit's full record is `AUDIT_FINDINGS_2026-09-09.md`
(section 4 is the VPS half); its terms of reference are `AUDIT.md`.

## Where to run

Everything of substance lives on the VPS: `ssh strawer@bigricebowl.cloud`,
then `cd ~/dashboards`. The database, the timers, the docker network the
screenshot tools use, and the FRED/BLS/BEA keys are all there. The laptop clone
(`C:\Bigricebowl\dashboards`) can read and edit code and documents, and can
run `tools/keycheck.py` (static, no data), but it cannot run validate, export,
coverage, clipcheck, shoot, reconcile, or anything that touches Postgres.

**Run Claude Code on the VPS inside tmux.** A session started from a plain
SSH shell dies at logout; the 9 September session lost two attempts to that
before getting it right. The recipe:

```bash
tmux new -s audit            # or: tmux attach -t audit
cd ~/dashboards && claude --continue
# detach: Ctrl-B then D; log out freely; come back with tmux attach -t audit
```

Verify from inside the session that `pstree -s -p $$` shows `tmux: server`
above `claude`. If it shows `sshd-session`, you are not in tmux.

The commits are pushed nightly at 23:30 local by `dashboards-push`; until
then `git log --oneline origin/master..HEAD` lists what the laptop cannot see
yet. Nothing here needs pushing by hand.

## What this session did, in order

1. **Merged and proved the web session's branch.** Validate 37/37 before and
   38/38 after (the extra check is the new release's freshness), forced
   re-export, coverage 100% on all seven, keycheck 0, build_nav nothing to
   change, clipcheck clean, every page and `/us/` rendered and looked at.
2. **The by-date alignment fix was not a no-op.** The CPI median changed in
   30 of 180 months and the breadth measure in 164, because three of the 135
   inputs end early (April, May, June 2026). An independent computation
   agreed with the new values in every month. Two sparse inputs were swapped
   for their monthly Table 2 parents (same weights). Trap 60 carries it.
3. **Area A, reconciliation by value.** `tools/reconcile.py` reproduces the
   CPI, PPI, ECI and Productivity news release tables from the database as
   of the vintage that published them: CPI 513 rows, PPI 897, ECI 385,
   Productivity 132 columns, PCE 210 weights and levels — **zero value
   disagreements**. bls.gov blocks this VPS on every route; the tables come
   from the Wayback Machine (trap 62).
4. **Claims were one release spanning two FRED releases.** The page stamp
   read Friday's date for Thursday's report every week and the calendar was
   filling with Fridays. The 106 state and territory series are now
   `eta.state_claims` (FRED 469); the national nine stay `eta.claims` (FRED
   180). Both are drawn on the same page; the stamp comes from the national
   one. `release_dates.py` probes two series per release and shouts if they
   map to different FRED releases (trap 61).
5. **359 FRED series marked `fetch_date` had ALFRED histories.** The
   backfill's "one row per observation means no history" test cannot tell
   a never-revised series (unadjusted CPI, ECI) from a vintage-less one.
   Test fixed, all 359 backfilled (89,994 rows) and on `from_row`. No FRED
   series is on `fetch_date` now; the 666 that are, are BLS and BEA, which
   genuinely serve none (trap 63).
6. **Every table looked at, at 1280px and 430px.** Axis labels collided on
   the weekly claims axes at desktop width and on nearly every panel at
   phone width. The engine now drops overlapping labels, sizes the label
   interval from measured label widths, sets value-axis steps the same way,
   and waits for the webfonts before drawing; `clipcheck.py` tests label
   collision at both widths and counts touching labels as colliding
   (trap 64). A quarterly stamp read "April 2026"; it reads "2026 Q2".
7. **Every number in every caption recomputed.** 45 measured claims, 39
   exact, six wrong and fixed (findings 4.6): the JOLTS separations peak is
   March 2020 at 16.3m; the 2022 saving-rate low is not a record; shelter is
   nine times gasoline, not thirteen; portfolio management swings −14% to
   +33%; the PPI persistence statistics; the teen-rate ratio "in normal
   times". Two month counts that drift now carry end dates.
8. **10 September, watching PPI: the `--due` gate would have silenced
   Friday's CPI.** It called a release landed on any row dated today, and
   the BLS-API items land an hour before FRED. It now requires every source
   feeding a release to have landed since the embargo (trap 65). Fixed and
   deployed the day before CPI.
9. Small fixes along the way: PCE Table 14's CPI excluded-from-core share
   (20.953), two state labels that carried "the", the "137 inputs" and "14
   residuals" spec comments (135 and 10).

Commits, in order: 2f75988 (split, reconcile, median inputs), d160b72
(docs), 08e921a (backfill), ccde9eb (axis labels, quarterly stamps),
b685260 (captions), and the one carrying this file.

## Where it stands

**3,126 series across 10 releases and three sources, 3,443,273 vintage rows
over 1,367,052 observations spanning 1913 to August 2026, 38/38 validations,
100% coverage, no label overflowing or colliding at either width.**

| Release | Published | Held | Note |
|---|---|---|---|
| `bls.employment_situation` | 138 | 297 | |
| `bls.cpi` | 176 | 469 | 87 items backfilled today |
| `eta.claims` | 6 | 9 | FRED 180, Thursdays |
| `eta.state_claims` | 53 | 106 | FRED 469, Fridays; new today |
| `bea.personal_income` | 232 | 235 | |
| `bls.ppi` | 61 | 639 | |
| `bls.jolts` | 44 | 684 | |
| `bls.eci` | 2 | 404 | 271 series backfilled today |
| `bls.productivity` | 2 | 282 | |
| `frb.wage_tracker` | 1 | 1 | no calendar, correctly |

`vintage_mode`: 2,460 FRED series `from_row`; 456 BLS and 210 BEA
`fetch_date`. None of the latter may ever be offered a revision overlay.

## The release watch — the thing still open

**Thursday 10 September**: PPI and the national claims report, 08:30 ET.
**Friday 11 September**: CPI and the state claims report. First releases
through everything above. What good looks like in `logs/refresh.log`:

- The 01:40 ET sweep on the 10th logs `release dates rc=0` listing both
  `eta.claims` and `eta.state_claims`, with no `!! spans` line, and the
  ingest inserts 0 rows.
- Thursday from 08:35 ET: `refresh start (--due)` naming `bls.ppi` and
  `eta.claims` (a simulation of the query says exactly those two), BLS
  series fetched from a recent year rather than 1939, `validate rc=0`,
  `export`, an ntfy push, and later windows saying nothing outstanding.
- Friday: the same for `bls.cpi` and `eta.state_claims`. **New since the
  trap 65 fix:** the first window will insert the BLS-API CPI items, and the
  windows after it must keep naming `bls.cpi` until FRED publishes the
  headline, about an hour later. A window saying "nothing outstanding"
  before `CPIAUCSL` has an August value is the defect back. The 87 backfilled
  CPI items are on `from_row` for the first time, so expect the ALFRED
  refetch to run for them and their new vintages to be dated
  `2026-09-11 00:00`, not a fetch time. The state poll on Friday is
  expected and right: FRED updates those series on the Friday.

**PPI, 10 September: landed, failed halfway, restored, fixed** (trap 67).
FRED's rate limit stopped the backfill and the gate called the release
landed, so the page kept July until a forced run at 13:19 ET. The pipeline
now paces FRED, polls a release until it has **settled** (a later poll found
nothing new), and retries a failed backfill or export on the next poll.
Friday's CPI is the first release through it: good looks like the polls
continuing past the first landing, one quiet poll logging `settled: bls.cpi`,
and then "nothing outstanding". **Merging `bls-provisional` will conflict in
`macro/refresh.py`**: both change `_OUTSTANDING` and the main loop. Keep all
three rules -- the branch's `o.source <> 'bls_provisional'` exclusion and
per-source fetching, and master's settle state and leftover-work retry.

**Fixed 10 September at William's request**: every date axis now labels
its newest period, where 5 of 164 did, and `clipcheck.py` enforces it at
both widths. Weekly Claims Tables 2, 3, 7, 8 and 9 say in their notes why
they end a week before Table 1. When `bls-provisional` is merged, the pages'
`?v=` stamps will conflict because both sides changed the engine: take either
side and rerun `tools/stamp_assets.py`. Recorded, not changed: a single
transient FRED 404 fails a poll and pushes a failure alert that the next
poll clears.

The release timer now polls every ten minutes from 08:35 to 14:55 ET and
every thirty from 15:25 to 20:55 ET, extended on 10 September when FRED had
posted neither PPI nor claims by mid-morning. If FRED is late, look again in
the evening before concluding anything is wrong.

**Built, tested, not deployed: branch `bls-provisional`**, in the worktree
`~/dashboards-bls-provisional`. On release mornings the BLS API's figure
stands in for FRED's until FRED catches up, then FRED's replaces it; trap 66
on the branch's `CLAUDE.md` has the rules. Deploy only after Friday's CPI has
landed cleanly on trap 65's gate, because this changes the same gate.

Deploy, **in this order** -- the branch's ingest reads `bls_id`, so merging
before the column exists fails every refresh:

```bash
cd ~/dashboards && set -a && . .env && set +a
# 1. the column. Run this SQL as the table's owner, the role trap 54 names:
#    macro_app, which MACRO_DSN connects as, has no DDL rights.
#      ALTER TABLE macro_series_meta ADD COLUMN bls_id TEXT;
# 2. re-verify every BLS id by value against the data as it stands that day,
#    then store the map. --apply refuses unless all of them verify.
./venv/bin/python ../dashboards-bls-provisional/tools/bls_map.py --apply \
    ../dashboards-bls-provisional/tools/research/bls_map_$(date +%F).csv
# 3. merge and restamp
git merge bls-provisional && python3 tools/stamp_assets.py
# 4. prove it
./venv/bin/python -m macro.validate && ./venv/bin/python macro/export.py
./venv/bin/python tools/coverage.py && python3 tools/keycheck.py
~/.venvs/shot/bin/python tools/clipcheck.py
git worktree remove ../dashboards-bls-provisional
```

The first release that exercises it is JOLTS on 29 September. Good looks
like `provisional from the BLS API, pending FRED:` in the log on the first
poll, "Early figures from the BLS API, pending FRED" in the stamp, polls
continuing, and then `changed:` and `backfill rc=0` for the same series once
FRED posts.

Then look, not just read: `tools/shoot.py --path us/inflation/ppi` (and
cpi, weekly-claims), the stamp dates in each bundle's `releases` block
(claims must read the 10th, state claims the 11th), the newest heatmap
column, CPI Table 1, PPI Table 6's weights. Run validate, coverage,
keycheck, clipcheck. When the Wayback Machine has the new tables (usually
within days), run `tools/reconcile.py` against them to prove the method
repeats at a release. Record it as findings section 4.7.

The session that wrote this was watching on hourly wake-ups. If you are a
new session, nothing was recorded past the 9th unless section 4.7 exists.

## Recorded, not changed — decisions for William

- **CPI and PPI Table 1 draw the twelve-month change from the seasonally
  adjusted index**, and say so. BLS's headline is unadjusted: July 2026
  reads 3.3 on the page where the release prints 3.4. Switching CPI to
  `CPIAUCNS`/`CUUR0000SA0L1E` (both held) would match the release; PPI
  would need `PPIFID`, not catalogued.
- **Nine SA rows of ECI Tables 1–3 and the ten unadjusted PPI headline
  groupings are not held**; none is drawn. Adding them is an ingest.
- Labour Costs draws 24–25 years with no window in its headers; Table 4
  leads with the quarterly ECI on purpose.
- Claims Table 9 lists states in postal-code order.
- Payroll Table 21's grey line is deliberate; Table 28's title wraps.
- The three lagging CPI items (`SS53031`, `SSFV031A`, `SEMC04`) are out of
  every measure except `SEMC04`, which stays as the only representation of
  its residual; gaps are handled by date.

## Loose ends, none blocking

- **74 series are dead at source** (45 Productivity, 23 PPI, 4 CPI, 2 ECI),
  confirmed against BLS. Nothing to recover; none is drawn.
- **`frb.wage_tracker` has no calendar rows, correctly**: FRED publishes no
  forward dates for it; the sweep picks it up within a day.
- **The flatness check is quiet and calibrated**: three panels carry
  `data-span="intended: …"`.
- **The dead-man's switch is proven end to end**; re-test with
  `MAX_AGE_HOURS=0 ops/dashboards-timer-check`, then run it bare.
- **`~/bigricebowl` still has an unpushed commit** (the EverOS pin) plus
  older uncommitted deletions that are not mine.
- Screenshots from the design review are in `logs/shots/review/` (175
  files, gitignored); the raw reconciliation runs and Wayback tables are in
  the session scratchpad only.

## October 2025 is permanently empty, and that is settled

The shutdown stopped field collection and BLS will not collect the October
reference period retroactively. All 59 household-survey series lost it, 439
of 469 monthly CPI series lost it, 201 of 202 establishment series kept it.
Nothing interpolates across it; the bundles keep the hole as a null slot.
Expect it again in **October 2026**, when the hole becomes the base of the
twelve-month change. Traps 4 and 22.

## Commands

```bash
cd ~/dashboards && set -a && . .env && set +a
./venv/bin/python -m macro.validate                 # 38/38
./venv/bin/python macro/export.py                   # re-export without ingesting
./venv/bin/python tools/coverage.py                 # 100% on all seven
python3 tools/keycheck.py                           # static, runs anywhere
~/.venvs/shot/bin/python tools/clipcheck.py         # overflow + collision, both widths
~/.venvs/shot/bin/python tools/shoot.py --path us/inflation/cpi [--element cHead]
./venv/bin/python tools/staleness.py                # 74 overdue, 0 actionable
./venv/bin/python tools/reconcile.py cpi --asof 2026-09-12 --items cu.item cpi.t01.htm cpi.t02.htm
tail -f logs/refresh.log
systemctl --user list-timers 'macro-refresh-*'
```

Fetching a BLS table for `reconcile.py` (bls.gov refuses the VPS):

```bash
curl -sL --compressed -o cpi.t02.htm \
  "https://web.archive.org/web/2026id_/https://www.bls.gov/news.release/cpi.t02.htm"
```

Before committing any document, read `git diff --stat` (trap 56). This file
was written whole and is about 12 KB; if it is ever 15 MB, that is the trap,
not a handoff.
