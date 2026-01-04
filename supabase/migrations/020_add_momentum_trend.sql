-- Add momentum and trend columns to metrics table
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS price_to_52w_high_pct NUMERIC(8, 2);
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS ma_trend NUMERIC(8, 2);

-- Add indexes for the new columns
CREATE INDEX IF NOT EXISTS idx_metrics_price_to_52w_high_pct ON metrics (price_to_52w_high_pct) WHERE price_to_52w_high_pct IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_metrics_ma_trend ON metrics (ma_trend) WHERE ma_trend IS NOT NULL;

-- Add comments
COMMENT ON COLUMN metrics.price_to_52w_high_pct IS '52주 고가 대비 현재가 (%). 90% 이상이면 신고가 근접';
COMMENT ON COLUMN metrics.ma_trend IS 'MA 추세 (MA50/MA200 - 1) * 100. 양수면 골든크로스, 음수면 데드크로스';

-- Drop and recreate the company_latest_metrics view with new columns
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
    c.is_active,
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
    m.dividend_yield,
    m.peg_ratio,
    m.beta,
    m.eps,
    m.book_value_per_share,
    m.graham_number,
    m.fifty_two_week_high,
    m.fifty_two_week_low,
    m.fifty_day_average,
    m.two_hundred_day_average,
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
    m.price_to_52w_high_pct,
    m.ma_trend,
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
