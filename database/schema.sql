-- schema.sql
-- ------------
-- Creates the database schema for storing prediction history.
--
--   psql -U postgres -c "CREATE DATABASE digit_recognition;"
--   psql -U postgres -d digit_recognition -f database/schema.sql
--
-- Safe to re-run: every statement is idempotent, so upgrading from the
-- older 3-column version of the table just adds the new columns.

CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    predicted_digit SMALLINT      NOT NULL CHECK (predicted_digit BETWEEN 0 AND 9),
    confidence      REAL          NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- NEW: where the image came from ('canvas' drawn in the Swing app, or 'upload')
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'upload';

-- NEW: the digit the user says it really was (feedback loop). NULL = no feedback yet.
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS corrected_digit SMALLINT
    CHECK (corrected_digit IS NULL OR corrected_digit BETWEEN 0 AND 9);

-- NEW: the full 10-class probability vector, stored as JSON text
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS probabilities TEXT;

CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_digit ON predictions (predicted_digit);
