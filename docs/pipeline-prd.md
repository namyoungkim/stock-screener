# 데이터 수집 파이프라인 재작성 PRD

> 작성일: 2026-01-13

## 개요

Stock Screener 데이터 수집 파이프라인의 완전 재작성을 위한 PRD.

**핵심 결정**: KR과 US를 **별도 파이프라인**으로 분리하여 각 마켓 특성에 최적화.

---

## 1. 현재 상태 및 문제점

### 1.1 이슈 요약

| 카테고리 | 이슈 | 심각도 | 영향 마켓 |
|----------|------|--------|----------|
| **안정성** | FDR 타임아웃 불안정 (3초↔10초 변동) | 높음 | KR |
| **안정성** | 수집 중간 행(hang) 발생 | 높음 | KR |
| **Rate Limit** | yfinance 429 에러 반복 | 중상 | US |
| **Rate Limit** | KIS API 제한 대비책 없음 | 중간 | KR |
| **복잡도** | 설정 분산 (constants.py + CLI + 하드코딩) | 중간 | 공통 |
| **복잡도** | 재시도 로직 산재 (sources, strategies, collectors) | 중간 | 공통 |
| **관찰성** | 성공률/소요시간 추적 어려움 | 중간 | 공통 |
| **관찰성** | 에러 원인 파악 어려움 (텍스트 로그) | 중간 | 공통 |

### 1.2 왜 분리하는가?

| 측면 | KR | US |
|------|----|----|
| **데이터 소스** | FDR + Naver + KIS (다중) | yfinance (단일) |
| **주요 문제** | 타임아웃/행 | Rate Limit |
| **수집 시간** | 5-10분 | 1-2시간 |
| **Rate Limit** | 거의 없음 | 빈번함 |
| **복잡도** | 낮음 | 높음 |

통합 구조의 문제:
- US의 Rate Limit 로직이 KR에 불필요하게 적용
- KR 장애가 US 수집을 지연시킴
- 마켓별 최적화 어려움

---

## 2. 목표

### 2.1 설계 원칙

1. **Fail Fast, Recover Gracefully** - 실패를 빠르게 감지하고, 명확한 복구 경로 제공
2. **Single Responsibility** - 각 컴포넌트는 하나의 역할만 수행
3. **Configuration as Code** - 모든 설정을 한 곳에서 관리, 시작 시 검증
4. **Observable by Default** - 모든 작업이 메트릭과 구조화된 로그를 생성

### 2.2 성공 지표

| 지표 | 현재 | 목표 |
|------|------|------|
| KR 수집 시간 | 5-10분 | 3-5분 |
| US 수집 시간 | 1-2시간 | 45-60분 |
| 성공률 | 측정 불가 | 95%+ |
| Rate Limit 복구 | 수동 재시작 | 자동 복구 |
| 장애 원인 파악 | 로그 분석 필요 | 즉시 확인 가능 |

---

## 3. 신규 아키텍처 (KR/US 분리)

### 3.1 디렉토리 구조

```
data-pipeline/
├── core/                      # 공통 인프라
│   ├── errors.py              # 에러 계층 구조
│   └── types.py               # 공유 타입 정의
│
├── observability/             # 공통 모니터링
│   ├── logger.py              # 구조화된 JSON 로거
│   └── metrics.py             # 메트릭 수집
│
├── storage/                   # 공통 저장소
│   ├── csv.py                 # CSV 저장
│   └── supabase.py            # Supabase 저장
│
├── kr/                        # ===== KR 전용 파이프라인 =====
│   ├── config.py              # KR 전용 설정
│   ├── pipeline.py            # KR 수집 메인 로직
│   ├── indicators.py          # 기술적 지표 (Beta=KOSPI)
│   └── sources/
│       ├── fdr.py             # FinanceDataReader
│       ├── naver.py           # Naver Finance
│       └── kis.py             # 한국투자증권 API
│
├── us/                        # ===== US 전용 파이프라인 =====
│   ├── config.py              # US 전용 설정
│   ├── pipeline.py            # US 수집 메인 로직
│   ├── indicators.py          # 기술적 지표 (Beta=S&P500)
│   ├── checkpoint.py          # Resume 지원
│   ├── sources/
│   │   └── yfinance.py        # yfinance 클라이언트
│   └── resilience/            # US 전용 장애 허용
│       ├── circuit_breaker.py
│       ├── retry.py
│       └── rate_limiter.py
│
└── cli/
    └── main.py                # collect kr / collect us / collect all
```

### 3.2 분리 원칙

| 레이어 | 공통 | KR 전용 | US 전용 |
|--------|------|---------|---------|
| **설정** | 기본 타입 | KR 타임아웃, 배치 | US Rate Limit, 백오프 |
| **로깅** | ✅ | - | - |
| **메트릭** | ✅ | - | - |
| **저장소** | ✅ | - | - |
| **데이터 소스** | - | FDR, Naver, KIS | yfinance |
| **장애 허용** | - | 단순 재시도 | Circuit Breaker, Token Bucket |
| **파이프라인** | - | 단순 순차 | Rate Limit 인식 배치 |

---

## 4. KR 파이프라인

### 특성
- **단순함 우선**: Rate Limit 걱정 없음
- **주요 관심사**: 타임아웃 관리, 다중 소스 조합
- **수집 시간 목표**: 3-5분

### 설정

```python
@dataclass(frozen=True)
class KRConfig:
    # 타임아웃 (초)
    fdr_timeout: float = 10.0
    naver_timeout: float = 5.0
    kis_timeout: float = 10.0

    # 배치
    history_batch_size: int = 100
    metrics_batch_size: int = 50

    # 재시도 (단순)
    max_retries: int = 2
    retry_delay: float = 1.0
```

### 흐름

```
1. 가격 수집 (FDR)
2. 히스토리 수집 (FDR, 배치)
3. 펀더멘탈 수집 (Naver + KIS 보조)
4. 기술적 지표 계산
5. 저장
```

---

## 5. US 파이프라인

### 특성
- **Rate Limit 중심**: yfinance 429 에러 대응이 핵심
- **주요 관심사**: Circuit Breaker, 지수 백오프, 진행상황 저장
- **수집 시간 목표**: 45-60분

### 설정

```python
@dataclass(frozen=True)
class USConfig:
    # 타임아웃 (초)
    price_timeout: float = 30.0
    history_timeout: float = 120.0
    metrics_timeout: float = 30.0

    # 배치 (Rate Limit 회피)
    price_batch_size: int = 50
    history_batch_size: int = 50
    metrics_batch_size: int = 10

    # 배치 간 딜레이
    batch_delay: float = 2.0
    batch_jitter: float = 1.0

    # Circuit Breaker
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 300.0

    # 재시도 (지수 백오프)
    max_retries: int = 3
    backoff_base: float = 2.0
    backoff_max: float = 300.0
```

### 장애 허용

- **Circuit Breaker**: 5회 연속 실패 → 300초 차단 → 복구 테스트
- **Rate Limiter**: Token Bucket (초당 5개, 버스트 10개)
- **Retry**: 지수 백오프 (2^n초, 최대 300초)

### 흐름

```
1. Resume 체크 (이전 진행상황 로드)
2. 가격 수집 (배치 + Rate Limit)
3. 히스토리 수집 (배치 + Rate Limit)
4. 메트릭 수집 (개별 + Circuit Breaker)
5. 기술적 지표 계산
6. 저장 + 체크포인트
```

---

## 6. 관찰성

### 구조화된 로그

```json
{
  "timestamp": "2026-01-13T08:30:00Z",
  "level": "info",
  "market": "us",
  "phase": "metrics",
  "message": "Batch completed",
  "batch_index": 5,
  "success_count": 9,
  "failed_count": 1,
  "duration_ms": 3500
}
```

### 메트릭

```python
@dataclass
class CollectionMetrics:
    market: str
    total_tickers: int
    successful: int
    failed: int
    phase_durations: dict[str, float]
    errors_by_type: dict[str, int]
    rate_limit_hits: int  # US 전용
```

---

## 7. 구현 순서

```
Phase 1: 공통 인프라 (core, observability)
    ↓
Phase 2: KR 파이프라인 (먼저, 빠른 검증)
    ↓
Phase 3: US 파이프라인 (Rate Limit 중심)
    ↓
Phase 4: CLI & 통합
```

---

## 8. 검증 방법

### 안정성
- [ ] 10회 연속 전체 수집 성공
- [ ] Rate Limit 발생 시 자동 복구
- [ ] 네트워크 장애 후 자동 재개

### 관찰성
- [ ] 수집 완료 후 성공률/소요시간 확인 가능
- [ ] 에러 발생 시 원인 즉시 파악 가능

### 성능
- [ ] KR 수집 5분 이내
- [ ] US 수집 60분 이내
