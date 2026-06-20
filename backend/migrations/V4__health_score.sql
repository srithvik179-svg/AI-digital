-- Phase 5: Add health_score and health_category to telemetry_snapshots
-- These are computed at ingest time by the Health Score Engine.

ALTER TABLE telemetry_snapshots
    ADD COLUMN IF NOT EXISTS health_score    REAL         DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS health_category VARCHAR(20)  DEFAULT NULL;

-- Index for fast alert queries (e.g. "find all critical snapshots for device X")
CREATE INDEX IF NOT EXISTS idx_snapshots_health_category
    ON telemetry_snapshots (device_id, health_category, timestamp DESC);

-- Index for range queries on score (e.g. "score < 50")
CREATE INDEX IF NOT EXISTS idx_snapshots_health_score
    ON telemetry_snapshots (health_score);

COMMENT ON COLUMN telemetry_snapshots.health_score    IS '0-100 composite health score computed by Phase 5 engine';
COMMENT ON COLUMN telemetry_snapshots.health_category IS 'Healthy | Warning | Critical';
