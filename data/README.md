# Data Directory

이 디렉토리는 로컬 데이터 저장용입니다. CSV 파일은 git에서 제외됩니다.

## 디렉토리 구조

```
data/
├── prices/       # 일별 주가 히스토리
├── financials/   # 분기별 재무제표
└── backup/       # Supabase 백업
```

## 파일 형식

### prices/
- `us_prices_YYYYMMDD.csv` - 미국 주식 가격
- `kr_prices_YYYYMMDD.csv` - 한국 주식 가격

### financials/
- `us_financials_YYYY.csv` - 미국 주식 재무제표
- `kr_financials_YYYY.csv` - 한국 주식 재무제표

### backup/
- `companies_YYYYMMDD.csv` - 회사 마스터 백업
- `metrics_YYYYMMDD.csv` - 지표 백업

## 용량 관리

- 1년 데이터: ~230MB
- 권장: 최근 2년 데이터만 로컬 보관
- 오래된 파일은 주기적으로 정리

## 복원

백업 파일로 Supabase 복원:
```bash
# CSV를 Supabase로 import (예정)
uv run --package stock-screener-data-pipeline python -m scripts.restore_backup
```
