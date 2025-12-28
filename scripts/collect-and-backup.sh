#!/bin/bash
# 로컬 데이터 파이프라인: 수집 → 품질검사 → 백업 → DB 적재
#
# 사용법: ./scripts/collect-and-backup.sh [kr|us|all] [--resume] [--no-db]
#
# 옵션:
#   kr|us|all  - 수집할 시장 (기본값: all)
#   --resume   - Rate Limit 후 이어서 수집
#   --no-db    - Supabase 적재 건너뛰기
#
# Exit codes:
#   0 - 성공
#   1 - 일반 오류
#   2 - Rate Limit 감지 (진행 상황 저장됨, --resume으로 재시작 가능)

MARKET=${1:-all}
RESUME_FLAG=""
SKIP_DB=false

# 플래그 파싱
for arg in "$@"; do
    case "$arg" in
        --resume)
            RESUME_FLAG="--resume"
            ;;
        --no-db)
            SKIP_DB=true
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "============================================"
echo "Stock Data Pipeline"
echo "Market: $MARKET"
echo "Resume: ${RESUME_FLAG:-no}"
echo "Skip DB: $SKIP_DB"
echo "Time: $(date)"
echo "============================================"

# Rate Limit 발생 시 처리 함수
handle_rate_limit() {
    local market=$1
    echo ""
    echo "============================================"
    echo "Rate Limit detected for $market"
    echo "Progress has been saved."
    echo ""
    echo "To resume after rate limit resets (15-30 min):"
    echo "  ./scripts/collect-and-backup.sh $market --resume"
    echo "============================================"
}

# Phase 1: KR 수집 (품질검사 + 자동재수집 포함)
KR_SUCCESS=true
if [[ "$MARKET" == "kr" || "$MARKET" == "all" ]]; then
    echo ""
    echo "[1/4] Collecting KR stocks..."
    if uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only $RESUME_FLAG; then
        echo "KR collection completed!"
    else
        exit_code=$?
        if [[ $exit_code -eq 2 ]]; then
            handle_rate_limit "KR"
            KR_SUCCESS=false
            if [[ "$MARKET" == "kr" ]]; then
                exit 2
            fi
        else
            echo "KR collection failed with exit code $exit_code"
            exit $exit_code
        fi
    fi
fi

# Phase 2: US 수집 (품질검사 + 자동재수집 포함)
US_SUCCESS=true
if [[ "$MARKET" == "us" || "$MARKET" == "all" ]]; then
    echo ""
    echo "[2/4] Collecting US stocks..."
    if uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only $RESUME_FLAG; then
        echo "US collection completed!"
    else
        exit_code=$?
        if [[ $exit_code -eq 2 ]]; then
            handle_rate_limit "US"
            US_SUCCESS=false
            if [[ "$MARKET" == "us" ]]; then
                exit 2
            fi
        else
            echo "US collection failed with exit code $exit_code"
            exit $exit_code
        fi
    fi
fi

# Phase 3: Google Drive 백업
# NOTE: rclone gdrive: 는 root_folder_id로 stock-screener-backup 폴더를 가리킴
if [[ -d "data/prices" ]] && [[ -n "$(ls -A data/prices/ 2>/dev/null)" ]]; then
    echo ""
    echo "[3/4] Backing up to Google Drive..."
    rclone copy data/prices/ gdrive:prices/ --progress
    rclone copy data/financials/ gdrive:financials/ --progress
    echo "Backup completed!"
else
    echo ""
    echo "[3/4] No data to backup, skipping..."
fi

# Phase 4: Supabase 적재
if [[ "$SKIP_DB" == false ]]; then
    echo ""
    echo "[4/4] Loading to Supabase..."

    DB_LOAD_ARGS=""
    if [[ "$MARKET" == "kr" ]]; then
        DB_LOAD_ARGS="--kr-only"
    elif [[ "$MARKET" == "us" ]]; then
        DB_LOAD_ARGS="--us-only"
    fi

    if uv run --package stock-screener-data-pipeline python -m loaders.csv_to_db $DB_LOAD_ARGS; then
        echo "Supabase loading completed!"
    else
        echo "Supabase loading failed!"
        exit 1
    fi
else
    echo ""
    echo "[4/4] Skipping Supabase loading (--no-db)"
fi

echo ""
echo "============================================"
if [[ "$KR_SUCCESS" == true ]] && [[ "$US_SUCCESS" == true ]]; then
    echo "All tasks completed successfully!"
else
    echo "Completed with some rate limits."
    echo "Run with --resume to continue after rate limit resets."
fi
echo "Time: $(date)"
echo "============================================"

# Rate Limit이 있었으면 exit code 2 반환
if [[ "$KR_SUCCESS" == false ]] || [[ "$US_SUCCESS" == false ]]; then
    exit 2
fi
