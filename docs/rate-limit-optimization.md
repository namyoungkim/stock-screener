# US 데이터 수집 Rate Limit 최적화 결과

> 테스트 날짜: 2026-01-08
> 테스트 환경: macOS, 로컬 네트워크

## 배경

US 주식 데이터 수집 시 yfinance의 rate limit으로 인해 6,000개 티커 수집에 1-2시간이 소요되었습니다.
배치 크기, 딜레이, 워커 수 등의 파라미터를 최적화하여 수집 시간을 단축했습니다.

## 테스트 방법

200개 티커로 다양한 설정을 테스트하고, rate limit 발생 여부와 수집 시간을 측정했습니다.

```bash
# 테스트 명령어 예시
time uv run python -m cli.main collect us --limit 200 --no-backup --no-db \
  --batch-size 20 --delay 1.5 --workers 6 --jitter 0.5
```

## 테스트 결과

### 200개 티커 기준

| Phase | batch_size | delay | workers | jitter | 시간 | 개선율 | Rate Limit |
|-------|------------|-------|---------|--------|------|--------|------------|
| 베이스라인 | 10 | 2.5s | 4 | 1.0s | **2분 45초** | - | 없음 |
| Phase 1 | 15 | 1.5s | 6 | 0.5s | 2분 14초 | 19% | 없음 |
| Phase 2 | 20 | 1.5s | 6 | 0.5s | **2분 0초** | **27%** | 없음 |
| Phase 3 | 30 | 1.0s | 8 | 0.3s | 1분 53초 | 32% | 없음 |

### 전체 수집 예상 시간 (6,000개 티커)

| 설정 | 예상 시간 |
|------|----------|
| 베이스라인 (기존) | 80-120분 |
| Phase 2 (채택) | **55-65분** |
| Phase 3 (공격적) | 50-55분 |

## 최적화 포인트

### 1. 배치 크기 증가 (10 → 20)
- 배치 수 감소로 전체 딜레이 시간 절감
- 200개 티커 기준: 20개 배치 → 10개 배치

### 2. 딜레이 감소 (2.5s → 1.5s)
- TLS fingerprinting bypass (curl_cffi)로 rate limit 위험 감소
- 배치당 1초 절약 × 배치 수 = 상당한 시간 절감

### 3. 워커 수 증가 (4 → 6)
- ThreadPoolExecutor 병렬 처리 향상
- KR 수집기는 8개 워커 사용 (참고)

### 4. 지터 감소 (1.0s → 0.5s)
- 불필요한 랜덤 대기 시간 축소
- 여전히 rate limit 방어 효과 유지

## 적용된 기본값

`data-pipeline/config/constants.py`:

```python
# === Batch Sizes ===
DEFAULT_BATCH_SIZE = 20  # (기존 10)

# === Concurrency ===
DEFAULT_MAX_WORKERS = 6  # (기존 4)

# === Delays (seconds) ===
DEFAULT_BASE_DELAY = 1.5  # (기존 2.5)
DEFAULT_JITTER = 0.5      # (기존 1.0)
```

## CLI 옵션

새로 추가된 rate limit 튜닝 옵션:

```bash
# 기본 설정 (최적화된 Phase 2)
uv run python -m cli.main collect us

# 더 공격적인 설정 (Phase 3)
uv run python -m cli.main collect us \
  --batch-size 30 --delay 1.0 --workers 8 --jitter 0.3

# 보수적인 설정 (rate limit 걱정 시)
uv run python -m cli.main collect us \
  --batch-size 10 --delay 2.5 --workers 4 --jitter 1.0

# 옵션 확인
uv run python -m cli.main collect --help
```

### 사용 가능한 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--batch-size` | Metrics 배치 크기 | 20 |
| `--delay` | 배치 간 딜레이 (초) | 1.5 |
| `--workers` | 병렬 워커 수 | 6 |
| `--jitter` | 랜덤 지터 범위 (초) | 0.5 |
| `--timeout` | 요청 타임아웃 (초) | 30 |

## Rate Limit 발생 시 대응

1. **자동 재시도**: `--resume` 플래그로 중단 지점부터 재개
   ```bash
   uv run python -m cli.main collect us --resume
   ```

2. **보수적 설정으로 전환**:
   ```bash
   uv run python -m cli.main collect us \
     --batch-size 10 --delay 2.5 --resume
   ```

3. **진행 상황 확인**:
   ```bash
   cat data/us_progress.txt | wc -l  # 완료된 티커 수
   ```

## 결론

- Phase 2 설정 (batch 20, delay 1.5, workers 6)을 기본값으로 채택
- **27% 성능 개선** (80-120분 → 55-65분)
- Rate limit 없이 안정적으로 동작
- CLI 옵션으로 필요 시 튜닝 가능

## 관련 파일

- `data-pipeline/config/constants.py` - 기본값 정의
- `data-pipeline/config/settings.py` - 환경변수 지원
- `data-pipeline/cli/main.py` - CLI 옵션
- `data-pipeline/sources/yfinance_source.py` - 실제 수집 로직
- `data-pipeline/collectors/us_collector.py` - US 수집기
