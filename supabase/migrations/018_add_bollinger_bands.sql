-- Add Bollinger Bands columns to metrics table
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_upper DECIMAL(10, 2);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_middle DECIMAL(10, 2);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_lower DECIMAL(10, 2);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_percent DECIMAL(6, 2);

COMMENT ON COLUMN metrics.bb_upper IS 'Bollinger Band Upper (20-day SMA + 2*StdDev)';
COMMENT ON COLUMN metrics.bb_middle IS 'Bollinger Band Middle (20-day SMA)';
COMMENT ON COLUMN metrics.bb_lower IS 'Bollinger Band Lower (20-day SMA - 2*StdDev)';
COMMENT ON COLUMN metrics.bb_percent IS 'Bollinger %B indicator (0-100, position within bands)';
