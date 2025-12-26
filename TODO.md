# TODO - 개선 필요 사항

> 마지막 업데이트: 2024-12-26

## 1. 데이터 파이프라인

### US 수집기 (`data-pipeline/collectors/us_stocks.py`)

- [ ] Supabase 저장 로직 구현
- [ ] Rate limiting 대응 (sleep, 재시도 로직)
- [ ] 배치 처리 (실패 시 이어서 수집)
- [ ] 진행률 로깅 개선
- [ ] 데이터 검증 (null 체크, 이상치 필터링)

### KR 수집기 (`data-pipeline/collectors/kr_stocks.py`)

- [ ] `get_krx_tickers()` 구현 (pykrx 또는 KRX 데이터 활용)
- [ ] corp_code 조회 로직 구현 (종목코드 → DART corp_code 매핑)
- [ ] `get_financial_statements()` 실제 데이터 추출 로직 구현
- [ ] Supabase 저장 로직 구현

### 공통

- [ ] `data-pipeline/collectors/base.py` - 공통 저장/에러 처리 모듈
- [ ] `data-pipeline/processors/` - 데이터 정제 로직

---

## 2. 데이터베이스

### Supabase 스키마 생성

- [ ] `companies` 테이블 (id, ticker, name, market, sector, currency)
- [ ] `financials` 테이블 (company_id, fiscal_year, quarter, revenue, ...)
- [ ] `prices` 테이블 (company_id, date, close, market_cap)
- [ ] `metrics` 테이블 (계산된 지표)
- [ ] `watchlist` 테이블 (user_id, company_id, added_at)
- [ ] `alerts` 테이블 (user_id, company_id, metric, operator, value)

### 인덱스 및 최적화

- [ ] ticker, market 조합 인덱스
- [ ] company_id + date 조합 인덱스

---

## 3. 백엔드 API

### 핵심 구현

- [ ] `backend/app/core/config.py` - 환경변수 설정 관리
- [ ] `backend/app/core/database.py` - Supabase 연결
- [ ] `backend/app/models/stock.py` - Pydantic 모델
- [ ] `backend/app/services/screener.py` - 스크리닝 로직

### API 엔드포인트

- [ ] `GET /api/stocks` - 종목 목록 조회
- [ ] `GET /api/stocks/{ticker}` - 종목 상세 조회
- [ ] `POST /api/screen` - 스크리닝 (필터 + 프리셋)
- [ ] `GET /api/presets` - 프리셋 전략 목록

### 지표 계산 엔진

- [ ] Valuation: P/E, P/B, P/S, EV/EBITDA
- [ ] Profitability: ROE, ROA, Net Margin, Gross Margin
- [ ] Financial Health: Debt/Equity, Current Ratio
- [ ] Cash Flow: FCF, FCF Yield

### 프리셋 전략

- [ ] Graham Classic (P/E < 15, P/B < 1.5, D/E < 0.5)
- [ ] Buffett Quality (ROE > 15%, 연속 수익)
- [ ] Dividend Value (배당 > 3%, 배당성향 < 60%)
- [ ] Deep Value (P/B < 1, P/E < 10, FCF > 0)

---

## 4. 보안

- [ ] CORS 설정 수정 (`"*"` → 특정 도메인만 허용)
- [ ] API 키 노출 방지 (환경변수 검증)
- [ ] Rate limiting 미들웨어 추가
- [ ] 입력 검증 강화

---

## 5. 디스코드 봇

- [ ] `discord-bot/bot.py` - 봇 메인 코드
- [ ] `/screen {preset}` 명령어
- [ ] `/stock {ticker}` 명령어
- [ ] `/watch {ticker}` 명령어
- [ ] `/watchlist` 명령어
- [ ] `/alert {ticker} {metric} {operator} {value}` 명령어

---

## 6. 프론트엔드 (Next.js)

- [ ] 프로젝트 초기 세팅 (Next.js 14, Tailwind, next-intl)
- [ ] Supabase Auth 연동
- [ ] 레이아웃 및 네비게이션
- [ ] 스크리너 페이지
- [ ] 종목 상세 페이지
- [ ] 워치리스트 페이지
- [ ] 다크모드
- [ ] 한/영 i18n

---

## 7. 인프라 및 배포

- [ ] Vercel 배포 설정 (프론트엔드)
- [ ] Railway 배포 설정 (백엔드, 봇)
- [ ] 도메인 연결
- [ ] GitHub Actions 실패 알림 추가

---

## 우선순위

### P0 - 즉시 (1주차 완료 필수)
1. Supabase 테이블 생성
2. US 수집기 저장 로직
3. KR 티커 확보 방법 결정

### P1 - 높음 (2주차)
1. 백엔드 API 기본 구조
2. 지표 계산 엔진
3. 스크리닝 엔드포인트

### P2 - 중간 (3-4주차)
1. 프론트엔드 MVP
2. 디스코드 봇 기본 기능
3. 워치리스트

### P3 - 낮음 (5주차 이후)
1. 알림 시스템
2. 프로덕션 보안 강화
3. 성능 최적화
