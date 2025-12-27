-- 005_create_metrics.sql
-- 투자 지표 테이블 (스크리닝 핵심)

CREATE TABLE metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 기준일
    date DATE NOT NULL,

    -- Valuation Ratios (가치평가)
    pe_ratio NUMERIC(12, 4),            -- P/E (주가수익비율)
    pb_ratio NUMERIC(12, 4),            -- P/B (주가순자산비율)
    ps_ratio NUMERIC(12, 4),            -- P/S (주가매출비율)
    ev_ebitda NUMERIC(12, 4),           -- EV/EBITDA
    ev_sales NUMERIC(12, 4),            -- EV/Sales
    peg_ratio NUMERIC(12, 4),           -- PEG 비율

    -- Profitability (수익성)
    roe NUMERIC(8, 4),                  -- 자기자본이익률
    roa NUMERIC(8, 4),                  -- 총자산이익률
    roic NUMERIC(8, 4),                 -- 투자자본이익률
    gross_margin NUMERIC(8, 4),         -- 매출총이익률
    operating_margin NUMERIC(8, 4),     -- 영업이익률
    net_margin NUMERIC(8, 4),           -- 순이익률

    -- Financial Health (재무건전성)
    debt_equity NUMERIC(12, 4),         -- 부채비율
    current_ratio NUMERIC(12, 4),       -- 유동비율
    quick_ratio NUMERIC(12, 4),         -- 당좌비율
    interest_coverage NUMERIC(12, 4),   -- 이자보상배율

    -- Cash Flow (현금흐름)
    fcf_yield NUMERIC(8, 4),            -- FCF 수익률
    operating_cf_margin NUMERIC(8, 4),  -- 영업현금흐름마진

    -- Dividend (배당)
    dividend_yield NUMERIC(8, 4),       -- 배당수익률
    payout_ratio NUMERIC(8, 4),         -- 배당성향

    -- Growth (성장성) - YoY
    revenue_growth_yoy NUMERIC(8, 4),   -- 매출 성장률 (전년대비)
    earnings_growth_yoy NUMERIC(8, 4),  -- 이익 성장률 (전년대비)

    -- Growth (성장성) - 3Y CAGR
    revenue_growth_3y NUMERIC(8, 4),    -- 매출 3년 CAGR
    earnings_growth_3y NUMERIC(8, 4),   -- 이익 3년 CAGR

    -- Graham Number (가치투자)
    eps NUMERIC(20, 4),                 -- 주당순이익 (Earnings Per Share)
    book_value_per_share NUMERIC(20, 4),-- 주당순자산 (Book Value Per Share)
    graham_number NUMERIC(20, 4),       -- 그레이엄 숫자 = sqrt(22.5 * EPS * BVPS)

    -- 메타데이터
    data_source VARCHAR(50),            -- 'yfinance', 'calculated'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_company_metrics_date UNIQUE (company_id, date)
);

COMMENT ON TABLE metrics IS '계산된 투자 지표 (스크리닝용)';
COMMENT ON COLUMN metrics.date IS '지표 계산 기준일';
