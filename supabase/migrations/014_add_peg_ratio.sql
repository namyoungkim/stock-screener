-- Add PEG ratio column to metrics table
-- Note: peg_ratio column already exists in schema.sql, this is for existing databases
ALTER TABLE metrics
ADD COLUMN IF NOT EXISTS peg_ratio NUMERIC(12, 4);

COMMENT ON COLUMN metrics.peg_ratio IS 'PEG 비율 (P/E ÷ 예상 성장률)';
