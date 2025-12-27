-- Add volume_change column to metrics table
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS volume_change DECIMAL(10, 2);

COMMENT ON COLUMN metrics.volume_change IS 'Volume change rate compared to 20-day average (%)';
