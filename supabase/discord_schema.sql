-- Discord Bot Specific Tables
-- 디스코드 봇 전용 테이블 (웹 인증과 분리)
-- 이 파일을 Supabase SQL Editor에서 실행하세요

-- ============================================
-- Discord 워치리스트 테이블
-- ============================================

CREATE TABLE discord_watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discord_user_id VARCHAR(20) NOT NULL,  -- Discord snowflake ID
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 추가 정보
    added_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,
    target_price NUMERIC(16, 4),

    -- 제약조건
    CONSTRAINT unique_discord_user_company UNIQUE (discord_user_id, company_id)
);

COMMENT ON TABLE discord_watchlist IS '디스코드 사용자별 관심 종목 목록';
COMMENT ON COLUMN discord_watchlist.discord_user_id IS 'Discord 사용자 ID (snowflake)';

-- ============================================
-- Discord 알림 조건 테이블
-- ============================================

CREATE TABLE discord_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discord_user_id VARCHAR(20) NOT NULL,  -- Discord snowflake ID
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- 알림 조건
    metric VARCHAR(50) NOT NULL,
    operator operator_type NOT NULL,
    value NUMERIC(16, 4) NOT NULL,

    -- 상태
    is_active BOOLEAN DEFAULT true,
    triggered_at TIMESTAMPTZ,
    triggered_count INTEGER DEFAULT 0,

    -- 메타데이터
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT unique_discord_alert_condition UNIQUE (discord_user_id, company_id, metric, operator, value)
);

COMMENT ON TABLE discord_alerts IS '디스코드 사용자별 알림 조건 설정';
COMMENT ON COLUMN discord_alerts.discord_user_id IS 'Discord 사용자 ID (snowflake)';
COMMENT ON COLUMN discord_alerts.metric IS '모니터링할 지표 (metrics 테이블 컬럼명 또는 latest_price)';

-- ============================================
-- 인덱스
-- ============================================

CREATE INDEX idx_discord_watchlist_user_id ON discord_watchlist(discord_user_id);
CREATE INDEX idx_discord_watchlist_company_id ON discord_watchlist(company_id);

CREATE INDEX idx_discord_alerts_user_id ON discord_alerts(discord_user_id);
CREATE INDEX idx_discord_alerts_company_id ON discord_alerts(company_id);
CREATE INDEX idx_discord_alerts_active ON discord_alerts(is_active) WHERE is_active = true;

-- ============================================
-- RLS 정책 (서비스 키 사용 시 우회됨)
-- ============================================

ALTER TABLE discord_watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE discord_alerts ENABLE ROW LEVEL SECURITY;

-- 서비스 역할에 대한 전체 액세스 허용
CREATE POLICY "Service role full access to discord_watchlist"
    ON discord_watchlist FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access to discord_alerts"
    ON discord_alerts FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================
-- 트리거
-- ============================================

CREATE TRIGGER update_discord_alerts_updated_at
    BEFORE UPDATE ON discord_alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
