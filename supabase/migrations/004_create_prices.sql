-- 004_create_prices.sql
-- 일별 주가 및 시가총액 테이블

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
