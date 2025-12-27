-- Add MACD columns to metrics table
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS macd DECIMAL(10, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS macd_signal DECIMAL(10, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS macd_histogram DECIMAL(10, 4);

COMMENT ON COLUMN metrics.macd IS 'MACD Line (12-day EMA - 26-day EMA)';
COMMENT ON COLUMN metrics.macd_signal IS 'Signal Line (9-day EMA of MACD)';
COMMENT ON COLUMN metrics.macd_histogram IS 'MACD Histogram (MACD - Signal)';
