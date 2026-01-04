# TODO - 개선 필요 사항

> 마지막 업데이트: 2026-01-04

## 0. 최근 완료 (2026-01-01)

- [x] **프론트엔드 개선** (PR #15, #16, #17)
  - 검색 기능 버그 수정 (프리셋/필터 사용 시 검색어 무시 문제)
  - 모바일 햄버거 메뉴 구현 (Header.tsx)
  - URL 상태 관리 훅 구현 (useUrlParams.ts) - 브라우저 뒤로가기 지원
  - 필터 패널 토글 버튼 (모바일 반응형)
  - 한글 IME 입력 수정 (모바일 자음 중복 문제 해결)

## 0.1. 이전 완료 (2025-12-29)

- [x] **Phase 3.5: 투자 인사이트 (규칙 기반)**
  - 종합 투자 점수 계산 (`lib/scoring.ts`) - P/E, P/B, ROE, D/E, RSI, Graham, MA Trend, MACD 기반
  - 리스크 감지 시스템 (`lib/risks.ts`) - HIGH/MEDIUM 레벨 경고
  - 새 컴포넌트: `InvestmentSignal`, `ActionGuide`, `RiskAlert`, `WatchlistPrompt`
  - 종목 상세 페이지 통합 (워치리스트 종목: 전체 분석, 미등록: 워치리스트 유도)
  - 워치리스트 페이지 요약 표시 (점수, 신호, 리스크 배지)
- [x] **디스코드 봇 워치리스트/알림 연동**
  - 디스코드 전용 테이블 (`discord_watchlist`, `discord_alerts`)
  - 백엔드 API (`/api/discord/watchlist`, `/api/discord/alerts`)
  - 봇 명령어: `/watch`, `/unwatch`, `/watchlist`, `/alert`, `/alerts`, `/delalert`, `/togglealert`
  - 웹 인증과 별도로 Discord User ID 기반 동작
- [x] **입력 검증 강화** - MetricType Enum 화이트리스트, UUID/범위/길이 검증
- [x] **API 키 노출 방지** - 환경변수 검증, 로그 마스킹, DB 연결 검증

## 0.1. 이전 완료 (2025-12-28)

- [x] **워크플로우 일일 실행으로 변경**
  - 데이터 수집: 평일 매일 00:00 UTC (09:00 KST)
  - 백업: 평일 매일 01:00 UTC (10:00 KST)
  - 휴장일은 gracefully 스킵 (pykrx/yfinance 빈 데이터 반환)
- [x] **Google Drive 백업 OAuth 설정**
  - Service Account → OAuth 인증으로 변경 (개인 계정 호환)
  - Production 모드로 토큰 만료 방지
  - 백업 테스트 완료
- [x] **데이터 파이프라인 리팩토링** - 공통 모듈 추출 및 코드 최적화
  - `common/` 패키지 생성 (config, logging, retry, indicators, storage)
  - `collectors/base.py` - BaseCollector 추상 클래스
  - `processors/validators.py` - MetricsValidator 데이터 검증
  - 코드 47% 감소 (us_stocks: 1,190→632줄, kr_stocks: 1,329→607줄)
  - `--resume` 플래그 추가 (중단된 수집 이어서 실행)
- [x] **KR 수집기 DART 제거** - pykrx + yfinance로 완전 대체
  - 수집 시간: ~45분 → ~5분 (DART API 호출 제거)
  - pykrx: PER, PBR, EPS, BPS (벌크 다운로드)
  - yfinance: ROE, ROA, Margins, D/E, Current Ratio
  - DART_API_KEY 더 이상 필요 없음
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
- [x] **Advanced Filters 구현** - 커스텀 지표 필터링
  - 프론트엔드: `FilterPanel.tsx`에 Advanced Filters UI 추가
  - 20개 지표 지원 (Valuation, Profitability, Technical 등 카테고리별)
  - 필터 추가/삭제/적용/초기화 기능
  - Preset과 Custom Filters 동시 사용 가능
  - 필터 적용 개수 뱃지 표시
- [x] **프리셋 관리 페이지 구현** - `/presets` 페이지
  - 백엔드: `user_presets` 테이블, API CRUD (`/api/user-presets`)
  - 시스템 프리셋 목록 (Graham, Buffett 등) 표시
  - 사용자 커스텀 프리셋 CRUD (생성/조회/삭제)
  - 프리셋 클릭 시 메인 페이지에서 필터 적용

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
- [x] 배치 처리 (실패 시 이어서 수집) - `--resume` 플래그
- [x] 데이터 검증 (null 체크, 이상치 필터링) - MetricsValidator

### KR 수집기 (`data-pipeline/collectors/kr_stocks.py`)

- [x] `get_krx_tickers()` 구현 (pykrx 활용)
- [x] ~~corp_code 조회 로직 구현~~ (DART 제거됨)
- [x] ~~`get_financial_statements()` 실제 데이터 추출 로직 구현~~ (DART 제거됨)
- [x] pykrx 펀더멘탈 데이터 (PER, PBR, EPS, BPS)
- [x] yfinance 재무 지표 (ROE, ROA, Margins, D/E, Current Ratio)
- [x] Supabase 저장 로직 구현
- [x] `--dry-run` 모드 추가 (DB 없이 테스트)

### 공통

- [x] `data-pipeline/collectors/base.py` - BaseCollector 추상 클래스
- [x] `data-pipeline/common/` - 공통 모듈 패키지
  - `config.py` - 설정 상수
  - `logging.py` - 로거 + CollectionProgress
  - `retry.py` - @with_retry 데코레이터, RetryQueue
  - `indicators.py` - 기술적 지표 계산 함수
  - `storage.py` - StorageManager (Supabase + CSV)
- [x] `data-pipeline/processors/validators.py` - MetricsValidator 데이터 검증

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
- [x] API 키 노출 방지 (환경변수 검증)
  - 서버 시작 시 필수 환경변수 검증 (SUPABASE_URL, SUPABASE_KEY)
  - 프로덕션 환경에서 누락 시 서버 시작 실패
  - 로그에 민감한 정보 마스킹 (`mask_secret()`)
  - DB 연결 health check
- [x] Rate limiting 미들웨어 추가 (slowapi)
- [x] 입력 검증 강화
  - `MetricType` Enum으로 metric 필드 화이트리스트 (33개 지표)
  - 숫자 범위 제한 (`-1e12 ~ 1e12`)
  - 문자열 길이 제한 (notes: 1000자, description: 500자)
  - UUID v4 형식 검증 (company_id 등)
  - ticker 패턴 검증 (`^[A-Za-z0-9.\-]+$`)

---

## 4.5. Self-hosted Runner 설정 ✅

> EC2 Self-hosted Runner 설정 완료. 현재는 로컬 Mac에서 수동 실행 중.
> 가이드: `.claude/rules/self-hosted-runner.md`

---

## 5. 디스코드 봇

- [x] `discord-bot/bot/main.py` - 봇 메인 코드
- [x] `discord-bot/bot/api.py` - 백엔드 API 클라이언트
- [x] `/stock {ticker}` 명령어 - 종목 정보 조회
- [x] `/screen {preset}` 명령어 - 프리셋 스크리닝
- [x] `/presets` 명령어 - 프리셋 목록
- [x] `/search {query}` 명령어 - 종목 검색
- [x] `/watch {ticker}` 명령어 - 워치리스트 추가
- [x] `/unwatch {ticker}` 명령어 - 워치리스트 삭제
- [x] `/watchlist` 명령어 - 워치리스트 조회
- [x] `/alert {ticker} {metric} {operator} {value}` 명령어 - 알림 생성
- [x] `/alerts` 명령어 - 알림 목록 조회
- [x] `/delalert {alert_id}` 명령어 - 알림 삭제
- [x] `/togglealert {alert_id}` 명령어 - 알림 활성화/비활성화

> **참고**: 디스코드 봇은 웹 인증과 별도로 작동합니다. `supabase/discord_schema.sql`을 실행해야 합니다.
> **배포**: P3에서 진행. 상세 가이드: `.claude/rules/discord-bot-deployment.md`

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
- [x] 프리셋 관리 페이지 + PresetForm 컴포넌트

> **i18n**: P3에서 진행

---

## 7. 인프라 및 배포

- [x] Vercel 배포 설정 (프론트엔드) - https://stock-screener-inky.vercel.app
- [x] Render 배포 설정 (백엔드) - https://stock-screener-api-c0kc.onrender.com
- [x] GitHub Actions 워크플로우 개선 (병렬 실행, 수동 트리거 옵션)
- [x] Supabase CLI 설정 (`supabase/config.toml`)

> **도메인 연결**: P3에서 진행

---

## 우선순위 (PRD 기준)

> 문서 계층: `docs/PRD.md` → `ROADMAP.md` → `TODO.md`

### P0 - 완료
- ~~Phase 1-3: MVP ~ 워치리스트/알림~~ ✅
- ~~Phase 3.5: 투자 인사이트~~ ✅

### P1 - Phase 4: AI 분석

> 아키텍처: `docs/PRD.md` 8절 참조

1. ~~US 티커 유니버스 확장 (~2,800 → ~6,000)~~ ✅
   - [x] NASDAQ FTP 연동 (`get_all_us_tickers()` 재작성)
   - [x] CLI 옵션 추가 (`--index-only`)
   - [x] 품질검사 업데이트 (`US_MAJOR_TICKERS` 재정의)
   - [x] 문서 업데이트
   > 완료: `.claude/rules/ticker-strategy.md`

2. OpenSearch 인프라 구축
   - [ ] OpenSearch 호스팅 결정 (AWS Serverless / 직접 호스팅)
   - [ ] 보고서 스키마 설계 (`docs/PRD.md` 5절 기준)
     - 밸류에이션: fair_value, current_price, upside, method
     - 매매 기준: buy_price, target_price, stop_loss
     - 뉴스/동향: sentiment_score, highlights, sector_trend
     - 추가 정보: screening_tags, embedding
   - [ ] 인덱스 생성

3. AI 종목 분석 파이프라인
   - [ ] Claude Code CLI 분석 스크립트 작성
   - [ ] 분석 결과 OpenSearch 저장
   - [ ] 분석 대상 범위 결정 (전체 / 워치리스트 / Top N)

4. 스크리닝 조건 확장 (현재 데이터로 구현 가능) ✅
   - [x] 그레이엄 스타일: 유동비율 > 1.5 조건 추가
   - [x] 모멘텀: 52주 신고가 근접 (90% 이상) - `momentum_high` 프리셋
   - [x] 모멘텀: 골든크로스 (MA50 > MA200) - `golden_cross` 프리셋

5. API + 프론트엔드
   - [ ] OpenSearch 조회 API 구현
   - [ ] 종목 상세 페이지에 AI 분석 섹션 추가

### P2 - Phase 5: AI 어드바이저
1. [ ] LangGraph Agent 구현 (실시간 채팅용)
2. [ ] AI Agent Tools 구현 (`docs/PRD.md` 8.3절 참조)
   - get_recommendations, get_report, search_reports, search_news, get_watchlist, compare_stocks
3. [ ] 오늘의 추천 기능
4. [ ] 개인화 추천 (워치리스트 기반)
5. [ ] 채팅 UI
6. [ ] 뉴스 수집 파이프라인 결정 (Finnhub API / RSS / 웹검색)

### P2.5 - 스크리닝 조건 확장 (추가 데이터 수집 필요)

> `docs/PRD.md` 4절 참조. 현재 데이터로 구현 가능한 조건은 P1-4로 이동됨.

- [ ] 배당 가치주: 연속 배당 연수 > 5년
- [ ] 퀄리티 가치주: 3년 이익 성장률 > 0
- [ ] 거래량 급증: 5일 평균 > 20일 평균 × 2
- [ ] 수급 시그널: 외국인/기관 순매수 (KRX 데이터 필요)
- [ ] 턴어라운드: 적자→흑자 전환, 영업이익률 개선 (분기 데이터 필요)

### P3 - 운영/인프라
1. [ ] 디스코드 봇 24/7 배포 (`.claude/rules/discord-bot-deployment.md`)
2. [ ] Self-hosted Runner 스케줄 활성화 (현재 로컬 Mac 수동 실행)
3. [ ] i18n (한/영)
4. [ ] 도메인 연결
5. [ ] 티커 요청 기능 (GitHub Issue 링크)
6. [ ] 프리셋 고급 기능 (수정/공유/복제)

