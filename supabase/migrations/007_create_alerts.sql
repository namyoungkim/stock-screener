-- 007_create_alerts.sql
-- 사용자 알림 조건 테이블

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
