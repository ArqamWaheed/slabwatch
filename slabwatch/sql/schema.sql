-- Slabwatch schema for Postgres / Tiger Cloud. Core tables only; extension-dependent pieces
-- (timescaledb hypertable, pgvector column + index) are added by store.init_db() if available.

CREATE TABLE IF NOT EXISTS households (
  id              text PRIMARY KEY,
  name            text,
  reference_no    text,                 -- 14-digit PITC ref; personal data, never logged
  disco           text DEFAULT 'lesco',
  threshold       real DEFAULT 200,
  penalty_months  int  DEFAULT 6,
  cycle_days      int  DEFAULT 30,
  lat             real DEFAULT 31.55,
  lon             real DEFAULT 74.34,
  meta            jsonb DEFAULT '{}'::jsonb,   -- n_acs, people, area_sqft (optional)
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS readings (
  household_id  text NOT NULL REFERENCES households(id),
  ts            timestamptz NOT NULL,
  reading_kwh   double precision NOT NULL,   -- cumulative meter register
  source        text NOT NULL,               -- photo | manual | bill
  confidence    real,
  display_label text,
  PRIMARY KEY (household_id, ts)
);

CREATE TABLE IF NOT EXISTS cycles (
  household_id   text NOT NULL REFERENCES households(id),
  start_date     date NOT NULL,
  end_date       date,
  start_reading  double precision,
  billed_units   double precision,           -- from the bill, when it arrives
  bill_month     text,                       -- YYYY-MM
  source         text DEFAULT 'bill',        -- bill | readings
  PRIMARY KEY (household_id, start_date)
);

CREATE TABLE IF NOT EXISTS forecasts (
  household_id  text NOT NULL REFERENCES households(id),
  ts            timestamptz NOT NULL DEFAULT now(),
  cycle_start   date NOT NULL,
  days_elapsed  int NOT NULL,
  units_so_far  double precision NOT NULL,
  p10 double precision, p50 double precision, p90 double precision,
  p_cross       double precision,
  threshold     real,
  verdict       text,
  backend       text,
  quantiles     jsonb,                       -- {"levels": [...], "units": [...]}
  scored_error  double precision,            -- filled when the bill arrives: billed - p50
  PRIMARY KEY (household_id, ts)
);

CREATE TABLE IF NOT EXISTS tariff_docs (
  id          bigserial PRIMARY KEY,
  url         text UNIQUE NOT NULL,
  title       text,
  snippet     text,
  published   text,
  source      text,
  query       text,
  fetched_at  timestamptz DEFAULT now(),
  tsv         tsvector GENERATED ALWAYS AS (
                to_tsvector('english', coalesce(title, '') || ' ' || coalesce(snippet, ''))) STORED
);
CREATE INDEX IF NOT EXISTS tariff_docs_tsv ON tariff_docs USING gin (tsv);
