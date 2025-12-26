-- 002_create_companies.sql
-- 회사 마스터 테이블 (US/KR 통합)

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
