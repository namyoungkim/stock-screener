# 실행 명령어

## 의존성 설치
```bash
uv sync
```

## 백엔드
```bash
uv run --package stock-screener-backend uvicorn app.main:app --reload
```

## 데이터 파이프라인

### 미국 주식 수집
```bash
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks             # 전체 유니버스 (DB + CSV)
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only  # 전체 유니버스 (CSV만)
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --sp500     # S&P 500만
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --test      # 테스트 (3개)
```
**전체 유니버스**: S&P 500 + S&P 400 + S&P 600 + Russell 2000 (~2,800개, 3-4시간 소요)

### 한국 주식 수집
```bash
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks             # 전체 (DB + CSV)
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only  # CSV만
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --test      # 테스트 (3개)
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kospi     # KOSPI만
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kosdaq    # KOSDAQ만
```

### 로컬 수집 + Google Drive 백업 (권장)
```bash
./scripts/collect-and-backup.sh         # 전체 (KR → US → 백업)
./scripts/collect-and-backup.sh kr      # KR만 + 백업
./scripts/collect-and-backup.sh us      # US만 + 백업
./scripts/collect-and-backup.sh kr --resume  # Rate Limit 후 재시작
```

**Rate Limit 대처:**
- Rate Limit 발생 시 진행 상황이 `data/{market}_progress.txt`에 자동 저장됨
- 15-30분 대기 후 `--resume` 플래그로 이어서 수집
- Exit code: 0=성공, 2=Rate Limit (재시작 필요)

> **주의**: KR, US를 동시에 실행하면 yfinance Rate Limit에 걸릴 수 있습니다. 순차 실행 권장.

### CSV → Supabase 로딩
```bash
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db              # 전체 (US + KR)
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --us-only    # US만
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --kr-only    # KR만
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --date 20251227  # 특정 날짜
```

## 프론트엔드
```bash
cd frontend && npm run dev    # 개발 서버 (http://localhost:3000)
cd frontend && npm run build  # 프로덕션 빌드
```

## 코드 품질
```bash
uv run ruff check .      # 린트 검사
uv run ruff format .     # 포맷팅
uv run ty check          # 타입 체크
uv run pytest            # 테스트
```
