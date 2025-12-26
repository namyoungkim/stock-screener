-- 008_create_indexes.sql
-- 성능 최적화를 위한 인덱스

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
