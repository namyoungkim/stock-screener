-- Add RSI column to metrics table
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS rsi DECIMAL(6, 2);

COMMENT ON COLUMN metrics.rsi IS 'Relative Strength Index (14-day)';
