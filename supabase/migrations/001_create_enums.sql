-- 001_create_enums.sql
-- 스키마에서 사용할 ENUM 타입 정의

-- 시장 타입 (US, KOSPI, KOSDAQ)
CREATE TYPE market_type AS ENUM ('US', 'KOSPI', 'KOSDAQ');

-- 분기 타입 (Q1-Q4, FY=연간)
CREATE TYPE quarter_type AS ENUM ('Q1', 'Q2', 'Q3', 'Q4', 'FY');

-- 알림 연산자 타입
CREATE TYPE operator_type AS ENUM ('<', '<=', '=', '>=', '>');
