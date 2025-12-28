-- Migration: Add Technical Indicators to metrics table
-- Run this in Supabase SQL Editor

-- Technical Indicators (기술적 지표)
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS rsi NUMERIC(8, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS mfi NUMERIC(8, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS volume_change NUMERIC(8, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS macd NUMERIC(12, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS macd_signal NUMERIC(12, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS macd_histogram NUMERIC(12, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_upper NUMERIC(16, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_middle NUMERIC(16, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_lower NUMERIC(16, 4);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS bb_percent NUMERIC(8, 4);

-- Add comments
COMMENT ON COLUMN metrics.rsi IS 'RSI (14일 상대강도지수)';
COMMENT ON COLUMN metrics.mfi IS 'Money Flow Index (자금흐름지수)';
COMMENT ON COLUMN metrics.volume_change IS '거래량 변화율 (20일 평균 대비 %)';
COMMENT ON COLUMN metrics.macd IS 'MACD (EMA12 - EMA26)';
COMMENT ON COLUMN metrics.macd_signal IS 'MACD Signal (9일 EMA)';
COMMENT ON COLUMN metrics.macd_histogram IS 'MACD Histogram (MACD - Signal)';
COMMENT ON COLUMN metrics.bb_upper IS 'Bollinger Band Upper (SMA20 + 2σ)';
COMMENT ON COLUMN metrics.bb_middle IS 'Bollinger Band Middle (SMA20)';
COMMENT ON COLUMN metrics.bb_lower IS 'Bollinger Band Lower (SMA20 - 2σ)';
COMMENT ON COLUMN metrics.bb_percent IS 'Bollinger %B ((Price - Lower) / (Upper - Lower))';

-- Create indexes for commonly filtered technical indicators
CREATE INDEX IF NOT EXISTS idx_metrics_rsi ON metrics(rsi) WHERE rsi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_metrics_mfi ON metrics(mfi) WHERE mfi IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_metrics_bb_percent ON metrics(bb_percent) WHERE bb_percent IS NOT NULL;

-- Update the view to include technical indicators
DROP VIEW IF EXISTS company_latest_metrics;

CREATE VIEW company_latest_metrics AS
SELECT
    c.id,
    c.ticker,
    c.name,
    c.market,
    c.sector,
    c.industry,
    c.currency,
    m.date AS metrics_date,
    m.pe_ratio,
    m.pb_ratio,
    m.ps_ratio,
    m.ev_ebitda,
    m.roe,
    m.roa,
    m.gross_margin,
    m.net_margin,
    m.debt_equity,
    m.current_ratio,
    m.fcf_yield,
    m.dividend_yield,
    m.payout_ratio,
    m.fifty_two_week_high,
    m.fifty_two_week_low,
    m.beta,
    m.fifty_day_average,
    m.two_hundred_day_average,
    m.peg_ratio,
    m.revenue_growth_yoy,
    m.earnings_growth_yoy,
    -- Technical Indicators
    m.rsi,
    m.mfi,
    m.volume_change,
    m.macd,
    m.macd_signal,
    m.macd_histogram,
    m.bb_upper,
    m.bb_middle,
    m.bb_lower,
    m.bb_percent,
    p.close AS latest_price,
    p.market_cap
FROM companies c
LEFT JOIN LATERAL (
    SELECT * FROM metrics
    WHERE company_id = c.id
    ORDER BY date DESC
    LIMIT 1
) m ON true
LEFT JOIN LATERAL (
    SELECT * FROM prices
    WHERE company_id = c.id
    ORDER BY date DESC
    LIMIT 1
) p ON true
WHERE c.is_active = true;

COMMENT ON VIEW company_latest_metrics IS '최신 지표가 포함된 회사 정보 (스크리닝용)';
