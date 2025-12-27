-- Add 52 week high/low columns to metrics table
ALTER TABLE metrics
ADD COLUMN IF NOT EXISTS fifty_two_week_high NUMERIC(16, 4),
ADD COLUMN IF NOT EXISTS fifty_two_week_low NUMERIC(16, 4);

COMMENT ON COLUMN metrics.fifty_two_week_high IS '52주 최고가';
COMMENT ON COLUMN metrics.fifty_two_week_low IS '52주 최저가';
