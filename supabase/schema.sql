-- Stock Screener Supabase Schema
-- 이 파일을 Supabase SQL Editor에서 실행하세요
-- https://supabase.com/dashboard/project/YOUR_PROJECT/sql/new

-- ============================================
-- 001: ENUM 타입 정의
-- ============================================

-- 시장 타입 (US, KOSPI, KOSDAQ)
CREATE TYPE market_type AS ENUM ('US', 'KOSPI', 'KOSDAQ');

-- 분기 타입 (Q1-Q4, FY=연간)
CREATE TYPE quarter_type AS ENUM ('Q1', 'Q2', 'Q3', 'Q4', 'FY');

-- 알림 연산자 타입
CREATE TYPE operator_type AS ENUM ('<', '<=', '=', '>=', '>');

-- ============================================
-- 002: 회사 마스터 테이블
-- ============================================

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 식별자
    ticker VARCHAR(20) NOT NULL,
    corp_code VARCHAR(10),              -- 한국 DART corp_code (미국은 NULL)

    -- 기본 정보
    name VARCHAR(255) NOT NULL,
    name_en VARCHAR(255),               -- 영문명 (한국 종목용)
    market market_type NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    currency VARCHAR(10) DEFAULT 'USD',

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_ticker_market UNIQUE (ticker, market)
);

COMMENT ON TABLE companies IS '미국/한국 상장 기업 마스터 테이블';
COMMENT ON COLUMN companies.corp_code IS '한국 DART 시스템의 고유 기업 코드';
COMMENT ON COLUMN companies.market IS 'US=미국, KOSPI=한국 유가증권, KOSDAQ=한국 코스닥';

-- ============================================
-- 003: 재무제표 테이블
-- ============================================

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

-- ============================================
-- 004: 일별 주가 테이블
-- ============================================

CREATE TABLE prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 날짜
    date DATE NOT NULL,

    -- 가격 정보
    open NUMERIC(16, 4),
    high NUMERIC(16, 4),
    low NUMERIC(16, 4),
    close NUMERIC(16, 4) NOT NULL,
    adjusted_close NUMERIC(16, 4),
    volume BIGINT,

    -- 시가총액
    market_cap NUMERIC(20, 2),
    enterprise_value NUMERIC(20, 2),

    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_company_date UNIQUE (company_id, date)
);

COMMENT ON TABLE prices IS '일별 주가 및 시가총액 데이터';

-- ============================================
-- 005: 투자 지표 테이블
-- ============================================

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

    -- Price Range (가격 범위)
    fifty_two_week_high NUMERIC(16, 4), -- 52주 최고가
    fifty_two_week_low NUMERIC(16, 4),  -- 52주 최저가

    -- Risk (리스크)
    beta NUMERIC(8, 4),                 -- 베타 (시장 대비 변동성)

    -- Moving Averages (이동평균)
    fifty_day_average NUMERIC(16, 4),   -- 50일 이동평균
    two_hundred_day_average NUMERIC(16, 4), -- 200일 이동평균

    -- Technical Indicators (기술적 지표)
    rsi NUMERIC(8, 4),                  -- RSI (14일)
    mfi NUMERIC(8, 4),                  -- Money Flow Index
    volume_change NUMERIC(8, 4),        -- 거래량 변화율 (20일 평균 대비 %)
    macd NUMERIC(12, 4),                -- MACD
    macd_signal NUMERIC(12, 4),         -- MACD Signal (9일 EMA)
    macd_histogram NUMERIC(12, 4),      -- MACD Histogram
    bb_upper NUMERIC(16, 4),            -- Bollinger Band Upper (SMA20 + 2σ)
    bb_middle NUMERIC(16, 4),           -- Bollinger Band Middle (SMA20)
    bb_lower NUMERIC(16, 4),            -- Bollinger Band Lower (SMA20 - 2σ)
    bb_percent NUMERIC(8, 4),           -- Bollinger %B

    -- Growth (성장성) - YoY
    revenue_growth_yoy NUMERIC(8, 4),   -- 매출 성장률 (전년대비)
    earnings_growth_yoy NUMERIC(8, 4),  -- 이익 성장률 (전년대비)

    -- Growth (성장성) - 3Y CAGR
    revenue_growth_3y NUMERIC(8, 4),    -- 매출 3년 CAGR
    earnings_growth_3y NUMERIC(8, 4),   -- 이익 3년 CAGR

    -- 메타데이터
    data_source VARCHAR(50),            -- 'yfinance', 'calculated'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_company_metrics_date UNIQUE (company_id, date)
);

COMMENT ON TABLE metrics IS '계산된 투자 지표 (스크리닝용)';
COMMENT ON COLUMN metrics.date IS '지표 계산 기준일';

-- ============================================
-- 006: 사용자 관심 종목 테이블
-- ============================================

CREATE TABLE watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 추가 정보
    added_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,                         -- 사용자 메모
    target_price NUMERIC(16, 4),        -- 목표가

    -- 제약조건
    CONSTRAINT unique_user_company UNIQUE (user_id, company_id)
);

COMMENT ON TABLE watchlist IS '사용자별 관심 종목 목록';

-- ============================================
-- 007: 사용자 알림 조건 테이블
-- ============================================

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 알림 조건
    metric VARCHAR(50) NOT NULL,        -- 'pe_ratio', 'pb_ratio', 'price' 등
    operator operator_type NOT NULL,
    value NUMERIC(16, 4) NOT NULL,

    -- 상태
    is_active BOOLEAN DEFAULT true,
    triggered_at TIMESTAMPTZ,           -- 마지막 트리거 시점
    triggered_count INTEGER DEFAULT 0,

    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_alert_condition UNIQUE (user_id, company_id, metric, operator, value)
);

COMMENT ON TABLE alerts IS '사용자별 알림 조건 설정';
COMMENT ON COLUMN alerts.metric IS '모니터링할 지표 (metrics 테이블 컬럼명 또는 price)';

-- ============================================
-- 008: 인덱스
-- ============================================

-- companies 테이블 인덱스
CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_market ON companies(market);
CREATE INDEX idx_companies_sector ON companies(sector);
CREATE INDEX idx_companies_ticker_market ON companies(ticker, market);
CREATE INDEX idx_companies_active ON companies(is_active) WHERE is_active = true;

-- financials 테이블 인덱스
CREATE INDEX idx_financials_company_id ON financials(company_id);
CREATE INDEX idx_financials_fiscal_year ON financials(fiscal_year DESC);
CREATE INDEX idx_financials_company_year ON financials(company_id, fiscal_year DESC);
CREATE INDEX idx_financials_company_year_quarter ON financials(company_id, fiscal_year DESC, quarter);

-- prices 테이블 인덱스
CREATE INDEX idx_prices_company_id ON prices(company_id);
CREATE INDEX idx_prices_date ON prices(date DESC);
CREATE INDEX idx_prices_company_date ON prices(company_id, date DESC);

-- metrics 테이블 인덱스
CREATE INDEX idx_metrics_company_id ON metrics(company_id);
CREATE INDEX idx_metrics_date ON metrics(date DESC);
CREATE INDEX idx_metrics_company_date ON metrics(company_id, date DESC);

-- 스크리닝용 부분 인덱스 (자주 사용되는 필터)
CREATE INDEX idx_metrics_pe_ratio ON metrics(pe_ratio) WHERE pe_ratio IS NOT NULL;
CREATE INDEX idx_metrics_pb_ratio ON metrics(pb_ratio) WHERE pb_ratio IS NOT NULL;
CREATE INDEX idx_metrics_roe ON metrics(roe) WHERE roe IS NOT NULL;
CREATE INDEX idx_metrics_dividend_yield ON metrics(dividend_yield) WHERE dividend_yield IS NOT NULL;

-- watchlist 테이블 인덱스
CREATE INDEX idx_watchlist_user_id ON watchlist(user_id);
CREATE INDEX idx_watchlist_company_id ON watchlist(company_id);

-- alerts 테이블 인덱스
CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_company_id ON alerts(company_id);
CREATE INDEX idx_alerts_active ON alerts(is_active) WHERE is_active = true;

-- ============================================
-- 009: Row Level Security 정책
-- ============================================

-- RLS 활성화
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE financials ENABLE ROW LEVEL SECURITY;
ALTER TABLE prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- companies: 인증된 사용자에게 읽기 허용
CREATE POLICY "Public read access for companies"
    ON companies FOR SELECT
    TO authenticated
    USING (true);

-- financials: 인증된 사용자에게 읽기 허용
CREATE POLICY "Public read access for financials"
    ON financials FOR SELECT
    TO authenticated
    USING (true);

-- prices: 인증된 사용자에게 읽기 허용
CREATE POLICY "Public read access for prices"
    ON prices FOR SELECT
    TO authenticated
    USING (true);

-- metrics: 인증된 사용자에게 읽기 허용
CREATE POLICY "Public read access for metrics"
    ON metrics FOR SELECT
    TO authenticated
    USING (true);

-- watchlist: 본인 데이터만 CRUD
CREATE POLICY "Users can view own watchlist"
    ON watchlist FOR SELECT
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can insert own watchlist"
    ON watchlist FOR INSERT
    TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can update own watchlist"
    ON watchlist FOR UPDATE
    TO authenticated
    USING ((SELECT auth.uid()) = user_id)
    WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can delete own watchlist"
    ON watchlist FOR DELETE
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

-- alerts: 본인 데이터만 CRUD
CREATE POLICY "Users can view own alerts"
    ON alerts FOR SELECT
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can insert own alerts"
    ON alerts FOR INSERT
    TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can update own alerts"
    ON alerts FOR UPDATE
    TO authenticated
    USING ((SELECT auth.uid()) = user_id)
    WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can delete own alerts"
    ON alerts FOR DELETE
    TO authenticated
    USING ((SELECT auth.uid()) = user_id);

-- ============================================
-- 010: 트리거 및 뷰
-- ============================================

-- updated_at 자동 갱신 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 각 테이블에 트리거 적용
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_financials_updated_at
    BEFORE UPDATE ON financials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_metrics_updated_at
    BEFORE UPDATE ON metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alerts_updated_at
    BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 최신 지표가 포함된 회사 정보 뷰 (스크리닝용)
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

-- =============================================
-- 사용자 프리셋 테이블
-- =============================================

CREATE TABLE user_presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    filters JSONB NOT NULL,  -- MetricFilter[] 배열: [{metric, operator, value}, ...]
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_user_preset_name UNIQUE (user_id, name)
);

COMMENT ON TABLE user_presets IS '사용자 정의 스크리닝 프리셋';
COMMENT ON COLUMN user_presets.filters IS 'MetricFilter 배열 (JSON): [{metric: string, operator: string, value: number}]';

-- 인덱스
CREATE INDEX idx_user_presets_user_id ON user_presets(user_id);

-- RLS 정책
ALTER TABLE user_presets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own presets" ON user_presets
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own presets" ON user_presets
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own presets" ON user_presets
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own presets" ON user_presets
    FOR DELETE USING (auth.uid() = user_id);

-- updated_at 트리거
CREATE TRIGGER update_user_presets_updated_at
    BEFORE UPDATE ON user_presets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
