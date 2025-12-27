# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

미국(S&P 500 + 400 + 600 + Russell 2000) 및 한국(KOSPI + KOSDAQ) 시장을 지원하는 가치투자 스크리닝 도구. FastAPI 백엔드, 데이터 수집 파이프라인, 디스코드 봇, Next.js 프론트엔드로 구성된 멀티 서비스 모노레포.

## 실행 명령어

### 의존성 설치
```bash
uv sync
```

### 백엔드
```bash
uv run --package stock-screener-backend uvicorn app.main:app --reload
```

### 데이터 파이프라인
```bash
# 미국 주식 수집
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks             # 전체 (DB + CSV)
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only  # CSV만
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --test      # 테스트 (10개)

# 한국 주식 수집
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks             # 전체 (DB + CSV)
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only  # CSV만
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --test      # 테스트 (3개)
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kospi     # KOSPI만
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kosdaq    # KOSDAQ만

# CSV → Supabase 로딩
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db              # 전체 (US + KR)
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --us-only    # US만
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --kr-only    # KR만
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --date 20251227  # 특정 날짜
```

### 코드 품질
```bash
uv run ruff check .      # 린트 검사
uv run ruff format .     # 포맷팅
uv run ty check          # 타입 체크
uv run pytest            # 테스트
```

### 프론트엔드
```bash
cd frontend && npm run dev    # 개발 서버 (http://localhost:3000)
cd frontend && npm run build  # 프로덕션 빌드
```

## 개발 프로세스

### 로컬 테스트 후 배포 (필수)
프론트엔드/백엔드 변경 시 **반드시 로컬에서 테스트 후 커밋/푸시**:

```bash
# 1. 백엔드 서버 실행
uv run --package stock-screener-backend uvicorn app.main:app --reload

# 2. 프론트엔드 서버 실행 (별도 터미널)
cd frontend && npm run dev

# 3. http://localhost:3000 에서 테스트

# 4. 테스트 완료 후 커밋 & 푸시
git add . && git commit -m "변경 내용" && git push
```

### 배포 환경
| 서비스 | 플랫폼 | URL |
|--------|--------|-----|
| Frontend | Vercel | https://stock-screener-inky.vercel.app |
| Backend | Render | https://stock-screener-api-c0kc.onrender.com |
| Database | Supabase | (대시보드에서 확인) |

- **Vercel**: `main` 브랜치 푸시 시 자동 배포
- **Render**: `main` 브랜치 푸시 시 자동 배포 (무료 티어: 15분 비활성 시 슬립)

## 아키텍처

```
stock-screener/
├── pyproject.toml        # 루트 (uv 워크스페이스 + 도구 설정)
├── backend/              # FastAPI REST API (Python 3.11+)
│   ├── pyproject.toml    # 백엔드 의존성
│   └── app/
│       ├── main.py       # 진입점 (CORS, 헬스체크)
│       ├── api/          # 라우트 핸들러 (스캐폴드)
│       ├── models/       # Pydantic 모델 (스캐폴드)
│       ├── services/     # 비즈니스 로직 (스캐폴드)
│       └── core/         # 설정 및 유틸리티 (스캐폴드)
├── data-pipeline/        # 데이터 수집 스크립트
│   ├── pyproject.toml    # 파이프라인 의존성
│   ├── collectors/
│   │   ├── us_stocks.py  # 미국 주식 수집 (S&P 500/400/600 + Russell 2000)
│   │   └── kr_stocks.py  # 한국 주식 수집 (KOSPI + KOSDAQ)
│   ├── loaders/
│   │   └── csv_to_db.py  # CSV → Supabase 로딩
│   └── processors/       # 데이터 변환 (스캐폴드)
├── discord-bot/          # 디스코드 인터페이스
│   └── pyproject.toml    # 봇 의존성
├── tests/                # 테스트 디렉토리
└── .github/workflows/    # GitHub Actions 스케줄 데이터 수집
```

### 데이터 흐름

**미국 주식** (~2,800개):
- 티커 소스: Wikipedia (S&P 500/400/600) + iShares (Russell 2000)
- 데이터: yfinance (가격, 재무, 지표)
- 저장: Supabase + CSV

**한국 주식** (~2,800개):
- 티커 소스: pykrx (KOSPI + KOSDAQ 전체)
- 가격/시가총액: pykrx
- 재무제표: OpenDartReader (DART API)
- 추가 지표: yfinance (Gross Margin, EV/EBITDA, Dividend Yield, Beta 등)
- 저장: Supabase + CSV

**자동화**:
- GitHub Actions가 매주 일요일 00:00 UTC에 수집기 실행
- 매주 Supabase 데이터를 CSV로 백업

### 수집 지표

| 지표 | US 소스 | KR 소스 |
|------|---------|---------|
| P/E (Trailing) | yfinance | DART 계산 |
| P/E (Forward) | yfinance | yfinance |
| P/B | yfinance | DART 계산 |
| P/S | yfinance | DART 계산 |
| EV/EBITDA | yfinance | yfinance |
| ROE, ROA | yfinance | DART 계산 |
| Gross Margin | yfinance | yfinance |
| Net Margin | yfinance | DART 계산 |
| Debt/Equity | yfinance | DART 계산 |
| Current Ratio | yfinance | DART 계산 |
| Dividend Yield | yfinance | yfinance |
| Beta | yfinance | yfinance |
| 52주 고/저 | yfinance | yfinance |

### 주요 의존성
- 백엔드: FastAPI, asyncpg, Pydantic, httpx
- 데이터 파이프라인: yfinance, pykrx, opendartreader, pandas, supabase-py
- 데이터베이스: Supabase (PostgreSQL)

### 하이브리드 저장 전략
- **Supabase**: 최신 데이터만 유지 (무료 티어 ~500MB 제한)
- **CSV (로컬/GitHub)**: 전체 히스토리 저장 (`data/` 디렉토리)

### CSV 출력 파일
```
data/
├── us_companies.csv              # 미국 기업 목록
├── kr_companies.csv              # 한국 기업 목록
├── prices/
│   ├── us_prices_YYYYMMDD.csv    # 미국 일별 가격
│   └── kr_prices_YYYYMMDD.csv    # 한국 일별 가격
└── financials/
    ├── us_metrics_YYYYMMDD.csv   # 미국 일별 지표
    └── kr_metrics_YYYYMMDD.csv   # 한국 일별 지표
```

## 환경 변수

`.env` 파일에 필요:
- `SUPABASE_URL`, `SUPABASE_KEY` - 데이터베이스 (필수)
- `DART_API_KEY` - 한국 DART 재무제표 (KR 수집 시 필수)
- `DISCORD_BOT_TOKEN` - 디스코드 봇 (봇 사용 시)
- `FMP_API_KEY` - Financial Modeling Prep (현재 미사용, yfinance로 대체)

## 현재 상태

**구현됨**:
- 미국/한국 주식 데이터 수집기 (전체 유니버스)
- 하이브리드 저장 (Supabase + CSV)
- GitHub Actions 워크플로우 (수집 + 백업)
- FastAPI 백엔드 API
- Next.js 프론트엔드 (Preset 전략, Tooltip UX)

**미구현**: 워치리스트, 알림, 디스코드 봇 로직

**코드 내 알려진 TODO**:
- CORS가 "*"로 설정됨 (프로덕션에서는 제한 필요)
