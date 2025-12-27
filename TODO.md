# TODO - 개선 필요 사항

> 마지막 업데이트: 2025-12-28

## 0. 최근 완료 (2025-12-28)

- [x] **문서 구조 개선** - 문서 통합 및 간결화
  - 커밋: `86ea589`
  - `value-investing-screener-roadmap.md` 삭제 (역할 완료)
  - `ROADMAP.md` 간결화 (141줄 → 64줄)
  - `.claude/rules/vision.md` 생성 (AI 비전 + Phase 4,5)
  - `.claude/rules/data-policy.md` 생성 (Google Drive 백업 정책)
- [x] **Rate Limiting 구현** - API 요청 횟수 제한
  - 커밋: `d4a1009`
  - 라이브러리: slowapi
  - 스크리닝: 30/minute, 일반 API: 100/minute
- [x] **다크모드 구현** - Tailwind class 전략
  - 커밋: `d4a1009`
  - ThemeContext, ThemeToggle 컴포넌트
  - 헤더에 🌙/☀️ 토글 버튼
  - localStorage에 테마 저장
- [x] **다크모드 전체 페이지 적용**
  - 커밋: `192b904` - 종목 상세 페이지
  - 커밋: `3a13c29` - 워치리스트 페이지
  - 커밋: `0e73a60` - UserMenu 드롭다운
- [x] **프론트엔드 스타일 가이드 문서화**
  - 커밋: `3a13c29`
  - `.claude/rules/frontend.md` - 다크모드 색상 매핑, 컴포넌트 패턴
- [x] **Screen API 버그 수정** - Rate limiting 파라미터 충돌
  - 커밋: `7dfcde5`
- [x] **CORS 보안 강화** - 특정 도메인만 허용
  - 커밋: `c857b5b`
- [x] **문서화** - README, SECURITY.md 업데이트
  - 커밋: `02f2c97`
- [x] **알림 시스템 구현** - 지표 기반 알림 CRUD
  - 백엔드: `/api/alerts` CRUD API (models, service, routes)
  - 프론트엔드: `/alerts` 페이지, `AlertForm` 컴포넌트
  - 종목 상세 페이지에서 알림 추가 가능
  - 알림 조건: 지표 + 연산자 + 값 (예: P/E <= 15)

## 이전 완료 (2025-12-27)

- [x] **Graham Number 구현** - EPS, BPS, Graham Number 수집 및 표시
  - 커밋: `ecdd2ea`
  - 수집기: US/KR 모두 적용
  - DB: `metrics` 테이블에 `eps`, `book_value_per_share`, `graham_number` 컬럼 추가
  - 프론트엔드: 상세 페이지에서 표시
- [x] **테스트 모드 개선** - `--test` 실행 시 CSV 파일에 `_test` 접미사 추가
- [x] **RSI 지표 추가** - 14일 기준 RSI 계산 및 표시
  - 커밋: `81d4520`
  - 수집기: 히스토리 데이터로 RSI 계산
  - DB: `metrics` 테이블에 `rsi` 컬럼 추가
  - 프론트엔드: 30 이하 과매도(초록), 70 이상 과매수(빨강) 표시
- [x] **거래량 변화율 추가** - 20일 평균 대비 거래량 변화율 계산
  - 커밋: `53e4bfd`
  - 수집기: 20일 평균 거래량 대비 변화율(%) 계산
  - DB: `metrics` 테이블에 `volume_change` 컬럼 추가
  - 프론트엔드: +100% 빨강, +50% 주황, -50% 파랑 표시
- [x] **MACD 지표 추가** - 이동평균수렴확산 지표
  - 커밋: `576fa00`
  - 수집기: MACD Line (12일-26일 EMA), Signal (9일 EMA), Histogram 계산
  - DB: `metrics` 테이블에 `macd`, `macd_signal`, `macd_histogram` 컬럼 추가
  - 프론트엔드: 히스토그램 양수 초록(상승), 음수 빨강(하락) 표시
- [x] **볼린저 밴드 추가** - 변동성 밴드 지표
  - 커밋: `7f5909d`
  - 수집기: Upper/Middle/Lower Band (20일 SMA ± 2×표준편차), %B 계산
  - DB: `metrics` 테이블에 `bb_upper`, `bb_middle`, `bb_lower`, `bb_percent` 컬럼 추가
  - 프론트엔드: %B 100% 이상 과매수(빨강), 0% 이하 과매도(초록) 표시
- [x] **MFI 지표 추가** - 자금흐름지수 (거래량 가중 RSI)
  - 커밋: `65dc337`
  - 수집기: Typical Price × Volume 기반 MFI 계산
  - DB: `metrics` 테이블에 `mfi` 컬럼 추가
  - 프론트엔드: 20 이하 과매도(초록), 80 이상 과매수(빨강) 표시
- [x] **Watchlist 기능 구현** - GitHub OAuth 인증 + 워치리스트
  - 커밋: `b12ecbe`
  - 백엔드: Supabase JWT 검증 (ES256/JWKS), Watchlist CRUD API
  - 프론트엔드: GitHub OAuth 로그인, AuthContext, WatchlistButton, /watchlist 페이지
  - UX 개선: 페이지네이션 추가, 컨테이너 너비 확장 (max-w-screen-xl)

---

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

- [x] Supabase SQL Editor에서 schema.sql 실행 필요
- [x] .env에 SUPABASE_URL, SUPABASE_KEY 설정 필요

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

- [x] 워치리스트 API (`/api/watchlist`)
- [x] 알림 API (`/api/alerts`)
- [x] 사용자 인증 (Supabase Auth)

---

## 4. 보안

- [x] CORS 설정 수정 (`"*"` → 특정 도메인만 허용)
- [ ] API 키 노출 방지 (환경변수 검증)
- [x] Rate limiting 미들웨어 추가 (slowapi)
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
- [x] Supabase Auth 연동 (GitHub OAuth)
- [x] 워치리스트 페이지
- [x] 알림 페이지 + AlertForm 컴포넌트
- [x] 페이지네이션 컴포넌트
- [x] 다크모드 (Tailwind class 전략)
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
1. ~~Supabase Auth 연동~~ ✅ 완료
2. ~~워치리스트 기능~~ ✅ 완료
3. 알림 시스템

### P3 - 낮음
1. ~~다크모드~~ ✅ 완료
2. i18n (한/영)
3. ~~프로덕션 보안 강화 (CORS 제한)~~ ✅ 완료
4. 성능 최적화
5. ~~배포 (Vercel, Render)~~ ✅ 완료

---

## 🔮 지표 확장 계획 (의사결정 필요)

> 데이터 수집이 오래 걸리므로, 필요한 지표를 미리 설계하여 한 번에 수집하는 것이 효율적.

### 현재 수집 중 (표시만 추가 필요)
| 지표 | 필드명 | 작업 |
|------|--------|------|
| ~~52주 최고~~ | `fifty_two_week_high` | ✅ 완료 |
| ~~52주 최저~~ | `fifty_two_week_low` | ✅ 완료 |
| ~~Beta~~ | `beta` | ✅ 완료 |

### 옵션 1: yfinance 직접 제공 (권장 - 빠름) ✅ 완료
- ~~50일/200일 이동평균~~: `fiftyDayAverage`, `twoHundredDayAverage` ✅ 완료
- ~~PEG Ratio~~: `trailingPegRatio` ✅ 완료
- 수집 시간 거의 증가 없음

### 옵션 2: Phase 2 (타이밍 지표) ✅ 완료
- ~~RSI (14일)~~: `rsi` ✅ 완료
- ~~거래량 변화율~~: `volume_change` ✅ 완료
- 수집 시간 증가

### 옵션 3: Phase 3 전체 (고급 분석) ✅ 완료
- ~~MACD~~: `macd`, `macd_signal`, `macd_histogram` ✅ 완료
- ~~볼린저 밴드~~: `bb_upper`, `bb_middle`, `bb_lower`, `bb_percent` ✅ 완료
- ~~Money Flow Index~~: `mfi` ✅ 완료
- 히스토리 60일 필요
- 수집 시간 대폭 증가

### 결정 사항
- [ ] 어떤 옵션으로 진행할지 결정
- [ ] 데이터 수집 전 스키마 미리 설계
