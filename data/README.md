# Data Directory

이 디렉토리는 로컬 데이터 저장용입니다. CSV 파일은 git에서 제외됩니다.

## 디렉토리 구조

```
data/
├── YYYY-MM-DD/              # 거래일 기준 디렉토리
│   ├── v1/                  # 버전별 디렉토리 (재수집 시 v2, v3 ...)
│   │   ├── us_prices.csv    # 미국 가격
│   │   ├── us_metrics.csv   # 미국 지표
│   │   ├── kr_prices.csv    # 한국 가격
│   │   └── kr_metrics.csv   # 한국 지표
│   └── current -> v1/       # 해당 날짜의 최신 버전 심링크
├── companies/               # 기업 마스터 데이터 (날짜 무관)
│   ├── us_companies.csv     # 미국 기업 목록
│   └── kr_companies.csv     # 한국 기업 목록
└── latest -> YYYY-MM-DD/vN/ # 가장 최신 수집 데이터 심링크
```

> **Note**: `YYYY-MM-DD`는 파이프라인 실행일이 아닌 **실제 거래일** 기준입니다.
> 예: 일요일(2026-01-05)에 실행 → `data/2026-01-03/` (금요일 거래일) 생성

## 버전 관리

- 같은 날 재수집 시 자동으로 새 버전 생성 (v1, v2, ...)
- `current` 심링크로 해당 날짜의 최신 버전 접근
- `latest` 심링크로 가장 최신 수집 데이터 접근

## 용량 관리

- 1년 데이터: ~230MB
- 권장: 최근 2년 데이터만 로컬 보관
- 오래된 데이터는 날짜 디렉토리 단위로 삭제

## CSV → Supabase 로딩

```bash
# 최신 데이터 (latest 심링크 사용)
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db

# 특정 날짜 + 버전
uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db --date 2026-01-03 --version v1
```
