# 아키텍처

## 디렉토리 구조

```
stock-screener/
├── pyproject.toml        # 루트 (uv 워크스페이스 + 도구 설정)
├── backend/              # FastAPI REST API (Python 3.11+)
│   ├── pyproject.toml    # 백엔드 의존성
│   └── app/
│       ├── main.py       # 진입점 (CORS, 헬스체크)
│       ├── api/          # 라우트 핸들러
│       ├── models/       # Pydantic 모델
│       ├── services/     # 비즈니스 로직
│       └── core/         # 설정 및 유틸리티
├── data-pipeline/        # 데이터 수집 스크립트
│   ├── pyproject.toml    # 파이프라인 의존성
│   ├── collectors/
│   │   ├── us_stocks.py  # 미국 주식 수집 (S&P 500/400/600 + Russell 2000)
│   │   └── kr_stocks.py  # 한국 주식 수집 (KOSPI + KOSDAQ)
│   ├── loaders/
│   │   └── csv_to_db.py  # CSV → Supabase 로딩
│   └── processors/       # 데이터 변환
├── frontend/             # Next.js 프론트엔드
├── discord-bot/          # 디스코드 인터페이스
├── tests/                # 테스트 디렉토리
└── .github/workflows/    # GitHub Actions 스케줄 데이터 수집
```

## 데이터 흐름

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

## 수집 지표

### 기본 지표

| 지표 | US 소스 | KR 소스 |
|------|---------|---------|
| P/E (Trailing) | yfinance | DART 계산 |
| P/E (Forward) | yfinance | yfinance |
| P/B | yfinance | DART 계산 |
| P/S | yfinance | DART 계산 |
| EV/EBITDA | yfinance | yfinance |
| PEG Ratio | yfinance | yfinance |
| ROE, ROA | yfinance | DART 계산 |
| Gross Margin | yfinance | yfinance |
| Net Margin | yfinance | DART 계산 |
| Debt/Equity | yfinance | DART 계산 |
| Current Ratio | yfinance | DART 계산 |
| Dividend Yield | yfinance | yfinance |
| Beta | yfinance | yfinance |
| EPS | yfinance | yfinance |
| Book Value/Share | yfinance | yfinance |
| Graham Number | 계산 | 계산 |
| 52주 고/저 | yfinance | yfinance |
| 50일/200일 이동평균 | yfinance | yfinance |

### 기술적 지표

| 지표 | 설명 | 계산 방식 |
|------|------|----------|
| RSI (14일) | 상대강도지수 | 가격 기반 계산 |
| MFI | 자금흐름지수 | 거래량 가중 RSI |
| MACD | 이동평균수렴확산 | EMA 12/26/9 |
| MACD Signal | MACD 신호선 | 9일 EMA |
| MACD Histogram | MACD 히스토그램 | MACD - Signal |
| Bollinger Upper | 볼린저밴드 상단 | SMA20 + 2σ |
| Bollinger Middle | 볼린저밴드 중간 | SMA20 |
| Bollinger Lower | 볼린저밴드 하단 | SMA20 - 2σ |
| Bollinger %B | 볼린저밴드 %B | (가격-하단)/(상단-하단) |
| Volume Change | 거래량 변화율 | 20일 평균 대비 % |

## 주요 의존성

- 백엔드: FastAPI, asyncpg, Pydantic, httpx
- 데이터 파이프라인: yfinance, pykrx, opendartreader, pandas, supabase-py
- 데이터베이스: Supabase (PostgreSQL)

## 하이브리드 저장 전략

- **Supabase**: 최신 데이터만 유지 (무료 티어 ~500MB 제한)
- **CSV (로컬/GitHub)**: 전체 히스토리 저장 (`data/` 디렉토리)

## CSV 출력 파일

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
