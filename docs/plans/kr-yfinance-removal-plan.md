# KR 수집기 yfinance 제거 및 KIS API 전환 구현 계획

## 상태: ✅ 완료 (2026-01-06)

## 목표
- ✅ yfinance 완전 제거
- ✅ KIS API + Naver 크롤링 + FDR로 대체
- ✅ 수집 시간: 1-2시간 → 10-15분
- ✅ 안정성 향상 (Rate Limit 문제 해결)

## 사용자 선택
- [x] 한국투자증권 계좌 있음
- [x] MA200: FDR 7개월 확장
- [x] Beta: KOSPI 대비 계산 포함 (FDR KS11)

---

## 새 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  KR 수집 파이프라인 (yfinance 0%)                            │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: FDR (7개월 OHLCV)                                  │
│    - 가격, 거래량                                            │
│    - 기술적 지표용 히스토리 (RSI, MACD, BB, MFI)              │
│    - MA50, MA200 계산                                        │
│    - Beta 계산 (KOSPI 대비)                                  │
│                                                             │
│  Phase 2: Naver Finance 크롤링 (확장)                        │
│    - PER, PBR, EPS, BPS (기존)                               │
│    - ROE, ROA (신규)                                         │
│    - 부채비율, 유동비율 (신규)                                │
│    - 배당수익률 (신규)                                        │
│    - 시가총액 (신규)                                          │
│                                                             │
│  Phase 3: KIS API (보조)                                     │
│    - 52주 고/저                                              │
│    - 시가총액 (Naver 백업)                                    │
│    - 재무비율 (Naver 실패 시 백업)                            │
│                                                             │
│  Phase 4: 로컬 계산                                          │
│    - 기술적 지표 (indicators.py)                             │
│    - Graham Number                                          │
│    - price_to_52w_high_pct, ma_trend                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 파일 구조

### 신규 파일
```
data-pipeline/common/
├── kis_client.py      # KIS API 클라이언트 (인증, rate limit, API 호출)
└── naver_finance.py   # Naver Finance 확장 크롤러 (기존 코드 분리 + 확장)
```

### 수정 파일
```
data-pipeline/
├── collectors/kr_stocks.py   # yfinance 제거, 새 소스 통합
├── common/config.py          # KIS 설정 추가
└── pyproject.toml            # yfinance 제거, python-kis 선택적 추가
```

---

## Stage 1: 기반 모듈 구축 (2-3일)

### 1.1 common/kis_client.py 생성

```python
class KISClient:
    """한국투자증권 Open API 클라이언트"""

    def __init__(self, app_key: str, app_secret: str, is_paper: bool = False)

    # 인증
    def _get_access_token(self) -> str
    def _refresh_token_if_needed(self) -> None

    # Rate Limit (초당 15건, 토큰 버킷)
    async def _acquire_rate_limit(self) -> None

    # API 메서드
    async def get_quote(self, ticker: str) -> dict
        # 현재가, 52주 고/저, 시가총액

    async def get_financial_ratio(self, ticker: str) -> dict
        # ROE, EPS, BPS, 부채비율 (Naver 백업용)

    async def get_quotes_bulk(self, tickers: list[str]) -> dict[str, dict]
        # 병렬 처리 + rate limit
```

### 1.2 common/naver_finance.py 생성

```python
class NaverFinanceClient:
    """Naver Finance 확장 크롤러"""

    # 기존 기능 (kr_stocks.py에서 이동)
    async def get_fundamentals(self, ticker: str) -> dict
        # PER, EPS, PBR, BPS

    # 신규 기능
    async def get_financial_ratios(self, ticker: str) -> dict
        # ROE, ROA, 부채비율, 유동비율
        # 소스: 투자지표 섹션 또는 fnguide 데이터

    async def get_market_cap(self, ticker: str) -> int
        # 시가총액

    async def get_dividend_yield(self, ticker: str) -> float
        # 배당수익률

    async def get_all_data(self, ticker: str) -> dict
        # 한 번의 페이지 요청으로 모든 데이터 추출

    async def fetch_bulk(self, tickers: list[str], concurrency: int = 10) -> dict
        # 병렬 처리 (aiohttp + semaphore)
```

### 1.3 config.py 업데이트

```python
# KIS API 설정
KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
KIS_PAPER_TRADING = os.environ.get("KIS_PAPER_TRADING", "false").lower() == "true"
KIS_RATE_LIMIT = 15  # 초당 요청 수

# FDR 설정
FDR_HISTORY_DAYS = 210  # 7개월 (MA200용)
```

---

## Stage 2: KR 수집기 리팩토링 (2-3일)

### 2.1 제거할 메서드
- `_fetch_yfinance_metrics()`
- `fetch_history_bulk()`
- `fetch_yfinance_batch()`
- yfinance import 및 관련 코드

### 2.2 수정할 메서드

**fetch_prices_batch()** → `fetch_fdr_data()`
```python
def fetch_fdr_data(self, tickers: list[str]) -> tuple[dict, dict]:
    """FDR로 가격 + 7개월 OHLCV 히스토리 수집

    Returns:
        prices: {ticker: {date, close, volume}}
        history: {ticker: DataFrame(OHLCV)}
    """
    start_date = (today - timedelta(days=210)).strftime("%Y-%m-%d")
    # ThreadPoolExecutor로 병렬 수집
    # 가격 데이터와 히스토리 동시 반환
```

**_fetch_naver_fundamentals_async()** → NaverFinanceClient로 이동

### 2.3 신규 메서드

```python
def _calculate_beta(self, stock_history: pd.DataFrame, kospi_history: pd.DataFrame) -> float:
    """KOSPI 대비 Beta 계산 (회귀분석)"""

def _calculate_moving_averages(self, history: pd.DataFrame) -> tuple[float, float]:
    """MA50, MA200 계산"""

def _fetch_kospi_history(self) -> pd.DataFrame:
    """KOSPI 지수 7개월 히스토리 (Beta 계산용)"""
```

### 2.4 새 collect() 흐름

```python
def collect(self, tickers: list[str] = None, ...):
    tickers = tickers or self.get_tickers()

    # Phase 1: FDR 7개월 OHLCV
    prices_all, history_data = self.fetch_fdr_data(tickers)
    kospi_history = self._fetch_kospi_history()

    # Phase 2: Naver 확장 크롤링
    naver_client = NaverFinanceClient()
    naver_data = await naver_client.fetch_bulk(valid_tickers)
    # → PER, PBR, EPS, BPS, ROE, ROA, D/E, CR, DY, market_cap

    # Phase 3: KIS API (52주, 백업)
    kis_client = KISClient(...)
    kis_data = await kis_client.get_quotes_bulk(valid_tickers)
    # → 52w_high/low, market_cap (백업)

    # Phase 4: 로컬 계산
    for ticker in valid_tickers:
        hist = history_data.get(ticker)

        # 기술적 지표
        technicals = calculate_all_technicals(hist)

        # MA50, MA200
        ma50, ma200 = self._calculate_moving_averages(hist)

        # Beta
        beta = self._calculate_beta(hist, kospi_history)

        # 52주 고/저 (히스토리에서 계산 또는 KIS)
        fifty_two_week_high = hist['High'].max() if hist else kis_data.get(ticker, {}).get('52w_high')

        # 데이터 결합
        combined = {
            **prices_all.get(ticker, {}),
            **naver_data.get(ticker, {}),
            **technicals,
            'fifty_day_average': ma50,
            'two_hundred_day_average': ma200,
            'beta': beta,
            'fifty_two_week_high': fifty_two_week_high,
            ...
        }

        # 저장
```

---

## Stage 3: 테스트 및 검증 (2일)

### 3.1 단위 테스트

```
tests/
├── test_kis_client.py
│   ├── test_token_acquisition
│   ├── test_rate_limiter
│   └── test_get_quote
├── test_naver_finance.py
│   ├── test_get_fundamentals
│   ├── test_get_financial_ratios
│   └── test_bulk_fetch
└── test_kr_collector.py
    ├── test_fetch_fdr_data
    ├── test_calculate_beta
    └── test_collect_integration
```

### 3.2 데이터 품질 검증

| 지표 | 검증 방법 |
|------|----------|
| PER, PBR | yfinance 대비 오차율 < 5% |
| ROE, ROA | yfinance 대비 오차율 < 10% |
| 기술적 지표 | 동일 계산 로직 (FDR/yfinance 동일) |
| 시가총액 | yfinance 대비 오차율 < 10% |
| 필드 커버리지 | 95% 이상 |

### 3.3 성능 벤치마크

| 항목 | 현재 | 목표 |
|------|------|------|
| 수집 시간 | 1-2시간 | 10-15분 |
| Rate Limit 발생 | 빈번 | 없음 |
| 성공률 | 80-90% | 98%+ |

---

## Stage 4: 마이그레이션 (1일)

### 4.1 의존성 변경

```toml
# pyproject.toml
# 제거
# "yfinance>=0.2.36"

# 추가 (선택적 - 직접 REST 호출 시 불필요)
# "python-kis>=2.0.0"
```

### 4.2 문서 업데이트

- CLAUDE.md: 새 데이터 소스 설명
- commands.md: 환경 변수 추가 (KIS_APP_KEY, KIS_APP_SECRET)
- architecture.md: 새 아키텍처 반영

### 4.3 롤백 전략

```python
# 환경 변수로 전환 가능
USE_LEGACY_YFINANCE = os.environ.get("USE_LEGACY_YFINANCE", "false")
```

---

## 일정 요약

| Stage | 작업 | 예상 시간 |
|-------|------|----------|
| 1 | 기반 모듈 구축 (kis_client, naver_finance) | 2-3일 |
| 2 | KR 수집기 리팩토링 | 2-3일 |
| 3 | 테스트 및 검증 | 2일 |
| 4 | 마이그레이션 및 문서화 | 1일 |
| **총계** | | **7-9일** |

---

## Critical Files

1. **신규**: `data-pipeline/common/kis_client.py`
2. **신규**: `data-pipeline/common/naver_finance.py`
3. **수정**: `data-pipeline/collectors/kr_stocks.py`
4. **수정**: `data-pipeline/common/config.py`
5. **수정**: `data-pipeline/pyproject.toml`
6. **유지**: `data-pipeline/common/indicators.py` (변경 없음)

---

## 환경 변수 (추가 필요)

```bash
# .env
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_PAPER_TRADING=false
```

---

## 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| Naver 페이지 구조 변경 | CSS 선택자 + 정규식 다중화, KIS 백업 |
| KIS Rate Limit | 토큰 버킷 + 백오프 구현 |
| ROE/ROA Naver에서 못 가져옴 | KIS 재무비율 API 백업 |
| FDR 일부 종목 실패 | 재시도 로직 + 누락 로깅 |

---

## 구현 완료 요약 (2026-01-06)

### 완료된 작업

| Stage | 작업 | 상태 |
|-------|------|------|
| 1 | kis_client.py 생성 | ✅ 완료 |
| 1 | naver_finance.py 생성 | ✅ 완료 |
| 1 | config.py KIS 설정 추가 | ✅ 완료 |
| 2 | kr_stocks.py yfinance 제거 | ✅ 완료 |
| 2 | kr_stocks.py pykrx 제거 | ✅ 완료 |
| 2 | KRCollector 독립 클래스화 | ✅ 완료 |
| 3 | 테스트 업데이트 | ✅ 완료 (27개 통과) |
| 4 | 문서 업데이트 | ✅ 완료 |

### 추가 정리 작업 (별도 커밋)

| 작업 | 상태 | 설명 |
|------|------|------|
| common/utils.py 생성 | ✅ 완료 | 중복 유틸리티 통합 |
| storage.py 리팩토링 | ✅ 완료 | utils에서 import |
| csv_to_db.py 리팩토링 | ✅ 완료 | utils에서 import |

### 남은 작업 (선택적, 별도 PR)

| 작업 | 상태 | 설명 |
|------|------|------|
| USCollector 독립화 | ⏳ 대기 | BaseCollector 상속 제거 |
| base.py 삭제 | ⏳ 대기 | US 독립화 후 삭제 |

### 관련 커밋

```
dbbf1ed refactor: consolidate utils and remove yfinance/pykrx from KR collector
a7377c8 feat: add KIS API and Naver Finance clients for KR data collection
```

### 결과

- **코드 감소**: ~240줄 (중복/dead code 제거)
- **KR 수집**: yfinance/pykrx 완전 제거, FDR + KIS + Naver만 사용
- **테스트**: 27개 모두 통과
- **독립성**: KRCollector는 BaseCollector 상속 없이 독립 클래스로 운영
