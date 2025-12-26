-- 003_create_financials.sql
-- 재무제표 테이블 (분기/연간)

CREATE TABLE financials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 기간 정보
    fiscal_year INTEGER NOT NULL,
    quarter quarter_type NOT NULL,      -- FY = 연간 데이터
    report_date DATE,                   -- 보고서 발표일

    -- 손익계산서 (Income Statement)
    revenue NUMERIC(20, 2),             -- 매출액
    cost_of_revenue NUMERIC(20, 2),     -- 매출원가
    gross_profit NUMERIC(20, 2),        -- 매출총이익
    operating_income NUMERIC(20, 2),    -- 영업이익
    net_income NUMERIC(20, 2),          -- 당기순이익
    ebitda NUMERIC(20, 2),              -- EBITDA

    -- 재무상태표 (Balance Sheet)
    total_assets NUMERIC(20, 2),        -- 총자산
    total_liabilities NUMERIC(20, 2),   -- 총부채
    total_equity NUMERIC(20, 2),        -- 자본총계
    current_assets NUMERIC(20, 2),      -- 유동자산
    current_liabilities NUMERIC(20, 2), -- 유동부채
    long_term_debt NUMERIC(20, 2),      -- 장기부채
    cash_and_equivalents NUMERIC(20, 2),-- 현금 및 현금성자산

    -- 현금흐름표 (Cash Flow Statement)
    operating_cash_flow NUMERIC(20, 2), -- 영업활동현금흐름
    investing_cash_flow NUMERIC(20, 2), -- 투자활동현금흐름
    financing_cash_flow NUMERIC(20, 2), -- 재무활동현금흐름
    free_cash_flow NUMERIC(20, 2),      -- 잉여현금흐름
    capex NUMERIC(20, 2),               -- 자본적지출

    -- 주당 지표
    shares_outstanding BIGINT,          -- 발행주식수
    eps NUMERIC(12, 4),                 -- 주당순이익
    dps NUMERIC(12, 4),                 -- 주당배당금
    bvps NUMERIC(12, 4),                -- 주당순자산

    -- 메타데이터
    data_source VARCHAR(50),            -- 'yfinance', 'dart', 'fmp'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_company_period UNIQUE (company_id, fiscal_year, quarter)
);

COMMENT ON TABLE financials IS '분기/연간 재무제표 데이터';
COMMENT ON COLUMN financials.quarter IS 'Q1-Q4=분기, FY=연간 합산';
