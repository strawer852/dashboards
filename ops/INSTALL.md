# Restoring the nightly backup

Prepared 3 September 2026. Every command here needs root, which is why none of
it has been applied — the files are staged in this directory and nothing on the
system has been touched.

## What was wrong

`/usr/local/bin/bigricebowl-backup` last wrote its log on **18 June 2026**.
Nothing schedules it any more: no systemd timer, no `/etc/cron.d` entry, and no
reference in `/etc/cron*`. Root's own crontab could not be read without sudo, so
that is the one place left to check.

Three separate faults, all fixed in the staged script:

1. **It dumps `investment`**, a database dropped in the July teardown. Only
   `essays` and `macro` exist now. The new script enumerates live databases from
   the server instead, so adding or dropping one can never break it again.
2. **`fail()` exits, and the dump ran first.** One missing database therefore did
   not merely lose that dump — it prevented `restic` from running at all, so
   every file path in the list went unbacked because of a database name. Dumps
   are now best-effort, restic always runs, and the script reports failure at the
   end.
3. **`/home/strawer/dashboards` was never in the restic paths.** It holds the raw
   archive — the only copy of the BLS vintages, since that API serves no
   point-in-time history — and a git repo with **no remote**. 5.7 MB excluding
   the venv.

And a fourth thing that is not a fault in the script but is the reason this went
unnoticed for ten weeks: **a script can report its own failure, but nothing
reports its absence.** `bigricebowl-backup-check` looks at the age of the newest
snapshot rather than at the script, and alarms if it exceeds 48 hours.

## Install

Staged files are in `ops/`. Steps 1 and 2 are read-only; nothing changes until
step 3.

**1. Confirm the restic repository is still reachable and its credentials still
work.** I could not do this: `/etc/restic/env` is `root:root` mode 600. Until
this passes, nothing below is worth doing.

```bash
sudo bash -c 'source /etc/restic/env && restic snapshots --latest 5'
```

**2. Check whether root's crontab still references the backup** — the one place
I could not look, and the likeliest explanation for why it stopped.

```bash
sudo crontab -l | grep -i backup
```

**3. Keep the current script, then install the new ones.**

```bash
sudo cp -a /usr/local/bin/bigricebowl-backup /usr/local/bin/bigricebowl-backup.pre-2026-09-03
sudo install -m 755 ops/bigricebowl-backup /usr/local/bin/bigricebowl-backup
sudo install -m 755 ops/bigricebowl-backup-check /usr/local/bin/bigricebowl-backup-check
sudo install -m 644 ops/bigricebowl-backup.service ops/bigricebowl-backup.timer \
                    ops/bigricebowl-backup-check.service ops/bigricebowl-backup-check.timer \
                    /etc/systemd/system/
sudo systemctl daemon-reload
```

**4. Run it once by hand and read the log before trusting a timer with it.**

```bash
sudo /usr/local/bin/bigricebowl-backup ; echo "exit: $?"
sudo tail -40 /var/log/bigricebowl-backup.log
```

Expect a dump line for `essays` and for `macro`, restic reporting files added,
and a snapshot listed at the end. A non-zero exit prints what went wrong and
sends Telegram.

**5. Enable the timers.**

```bash
sudo systemctl enable --now bigricebowl-backup.timer bigricebowl-backup-check.timer
systemctl list-timers 'bigricebowl-*'
```

**6. Prove the alarm path works**, rather than assuming it. The Telegram token in
`~/bigricebowl/.env` has not been exercised since June and may have been revoked.

```bash
sudo MAX_AGE_HOURS=0 /usr/local/bin/bigricebowl-backup-check ; echo "exit: $?"
```

That forces the age check to fail and should put a message on your phone. If
nothing arrives, the alarm is decorative and the whole exercise repeats itself
in a few months — fix the token before relying on it.

## Rollback

```bash
sudo systemctl disable --now bigricebowl-backup.timer bigricebowl-backup-check.timer
sudo cp -a /usr/local/bin/bigricebowl-backup.pre-2026-09-03 /usr/local/bin/bigricebowl-backup
```

## What deliberately did NOT change

The retention policy is the original's, unaltered: `--keep-daily 14
--keep-weekly 12 --keep-monthly 36 --prune`. With `--prune` that step deletes
data, so the window is yours to decide, not something to tidy while fixing an
unrelated fault. I had first staged 7/5/12 and caught it before it shipped; it
would have destroyed snapshots you meant to keep. The Sunday `restic check` is
kept as it was too.

Only the failure handling around them changed: both now record a problem and let
the script run to the end, instead of calling `fail()` and exiting.
