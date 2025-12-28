-- Migration: Fix Numeric Precision for High-Value Stocks
-- Run this in Supabase SQL Editor
-- Issue: Some columns have NUMERIC(10, 4) which limits to < 1,000,000
-- Fix: Increase to NUMERIC(16, 4) for price columns, NUMERIC(12, 4) for ratios

-- ============================================
-- Step 1: Drop the view (required before altering columns)
-- ============================================

DROP VIEW IF EXISTS company_latest_metrics;

-- ============================================
-- Step 2: Price-related columns (한국 고가주 대응)
-- NUMERIC(16, 4) allows up to 999,999,999,999.9999
-- ============================================

ALTER TABLE metrics ALTER COLUMN fifty_two_week_high TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN fifty_two_week_low TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN fifty_day_average TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN two_hundred_day_average TYPE NUMERIC(16, 4);

-- Bollinger Bands (가격 기반)
ALTER TABLE metrics ALTER COLUMN bb_upper TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN bb_middle TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN bb_lower TYPE NUMERIC(16, 4);

-- MACD (가격 차이 기반, 고가주는 값이 클 수 있음)
ALTER TABLE metrics ALTER COLUMN macd TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN macd_signal TYPE NUMERIC(16, 4);
ALTER TABLE metrics ALTER COLUMN macd_histogram TYPE NUMERIC(16, 4);

-- ============================================
-- Step 3: Ratio columns (극단적 값 대응)
-- NUMERIC(12, 4) allows up to 99,999,999.9999
-- ============================================

ALTER TABLE metrics ALTER COLUMN pe_ratio TYPE NUMERIC(12, 4);
ALTER TABLE metrics ALTER COLUMN pb_ratio TYPE NUMERIC(12, 4);
ALTER TABLE metrics ALTER COLUMN ps_ratio TYPE NUMERIC(12, 4);
ALTER TABLE metrics ALTER COLUMN ev_ebitda TYPE NUMERIC(12, 4);
ALTER TABLE metrics ALTER COLUMN debt_equity TYPE NUMERIC(12, 4);
ALTER TABLE metrics ALTER COLUMN current_ratio TYPE NUMERIC(12, 4);

-- ============================================
-- Step 4: Recreate the view
-- ============================================

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
