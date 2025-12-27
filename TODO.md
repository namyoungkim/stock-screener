# TODO - 개선 필요 사항

> 마지막 업데이트: 2025-12-27

## 1. 데이터 파이프라인

### US 수집기 (`data-pipeline/collectors/us_stocks.py`)

- [x] Supabase 저장 로직 구현
- [x] Rate limiting 대응 (sleep, 재시도 로직)
- [x] `--dry-run` 모드 추가 (DB 없이 테스트)
- [x] 진행률 로깅 개선
- [ ] 배치 처리 (실패 시 이어서 수집)
- [ ] 데이터 검증 (null 체크, 이상치 필터링)

### KR 수집기 (`data-pipeline/collectors/kr_stocks.py`)

- [x] `get_krx_tickers()` 구현 (pykrx 활용)
- [x] corp_code 조회 로직 구현 (종목코드 → DART corp_code 매핑)
- [x] `get_financial_statements()` 실제 데이터 추출 로직 구현
- [x] Supabase 저장 로직 구현
- [x] `--dry-run` 모드 추가 (DB 없이 테스트)

### 공통

- [ ] `data-pipeline/collectors/base.py` - 공통 저장/에러 처리 모듈
- [ ] `data-pipeline/processors/` - 데이터 정제 로직

---

## 2. 데이터베이스

### Supabase 스키마 생성

- [x] `companies` 테이블 (id, ticker, name, market, sector, currency)
- [x] `financials` 테이블 (company_id, fiscal_year, quarter, revenue, ...)
- [x] `prices` 테이블 (company_id, date, close, market_cap)
- [x] `metrics` 테이블 (계산된 지표)
- [x] `watchlist` 테이블 (user_id, company_id, added_at)
- [x] `alerts` 테이블 (user_id, company_id, metric, operator, value)
- [x] `company_latest_metrics` 뷰 (스크리닝용)
- [x] 통합 스키마 파일 (`supabase/schema.sql`)

### 인덱스 및 최적화

- [x] ticker, market 조합 인덱스
- [x] company_id + date 조합 인덱스
- [x] 스크리닝용 부분 인덱스 (pe_ratio, pb_ratio, roe, dividend_yield)

### 적용 상태

- [ ] Supabase SQL Editor에서 schema.sql 실행 필요
- [ ] .env에 SUPABASE_URL, SUPABASE_KEY 설정 필요

---

## 3. 백엔드 API

### 핵심 구현

- [x] `backend/app/core/config.py` - 환경변수 설정 관리
- [x] `backend/app/core/database.py` - Supabase 연결
- [x] `backend/app/models/stock.py` - Pydantic 모델
- [x] `backend/app/services/screener.py` - 스크리닝 로직

### API 엔드포인트

- [x] `GET /api/stocks` - 종목 목록 조회
- [x] `GET /api/stocks/{ticker}` - 종목 상세 조회
- [x] `POST /api/screen` - 스크리닝 (필터 + 프리셋)
- [x] `GET /api/screen/presets` - 프리셋 전략 목록

### 프리셋 전략

- [x] Graham Classic (P/E < 15, P/B < 1.5, D/E < 0.5)
- [x] Buffett Quality (ROE > 15%, Net Margin > 10%)
- [x] Dividend Value (배당 > 3%)
- [x] Deep Value (P/B < 1, P/E < 10)

### 추가 필요

- [ ] 워치리스트 API (`/api/watchlist`)
- [ ] 알림 API (`/api/alerts`)
- [ ] 사용자 인증 (Supabase Auth)

---

## 4. 보안

- [ ] CORS 설정 수정 (`"*"` → 특정 도메인만 허용)
- [ ] API 키 노출 방지 (환경변수 검증)
- [ ] Rate limiting 미들웨어 추가
- [ ] 입력 검증 강화

---

## 5. 디스코드 봇

- [x] `discord-bot/bot/main.py` - 봇 메인 코드
- [x] `discord-bot/bot/api.py` - 백엔드 API 클라이언트
- [x] `/stock {ticker}` 명령어 - 종목 정보 조회
- [x] `/screen {preset}` 명령어 - 프리셋 스크리닝
- [x] `/presets` 명령어 - 프리셋 목록
- [x] `/search {query}` 명령어 - 종목 검색
- [ ] `/watch {ticker}` 명령어 - 워치리스트 추가
- [ ] `/watchlist` 명령어 - 워치리스트 조회
- [ ] `/alert {ticker} {metric} {operator} {value}` 명령어

---

## 6. 프론트엔드 (Next.js)

- [x] 프로젝트 초기 세팅 (Next.js 14, Tailwind, React Query)
- [x] 레이아웃 및 네비게이션 (Header, Footer)
- [x] API 클라이언트 (`src/lib/api.ts`)
- [x] 스크리너 페이지 (메인)
- [x] 종목 상세 페이지 (`/stocks/[ticker]`)
- [x] StockTable, FilterPanel 컴포넌트
- [ ] Supabase Auth 연동
- [ ] 워치리스트 페이지
- [ ] 다크모드
- [ ] 한/영 i18n

---

## 7. 인프라 및 배포

- [x] Vercel 배포 설정 (프론트엔드) - https://stock-screener-inky.vercel.app
- [x] Render 배포 설정 (백엔드) - https://stock-screener-api-c0kc.onrender.com
- [ ] 도메인 연결
- [x] GitHub Actions 워크플로우 개선 (병렬 실행, 수동 트리거 옵션)
- [x] Supabase CLI 설정 (`supabase/config.toml`)

---

## 우선순위

### P0 - 즉시 (완료)
1. ~~Supabase 테이블 생성~~ ✅
2. ~~US 수집기 저장 로직~~ ✅
3. ~~KR 티커 확보 방법 결정~~ ✅ (pykrx 사용)
4. ~~백엔드 API 기본 구조~~ ✅
5. ~~프론트엔드 MVP~~ ✅
6. ~~디스코드 봇 기본 기능~~ ✅

### P1 - 높음 (다음 단계)
1. Supabase 스키마 적용 (SQL Editor에서 실행)
2. 환경 변수 설정 (.env)
3. 데이터 수집 실행 (US/KR)
4. 통합 테스트

### P2 - 중간
1. Supabase Auth 연동
2. 워치리스트 기능
3. 알림 시스템

### P3 - 낮음
1. 다크모드
2. i18n (한/영)
3. 프로덕션 보안 강화 (CORS 제한)
4. 성능 최적화
5. ~~배포 (Vercel, Render)~~ ✅ 완료
