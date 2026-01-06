# Data-Pipeline 코드 리뷰 및 최적화 계획

## 상태: ✅ 완료 (2026-01-06)

## 개요

data-pipeline 하위 코드 전체에 대한 코드 리뷰 결과와 최적화 계획입니다.

---

## 구현 완료 요약

| Phase | 작업 | 상태 |
|-------|------|------|
| Phase 1 | pykrx 의존성 제거 | ✅ 이미 완료됨 |
| Phase 1 | 배치 사이즈 500→1000 | ✅ csv_to_db.py |
| Phase 1 | iterrows() 벡터화 | ✅ csv_to_db.py (metrics/prices) |
| Phase 1 | 날짜 파싱 최적화 | ✅ kr_stocks.py |
| Phase 2 | 배치 upsert 메서드 추가 | ✅ storage.py |
| Phase 2 | 마켓 인덱스 캐싱 | ✅ 이미 최적화됨 (KR: KOSPI 1회 로드, US: yfinance 제공) |
| Phase 2 | Universe 캐싱 | ✅ quality_check.py (lru_cache) |
| Phase 2 | CSV merge 최적화 | ✅ quality_check.py (drop_duplicates) |
| Phase 3 | 예외 로깅 추가 | ✅ indicators.py (8개 함수) |
| Phase 3 | 예외 로깅 개선 | ✅ us_stocks.py (price extraction) |

**테스트**: 150개 모두 통과

---

## 1. Critical Issues (즉시 수정)

### 1.1 DB 순차 Upsert - 8,400건 개별 API 호출

**위치**: `common/storage.py`, `collectors/us_stocks.py`, `collectors/kr_stocks.py`

**현재 문제**:
```python
# collectors에서 티커마다 3번의 개별 API 호출
for ticker in valid_tickers:
    company_id = self.storage.upsert_company(...)  # API 호출 1
    self.storage.upsert_metrics(...)                # API 호출 2
    self.storage.upsert_price(...)                  # API 호출 3

# 2,800 KR 종목 × 3 = 8,400 API 호출
# 6,000 US 종목 × 3 = 18,000 API 호출
```

**영향**:
- 순차 네트워크 I/O로 1-2분 낭비
- Supabase는 배치 upsert 지원하지만 미사용

**해결책**:
```python
# storage.py에 배치 메서드 추가
def upsert_companies_batch(self, records: list[dict], batch_size: int = 100):
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        self.client.table("companies").upsert(batch).execute()

def upsert_metrics_batch(self, records: list[dict], batch_size: int = 100):
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        self.client.table("metrics").upsert(batch, on_conflict="company_id,date").execute()

def upsert_prices_batch(self, records: list[dict], batch_size: int = 100):
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        self.client.table("prices").upsert(batch, on_conflict="company_id,date").execute()
```

**예상 개선**: 8,400 API → 84 API (**100배 감소**)

---

### 1.2 Beta 계산 시 마켓 인덱스 중복 로드

**위치**: `common/indicators.py:331-399`

**현재 문제**:
```python
def calculate_beta(stock_hist, market_hist, period=252):
    # 호출자가 market_hist를 매번 전달
    # KR: 2,800 종목 × KOSPI 로드 = 2,800번 중복 로드
    # US: 6,000 종목 × S&P500 로드 = 6,000번 중복 로드
```

**해결책**:
```python
import functools

@functools.lru_cache(maxsize=4)
def get_cached_market_index(market: str, period_days: int = 252) -> pd.DataFrame:
    """마켓 인덱스 데이터 캐싱"""
    import FinanceDataReader as fdr
    from datetime import datetime, timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days + 30)

    if market == "KR":
        return fdr.DataReader("KS11", start_date, end_date)
    else:  # US
        return fdr.DataReader("SPY", start_date, end_date)
```

**예상 개선**: 2,800 로드 → 1 로드 (**2,800배 감소**)

---

### 1.3 DataFrame.iterrows() 성능 문제

**위치**: `loaders/csv_to_db.py:110-125, 131-140, 272-290, 296-319, 351-368, 374-394`

**현재 문제**:
```python
for _, row in us_df.iterrows():  # pandas에서 가장 느린 반복 방법
    companies_to_upsert.append({
        "ticker": row["ticker"],
        "name": row["name"],
        ...
    })
```

**영향**: 9,000 rows에서 2-3초 오버헤드

**해결책**:
```python
# 방법 1: to_dict('records') 사용
companies_to_upsert = us_df[["ticker", "name", "sector", "industry", "currency"]].to_dict('records')

# 방법 2: 필요한 컬럼만 선택 후 변환
metrics_to_upsert = us_df[METRICS_COLUMNS].to_dict('records')
```

**예상 개선**: 2-3초 → 0.2초 (**10배 감소**)

---

## 2. Medium Issues

### 2.1 배치 실패 시 Silent Exception

**위치**: `collectors/us_stocks.py:470-471`

**현재 문제**:
```python
except Exception:
    pass  # 모든 에러를 조용히 무시
```

**해결책**:
```python
except (KeyError, IndexError, TypeError) as e:
    self.logger.debug(f"Data format error for {ticker}: {e}")
except Exception as e:
    self.logger.warning(f"Unexpected error processing {ticker}: {e}")
```

---

### 2.2 미사용 pykrx 의존성

**위치**: `pyproject.toml:7`

**현재 문제**:
```toml
"pykrx>=1.0.45",  # KR collector에서 제거됨, 더 이상 사용 안 함
```

**해결책**: 의존성 제거

---

### 2.3 Async Wrapper 복잡성

**위치**: `collectors/kr_stocks.py:228-254`

**현재 문제**:
```python
def _fetch_naver_fundamentals(self, tickers):
    try:
        asyncio.get_running_loop()
        # ThreadPoolExecutor로 asyncio.run() 실행 (복잡)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, self._fetch_naver_fundamentals_async(tickers))
            results = future.result()
    except RuntimeError:
        results = asyncio.run(self._fetch_naver_fundamentals_async(tickers))
```

**해결책**:
```python
def _fetch_naver_fundamentals(self, tickers):
    """Naver Finance에서 기초지표 수집"""
    return asyncio.run(self._fetch_naver_fundamentals_async(tickers))
```

---

### 2.4 날짜 파싱 매 루프마다 실행

**위치**: `collectors/kr_stocks.py:994`

**현재 문제**:
```python
for ticker in valid_tickers:
    all_metrics.append({
        "date": price_data.get("date", date.today().isoformat()),  # 매번 호출
        ...
    })
```

**해결책**:
```python
default_date = date.today().isoformat()  # 루프 밖에서 1번만
for ticker in valid_tickers:
    all_metrics.append({
        "date": price_data.get("date") or default_date,
        ...
    })
```

---

### 2.5 ThreadPool 중복 생성

**위치**: `collectors/kr_stocks.py:401, 503`

**현재 문제**:
```python
# 첫 번째 풀 (line 401)
executor = ThreadPoolExecutor(max_workers=10)

# 두 번째 풀 (line 503) - 동일한 설정
executor = ThreadPoolExecutor(max_workers=10)
```

**해결책**:
```python
def __init__(self):
    self._executor = ThreadPoolExecutor(max_workers=10)

def __del__(self):
    self._executor.shutdown(wait=True)
```

---

### 2.6 CSV Merge O(n²) 알고리즘

**위치**: `processors/quality_check.py:280-296`

**현재 문제**:
```python
existing_df = pd.read_csv(metrics_file)
new_df = pd.DataFrame(new_metrics)

existing_tickers = set(existing_df["ticker"])
new_tickers = set(new_df["ticker"])
overlap = existing_tickers & new_tickers

if overlap:
    existing_df = existing_df[~existing_df["ticker"].isin(overlap)]  # O(n)

merged_df = pd.concat([existing_df, new_df], ignore_index=True)
```

**해결책**:
```python
merged_df = pd.concat([existing_df, new_df])
merged_df = merged_df.drop_duplicates(subset=['ticker', 'date'], keep='last')
```

---

### 2.7 retry.py 미사용 (Dead Code)

**위치**: `common/retry.py` vs `common/config.py`

**현재 문제**:
- `retry.py`: 범용 retry decorator 정의
- `config.py`: BACKOFF_TIMES = [60, 120, 180, 300, 600] 별도 정의
- collectors는 config.py만 사용, retry.py는 거의 미사용

**해결책**: 통합 또는 정리 필요

---

### 2.8 배치 사이즈 보수적 (500 vs 1000)

**위치**: `loaders/csv_to_db.py:44`

**현재 문제**:
```python
BATCH_SIZE = 500  # Supabase는 1000까지 지원
```

**해결책**:
```python
BATCH_SIZE = 1000  # 2배 효율
```

---

### 2.9 인디케이터 예외 처리 Silent

**위치**: `common/indicators.py:33, 65, 92, 141, 197, 331`

**현재 문제**:
```python
def calculate_rsi(hist, period=14):
    try:
        # 계산 로직
    except Exception:  # 무슨 에러인지 알 수 없음
        return None
```

**해결책**:
```python
def calculate_rsi(hist, period=14):
    try:
        # 계산 로직
    except Exception as e:
        logger.debug(f"RSI calculation failed for {len(hist)} rows: {e}")
        return None
```

---

### 2.10 Universe NASDAQ FTP 재요청

**위치**: `processors/quality_check.py:95-116`

**현재 문제**:
```python
def get_universe(self, market: str) -> list[str]:
    if market.upper() == "US":
        from collectors.us_stocks import get_all_us_tickers
        all_data = get_all_us_tickers()  # 매번 NASDAQ FTP 요청
        return list(all_data.keys())
```

**해결책**:
```python
@functools.lru_cache(maxsize=2)
def get_universe(self, market: str) -> list[str]:
    # 캐시된 결과 반환
```

---

## 3. Low Issues

### 3.1 중복 safe_float/safe_int 구현

**위치**: `common/utils.py:30-61` vs `common/kis_client.py:413-431`

**현재 문제**:
- `utils.py`: `safe_float()`, `safe_int()` 정의
- `kis_client.py`: `_parse_float()`, `_parse_int()` 별도 정의 (중복)

**해결책**: kis_client.py에서 utils.py 함수 사용

---

### 3.2 중복 load_dotenv() 호출

**위치**: `common/config.py:9`, `common/utils.py:16`

**해결책**: config.py에서만 호출하고 utils.py에서 제거

---

### 3.3 미사용 max_abs 파라미터

**위치**: `common/utils.py:47`

**현재 문제**:
```python
def safe_float(value, max_abs=None):  # max_abs 사용처 없음
```

**해결책**: 파라미터 제거 또는 실제 사용 구현

---

### 3.4 ProgressTracker Thread Safety

**위치**: `common/rate_limit.py:227-275`

**현재 문제**:
```python
def mark_completed(self, ticker: str) -> None:
    self.completed_tickers.add(ticker)  # Thread-safe하지 않음

def save_progress(self) -> None:
    with open(self.progress_file, "w") as f:  # Atomic 아님
```

**해결책**: Lock 추가 또는 단일 스레드 사용 문서화

---

## 4. 코드 중복 정리

### 4.1 티커 필터링 로직 중복

**위치**:
- `us_stocks.py:177-183`
- `us_stocks.py:210-216`

**현재 문제**:
```python
# 두 곳에서 동일한 필터링
nasdaq_tickers = [
    t for t in nasdaq_tickers
    if t and len(t) <= 5 and t.isalpha()
    and not (len(t) == 5 and t.endswith("W"))
    and not (len(t) == 5 and t.endswith("R"))
    and not (len(t) == 5 and t.endswith("U"))
]
```

**해결책**:
```python
# common/utils.py에 추가
def filter_common_stocks(tickers: list[str]) -> list[str]:
    """일반 주식만 필터링 (워런트, 권리, 유닛 제외)"""
    return [
        t for t in tickers
        if t and len(t) <= 5 and t.isalpha()
        and not (len(t) == 5 and t[-1] in 'WRU')
    ]
```

---

## 5. 구현 순서

### Phase 1: Quick Wins (즉시 적용)

| 작업 | 파일 | 예상 효과 |
|------|------|----------|
| pykrx 의존성 제거 | pyproject.toml | 설치 시간 단축 |
| 배치 사이즈 500→1000 | csv_to_db.py | API 호출 50% 감소 |
| 날짜 파싱 최적화 | kr_stocks.py | 10% 성능 개선 |
| iterrows() 대체 | csv_to_db.py | 10배 빠름 |

### Phase 2: 성능 개선

| 작업 | 파일 | 예상 효과 |
|------|------|----------|
| 배치 upsert 구현 | storage.py | 100배 API 감소 |
| 마켓 인덱스 캐싱 | indicators.py | 2,800배 로드 감소 |
| Universe 캐싱 | quality_check.py | 5-10초 절약 |
| CSV merge 최적화 | quality_check.py | O(n²)→O(n) |

### Phase 3: 코드 품질

| 작업 | 파일 | 효과 |
|------|------|------|
| 예외 로깅 추가 | indicators.py, us_stocks.py | 디버깅 개선 |
| 중복 코드 정리 | utils.py, kis_client.py | 유지보수성 |
| 티커 필터 통합 | utils.py, us_stocks.py | 코드 재사용 |
| retry 로직 통합 | retry.py, config.py | Dead code 제거 |

---

## 6. 예상 개선 효과

| 항목 | 현재 | 개선 후 | 효과 |
|------|------|---------|------|
| DB upsert | 8,400 API | 84 API | **100배** |
| 마켓 인덱스 로드 | 2,800회 | 1회 | **2,800배** |
| iterrows 처리 | 2-3초 | 0.2초 | **10배** |
| 배치 사이즈 | 18 API | 9 API | **2배** |
| Universe 로드 | 매번 FTP | 캐시 | **5-10초** |

**총 예상**:
- 수집 시간 15-20% 단축
- 메모리 사용 30% 감소
- 유지보수성 향상

---

## 7. 관련 파일

### 수정 대상

| 파일 | 수정 내용 |
|------|----------|
| `common/storage.py` | 배치 upsert 메서드 추가 |
| `common/indicators.py` | 마켓 인덱스 캐싱, 예외 로깅 |
| `common/utils.py` | 티커 필터 함수 추가, 중복 제거 |
| `common/kis_client.py` | 중복 parse 함수 제거 |
| `collectors/us_stocks.py` | 배치 저장, 예외 로깅 |
| `collectors/kr_stocks.py` | 배치 저장, 날짜 최적화, ThreadPool 재사용 |
| `loaders/csv_to_db.py` | iterrows 대체, 배치 사이즈 증가 |
| `processors/quality_check.py` | CSV merge 최적화, Universe 캐싱 |
| `pyproject.toml` | pykrx 제거 |
