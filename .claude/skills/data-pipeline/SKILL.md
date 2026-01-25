---
name: data-pipeline
description: 데이터 수집 파이프라인 실행. "데이터 수집", "파이프라인 실행", "collect" 등에 반응
allowed-tools: Bash(uv:*), Bash(cd:*), Read
---

# 데이터 파이프라인 실행

$ARGUMENTS가 주어지면 그에 따라 데이터 수집을 실행합니다.

## 사용법

### 데이터 수집
- `/data-pipeline` - 전체 수집 (KR -> US -> 백업 -> DB)
- `/data-pipeline us` - 미국만
- `/data-pipeline kr` - 한국만
- `/data-pipeline resume` - Rate Limit 후 재개
- `/data-pipeline test` - 테스트 (3개 티커)

### 지표 보충 (Enrich)
- `/data-pipeline enrich kr` - KR 지표 보충 (EPS, BPS, Graham Number)
- `/data-pipeline enrich kr --date 2026-01-23` - 특정 날짜
- `/data-pipeline enrich kr --dry-run` - 미리보기

## 실행 절차
1. `cd data-pipeline` 디렉토리 이동
2. 명령어 실행:
   - 전체: `uv run python -m cli.main collect all`
   - US: `uv run python -m cli.main collect us`
   - KR: `uv run python -m cli.main collect kr`
   - Resume: `uv run python -m cli.main collect all --resume`
   - Test: `uv run python -m cli.main collect us --test`
   - Enrich: `uv run python -m cli.main enrich kr`
3. 완료 후 결과 보고

## 옵션
- `--csv-only` - CSV만 생성 (DB 스킵)
- `--no-backup` - Google Drive 백업 스킵
- `--no-db` - DB 적재 스킵
- `--limit N` - N개 티커만 수집
- `-v` - 상세 출력
- `-q` - 최소 출력

## 예상 시간
| 마켓 | 종목 수 | 예상 시간 |
|------|---------|----------|
| KR | ~2,800개 | ~5-10분 |
| US | ~6,000개 | ~1-2시간 |
| US (--limit 500) | 500개 | ~10-15분 |
