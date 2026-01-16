-- Migration: Fix SECURITY DEFINER to SECURITY INVOKER
-- Date: 2026-01-16
-- Description: View를 SECURITY INVOKER로 재생성하여 RLS 정책이 쿼리 사용자에게 적용되도록 함

-- 기존 뷰 삭제
DROP VIEW IF EXISTS company_latest_metrics;

-- security_invoker = true로 뷰 재생성
-- 이렇게 하면 뷰 쿼리 시 쿼리하는 사용자의 권한으로 실행됨 (RLS 정책 적용)
CREATE VIEW company_latest_metrics
WITH (security_invoker = true) AS
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

COMMENT ON VIEW company_latest_metrics IS '최신 지표가 포함된 회사 정보 (스크리닝용)';
