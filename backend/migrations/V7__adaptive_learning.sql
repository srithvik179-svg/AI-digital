-- Phase 53: Adaptive Learning Feedback Table Migration
-- Stores user ratings for AI recommendations, chatbot answers, RCA, and predictions

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id                  VARCHAR(64)  PRIMARY KEY,
    device_id           VARCHAR(128) NOT NULL,
    feedback_type       VARCHAR(32)  NOT NULL,
    rating              SMALLINT     NOT NULL CHECK (rating IN (-1, 1)),
    query_text          TEXT,
    response_text       TEXT,
    recommendation_id   VARCHAR(128),
    comments            TEXT,
    confidence_at_time  REAL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Indexes for efficient filtering and aggregation
CREATE INDEX IF NOT EXISTS idx_feedback_device ON recommendation_feedback (device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_type   ON recommendation_feedback (feedback_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON recommendation_feedback (rating, feedback_type);
