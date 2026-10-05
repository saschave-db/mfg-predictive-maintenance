-- Lakebase OLTP tables written by the app (work orders) and read by the simulator (fault injection).
-- Schema pdm_ops is replicated to Unity Catalog with Lakehouse Sync, so REPLICA IDENTITY FULL is set.
CREATE SCHEMA IF NOT EXISTS pdm_ops;

CREATE TABLE IF NOT EXISTS pdm_ops.work_orders (
  work_order_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  station_id             TEXT NOT NULL,
  plant_id               TEXT NOT NULL,
  line_id                TEXT NOT NULL,
  priority               TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
  status                 TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'completed', 'cancelled')),
  failure_probability    NUMERIC(5, 4),
  risk_band              TEXT,
  top_signal             TEXT,
  description            TEXT,
  assigned_technician_id TEXT,
  created_by             TEXT NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at           TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS work_orders_station_idx ON pdm_ops.work_orders (station_id, status);
ALTER TABLE pdm_ops.work_orders REPLICA IDENTITY FULL;

CREATE TABLE IF NOT EXISTS pdm_ops.sim_commands (
  command_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  command       TEXT NOT NULL CHECK (command IN ('inject_fault', 'repair')),
  station_id    TEXT NOT NULL,
  failure_mode  TEXT,
  requested_by  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'applied')),
  requested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sim_commands_pending_idx ON pdm_ops.sim_commands (status) WHERE status = 'pending';
ALTER TABLE pdm_ops.sim_commands REPLICA IDENTITY FULL;

-- Synced (read-only) tables land in pdm_live; created by the sync pipelines.
CREATE SCHEMA IF NOT EXISTS pdm_live;
