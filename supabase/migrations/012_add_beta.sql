-- Add beta column to metrics table
ALTER TABLE metrics
ADD COLUMN IF NOT EXISTS beta NUMERIC(8, 4);

COMMENT ON COLUMN metrics.beta IS '베타 (시장 대비 변동성)';
