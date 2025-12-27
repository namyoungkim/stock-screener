-- Add moving average columns to metrics table
ALTER TABLE metrics
ADD COLUMN IF NOT EXISTS fifty_day_average NUMERIC(16, 4),
ADD COLUMN IF NOT EXISTS two_hundred_day_average NUMERIC(16, 4);

COMMENT ON COLUMN metrics.fifty_day_average IS '50일 이동평균';
COMMENT ON COLUMN metrics.two_hundred_day_average IS '200일 이동평균';
