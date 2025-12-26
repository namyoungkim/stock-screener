-- 006_create_watchlist.sql
-- 사용자 관심 종목 테이블

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
