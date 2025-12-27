-- Add MFI (Money Flow Index) column to metrics table
ALTER TABLE metrics ADD COLUMN IF NOT EXISTS mfi DECIMAL(10, 2);

-- Add index for MFI-based screening
CREATE INDEX IF NOT EXISTS idx_metrics_mfi ON metrics (mfi) WHERE mfi IS NOT NULL;

-- Update view to include MFI
DROP VIEW IF EXISTS company_latest_metrics;
CREATE VIEW company_latest_metrics AS
SELECT DISTINCT ON (c.id)
    c.id,
    c.ticker,
    c.name,
    c.market,
    c.sector,
    c.industry,
    c.currency,
    m.pe_ratio,
    m.forward_pe,
    m.pb_ratio,
    m.ps_ratio,
    m.ev_ebitda,
    m.roe,
    m.roa,
    m.debt_equity,
    m.current_ratio,
    m.gross_margin,
    m.net_margin,
    m.dividend_yield,
    m.eps,
    m.book_value_per_share,
    m.graham_number,
    m.fifty_two_week_high,
    m.fifty_two_week_low,
    m.fifty_day_average,
    m.two_hundred_day_average,
    m.peg_ratio,
    m.beta,
    m.rsi,
    m.volume_change,
    m.macd,
    m.macd_signal,
    m.macd_histogram,
    m.bb_upper,
    m.bb_middle,
    m.bb_lower,
    m.bb_percent,
    m.mfi,
    p.close AS current_price,
    p.market_cap,
    m.date AS metrics_date
FROM companies c
LEFT JOIN metrics m ON c.id = m.company_id
LEFT JOIN prices p ON c.id = p.company_id AND p.date = m.date
ORDER BY c.id, m.date DESC NULLS LAST;
