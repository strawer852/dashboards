-- macro — schema for the BigRiceBowl data dashboards
-- Applied to database `macro` on the VPS postgres (timescaledb-ha:pg17).
--
-- Deliberately PLAIN TABLES, not hypertables. The retired `investment` stack
-- used create_hypertable() on macro_observations, and that is what produced its
-- worst bug: TimescaleDB chunk-constraint inference stopped
-- `ON CONFLICT (cols) DO NOTHING` from ever firing, leaving 650,093 duplicate
-- rows in 1,784,464 — of which 4,191 held DIVERGENT values under the same key.
-- On a plain table the conflict guard behaves normally and the bug class is
-- gone. At 33 series the chunking bought nothing anyway; the old row count came
-- from 144 series across four regions. Revisit only if this passes a few million
-- rows, which the backfill will measure.

BEGIN;

-- ── releases and their calendar ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS macro_releases (
    release_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    agency       TEXT NOT NULL,
    cadence      TEXT NOT NULL,          -- monthly, weekly
    url          TEXT
);

CREATE TABLE IF NOT EXISTS macro_release_dates (
    release_id   TEXT        NOT NULL REFERENCES macro_releases(release_id) ON DELETE CASCADE,
    release_at   TIMESTAMPTZ NOT NULL,   -- embargo lift, in UTC
    ref_period   DATE,                   -- the period being reported
    status       TEXT        NOT NULL DEFAULT 'scheduled',
    PRIMARY KEY (release_id, release_at)
);

CREATE INDEX IF NOT EXISTS idx_reldates_next ON macro_release_dates(release_at);

-- ── macro_series_meta ────────────────────────────────────────────────────────
-- Column set carried over from the retired catalog (migration 0018), which is
-- richer than a from-scratch design: companion_series_id pairs each SA series
-- with its NSA twin, and `dataset` already models the release grouping.
CREATE TABLE IF NOT EXISTS macro_series_meta (
    series_id            TEXT PRIMARY KEY,
    source               TEXT        NOT NULL,          -- fred, bls, ...
    title                TEXT        NOT NULL,
    frequency            TEXT        NOT NULL,          -- D W M Q A
    country              TEXT,
    category             TEXT,                          -- employment, prices, ...
    importance           INT         CHECK (importance BETWEEN 1 AND 10),
    -- FALSE means: hold and refresh this series, but never sweep it into a
    -- dashboard bundle. Ingested for analysis rather than display. A spec can
    -- still ask for it by name in include_series.
    publish              BOOLEAN     NOT NULL DEFAULT TRUE,
    seasonal_adjustment  TEXT,                          -- SA, NSA, N/A
    companion_series_id  TEXT,                          -- the SA<->NSA twin
    validation_mode      TEXT        NOT NULL DEFAULT 'zscore',
    pub_lag_days         INT,                           -- staleness detection
    staleness_mode       TEXT,
    originator           TEXT,                          -- publishing agency
    dataset              TEXT,                          -- release name as the old catalog held it
    -- Real FK to the release, so a dashboard resolves its "as of" stamp by key
    -- rather than by matching a human-readable string.
    release_id           TEXT        REFERENCES macro_releases(release_id),
    source_url           TEXT,
    unit                 TEXT,

    -- The three-mode vintage system, from FINDINGS_revision_handling.md.
    -- Held as data rather than a code-side constant, so a mode can never drift
    -- silently the way FIXHAI's did.
    --   from_row       ALFRED realtime_start; true revision history
    --   fetch_date     no usable ALFRED history; new row only when value changes
    --   observation_dt anchor only; NO revision tracking, NOT point-in-time safe
    vintage_mode         TEXT        NOT NULL DEFAULT 'from_row'
                         CHECK (vintage_mode IN ('from_row','fetch_date','observation_dt')),

    last_check           TIMESTAMPTZ,
    last_release         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_meta_release  ON macro_series_meta(release_id);
CREATE INDEX IF NOT EXISTS idx_meta_category ON macro_series_meta(category);
CREATE INDEX IF NOT EXISTS idx_meta_country  ON macro_series_meta(country);

-- ── macro_observations ───────────────────────────────────────────────────────
-- The primary key is the whole point: every revision of an observation lands as
-- its own row, so revision history is never overwritten. Verified in the old
-- system on PAYEMS (Jan 2026: 158627 -> 158558 -> 158592) and on the February
-- annual benchmark, which restates the entire back history as one vintage.
CREATE TABLE IF NOT EXISTS macro_observations (
    series_id      TEXT        NOT NULL REFERENCES macro_series_meta(series_id) ON DELETE CASCADE,
    source         TEXT        NOT NULL,
    observation_dt DATE        NOT NULL,
    vintage_dt     TIMESTAMPTZ NOT NULL,
    value          NUMERIC,                             -- NULL = published as missing
    unit           TEXT,
    PRIMARY KEY (series_id, observation_dt, vintage_dt)
);

CREATE INDEX IF NOT EXISTS idx_obs_series_dt ON macro_observations(series_id, observation_dt DESC);
CREATE INDEX IF NOT EXISTS idx_obs_vintage   ON macro_observations(series_id, vintage_dt DESC);

-- ── read views ───────────────────────────────────────────────────────────────
-- What the charts read: the latest vintage of each observation.
CREATE OR REPLACE VIEW macro_observations_current AS
SELECT DISTINCT ON (series_id, observation_dt)
       series_id, source, observation_dt, value, unit, vintage_dt
FROM   macro_observations
ORDER  BY series_id, observation_dt, vintage_dt DESC;

-- What was said on the day. The revision overlay is the difference between them.
CREATE OR REPLACE VIEW macro_observations_first AS
SELECT DISTINCT ON (series_id, observation_dt)
       series_id, source, observation_dt, value, unit, vintage_dt
FROM   macro_observations
ORDER  BY series_id, observation_dt, vintage_dt ASC;

COMMENT ON VIEW macro_observations_first IS
  'First published value per observation. Honest only for vintage_mode=from_row; '
  'an observation_dt anchor carries no true first-availability date and is not '
  'point-in-time safe (look-ahead leakage if used in a backtest).';

COMMIT;
