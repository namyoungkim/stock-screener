-- 009_create_rls.sql
-- Row Level Security 정책

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
