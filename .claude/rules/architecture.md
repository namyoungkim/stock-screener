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
│   │   ├── base.py       # BaseCollector 추상 클래스
│   │   ├── us_stocks.py  # 미국 주식 수집 (NYSE + NASDAQ 전체)
│   │   └── kr_stocks.py  # 한국 주식 수집 (KOSPI + KOSDAQ)
│   ├── common/           # 공통 모듈
│   │   ├── config.py     # 설정 상수
│   │   ├── logging.py    # 로거 + CollectionProgress
│   │   ├── retry.py      # @with_retry 데코레이터
│   │   ├── indicators.py # 기술적 지표 계산
│   │   ├── storage.py    # StorageManager
│   │   ├── session.py    # curl_cffi 브라우저 세션 (TLS fingerprinting 우회)
│   │   └── rate_limit.py # Rate Limit 감지 + ProgressTracker + FailureType
│   ├── loaders/
│   │   └── csv_to_db.py  # CSV → Supabase 로딩
│   └── processors/
│       ├── validators.py    # MetricsValidator 데이터 검증
│       └── quality_check.py # 수집 품질 검사 + 자동재수집
├── frontend/             # Next.js 프론트엔드
├── discord-bot/          # 디스코드 인터페이스
├── tests/                # 테스트 디렉토리
└── .github/workflows/    # GitHub Actions 스케줄 데이터 수집
```

## 데이터 흐름

**미국 주식** (~6,000개):
- 티커 소스: NASDAQ FTP (NYSE + NASDAQ 전체)
- 데이터: yfinance (가격, 재무, 지표)
- 저장: Supabase + CSV
- 옵션: `--index-only`로 S&P + Russell만 수집 (~2,800개)

**한국 주식** (~2,800개):
- 티커 소스: CSV (`kr_companies.csv`)
- 가격: FinanceDataReader (네이버 금융)
- EPS/BPS/PER/PBR: 네이버 금융 웹 크롤링
- 재무 지표: yfinance (ROE, ROA, Margins, D/E, Current Ratio 등)
- 저장: Supabase + CSV

> **Note**: 2025.12.27부터 KRX 로그인 필수화로 pykrx가 작동하지 않아 FDR + 네이버 크롤링으로 전환

**데이터 파이프라인** (`./scripts/collect-and-backup.sh`):
1. KR 수집 (품질검사 + 자동재수집)
2. US 수집 (품질검사 + 자동재수집)
3. Google Drive 백업 (rclone)
4. Supabase 적재 (csv_to_db)

**자동 품질 검사**:
- 유니버스 커버리지 (95% 이상)
- 대형주 누락 검사 (US Major Top 15, KOSPI Top 10)
- 지표 완성도 (PE, PB, ROE, RSI 등)
- 누락 100개 이하 시 자동 재수집

**수집 소요 시간** (로컬 Mac 기준):

| 마켓 | 종목 수 | 예상 시간 |
|------|---------|----------|
| KR | ~2,800개 | ~10분 (병렬화) |
| US (full) | ~6,000개 | ~1-1.5시간 |
| US (--index-only) | ~2,800개 | ~30-45분 |
| US (--sp500) | ~500개 | ~10-15분 |

**Rate Limit 대응** (2단계 전략):

1. **1차 방어: TLS Fingerprinting 우회**
   - curl_cffi 라이브러리로 Chrome 브라우저 세션 모방
   - Yahoo Finance의 자동화 탐지 우회

2. **2차 방어: 자동 재시도 루프**
   - History 수집 + Metrics 수집 모두 재시도 지원
   - 최대 10라운드 재시도 (실패 티커만 별도 재수집)
   - 실패 유형 분류: RATE_LIMIT, TIMEOUT (재시도) vs NO_DATA, OTHER (스킵)

| 설정 | 값 | 설명 |
|------|-----|------|
| 배치 크기 | 10 | `--batch-size`로 조정 가능 |
| 배치 간 딜레이 | 2.5-3.5초 | 랜덤 지터 |
| History 재시도 대기 | 2분 | `yf.download()`는 관대함 |
| Metrics 재시도 대기 | 10분 | `.info()` 호출은 민감함 |
| 배치 내 백오프 | 최대 5회 | 1분→2분→3분→5분→10분 |
| 최대 재시도 | 10회 | 무한 루프 방지 |

> 주의: KR, US 동시 실행 시 yfinance Rate Limit에 걸릴 수 있음

## 수집 지표

### 기본 지표

| 지표 | US 소스 | KR 소스 |
|------|---------|---------|
| P/E (Trailing) | yfinance | 네이버 금융 |
| P/E (Forward) | yfinance | yfinance |
| P/B | yfinance | 네이버 금융 |
| P/S | yfinance | yfinance |
| EV/EBITDA | yfinance | yfinance |
| PEG Ratio | yfinance | yfinance |
| ROE, ROA | yfinance | yfinance |
| Gross Margin | yfinance | yfinance |
| Net Margin | yfinance | yfinance |
| Debt/Equity | yfinance | yfinance |
| Current Ratio | yfinance | yfinance |
| Dividend Yield | yfinance | yfinance |
| Beta | yfinance | yfinance |
| EPS | yfinance | 네이버 금융 |
| Book Value/Share | yfinance | 네이버 금융 |
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
- 데이터 파이프라인: yfinance, FinanceDataReader, pandas, supabase-py, beautifulsoup4, curl-cffi
- 데이터베이스: Supabase (PostgreSQL)

## 하이브리드 저장 전략

- **Supabase**: 최신 데이터만 유지 (무료 티어 ~500MB 제한)
- **CSV (로컬/GitHub)**: 전체 히스토리 저장 (`data/` 디렉토리)

## CSV 출력 파일

> **Note**: `YYYY-MM-DD`는 파이프라인 실행일이 아닌 **실제 거래일** 기준입니다.
> 예: 일요일(2026-01-05)에 실행 → `data/2026-01-03/` (금요일 거래일) 생성

```
data/
├── YYYY-MM-DD/                   # 거래일 기준 디렉토리
│   ├── v1/                       # 버전별 디렉토리 (재수집 시 v2, v3 ...)
│   │   ├── us_prices.csv         # 미국 가격
│   │   ├── us_metrics.csv        # 미국 지표
│   │   ├── kr_prices.csv         # 한국 가격
│   │   └── kr_metrics.csv        # 한국 지표
│   └── current -> v1/            # 해당 날짜의 최신 버전 심링크
├── companies/                    # 기업 마스터 데이터 (날짜 무관)
│   ├── us_companies.csv          # 미국 기업 목록
│   └── kr_companies.csv          # 한국 기업 목록
└── latest -> YYYY-MM-DD/vN/      # 가장 최신 수집 데이터 심링크
```

**버전 관리**:
- 같은 날 재수집 시 자동으로 새 버전 생성 (v1, v2, ...)
- `latest` 심링크로 가장 최신 데이터 쉽게 접근
- 오래된 데이터 정리가 날짜 단위로 쉬움
