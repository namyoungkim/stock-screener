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
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks             # 전체 (DB + CSV)
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only  # CSV만
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --test      # 테스트 (10개)
```

### 한국 주식 수집
```bash
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks             # 전체 (DB + CSV)
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only  # CSV만
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --test      # 테스트 (3개)
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kospi     # KOSPI만
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --kosdaq    # KOSDAQ만
```

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
