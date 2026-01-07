# 실행 명령어

## 의존성 설치
```bash
uv sync
```

## 백엔드
```bash
uv run --package stock-screener-backend uvicorn app.main:app --reload
```

## 데이터 파이프라인 (CLI)

> **Note**: 모든 파이프라인 명령은 `data-pipeline/` 디렉토리에서 실행합니다.

```bash
cd data-pipeline
```

### 데이터 수집
```bash
uv run python -m cli.main collect all              # 전체 (KR → US → 백업 → DB)
uv run python -m cli.main collect us               # US만
uv run python -m cli.main collect kr               # KR만
uv run python -m cli.main collect all --resume     # Rate Limit 후 재시작
uv run python -m cli.main collect all --csv-only   # CSV만 (DB 스킵)
uv run python -m cli.main collect all --no-backup  # 백업 스킵
uv run python -m cli.main collect all --no-db      # DB 적재 스킵
uv run python -m cli.main collect us --test        # 테스트 (3개 티커)
uv run python -m cli.main collect us --limit 100   # 100개 티커만
uv run python -m cli.main collect us --tickers-file ../data/missing_tickers.txt  # 파일에서 티커 목록
uv run python -m cli.main collect all -q           # 최소 출력
uv run python -m cli.main collect all -v           # 상세 출력
```

**파이프라인 단계:**
1. KR 수집 (FDR + Naver)
2. US 수집 (yfinance)
3. Google Drive 백업 (rclone)
4. Supabase 적재

**Exit Codes:**
- 0: 성공
- 1: 오류
- 2: Rate Limit (재시작 필요)

### 티커 목록 업데이트
```bash
uv run python -m cli.main update-tickers all       # 전체 (KR + US)
uv run python -m cli.main update-tickers kr        # KR만 (FDR KRX-DESC)
uv run python -m cli.main update-tickers us        # US만 (NASDAQ FTP)
uv run python -m cli.main update-tickers kr --dry-run  # 변경사항 미리보기
```

### 백업
```bash
uv run python -m cli.main backup                   # Google Drive 백업
```

### DB 로딩
```bash
uv run python -m cli.main load                     # 전체 (latest 사용)
uv run python -m cli.main load --us-only           # US만
uv run python -m cli.main load --kr-only           # KR만
uv run python -m cli.main load --date 2026-01-03   # 특정 날짜
```

### 버전 확인
```bash
uv run python -m cli.main version
```

## 예상 시간

| 마켓 | 종목 수 | 예상 시간 | 비고 |
|------|---------|----------|------|
| KR | ~2,800개 | ~5-10분 | FDR + Naver |
| US | ~6,000개 | ~1-2시간 | yfinance |
| US (--limit 500) | 500개 | ~10-15분 | |

## LaunchAgent (자동 실행)

화~토 오전 8시에 자동 실행됩니다.

```bash
# 상태 확인
launchctl list | grep stock-screener

# 즉시 테스트 실행
launchctl start com.stock-screener.data-pipeline

# 로그 확인
tail -f /tmp/stock-screener-pipeline.log
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
