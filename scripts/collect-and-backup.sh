#!/bin/bash
# 로컬 데이터 수집 및 Google Drive 백업 스크립트
# 사용법: ./scripts/collect-and-backup.sh [kr|us|all] [--resume]
#
# Exit codes:
#   0 - 성공
#   1 - 일반 오류
#   2 - Rate Limit 감지 (진행 상황 저장됨, --resume으로 재시작 가능)

MARKET=${1:-all}
RESUME_FLAG=""

# --resume 플래그 확인
for arg in "$@"; do
    if [[ "$arg" == "--resume" ]]; then
        RESUME_FLAG="--resume"
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "============================================"
echo "Stock Data Collection & Backup"
echo "Market: $MARKET"
echo "Resume: ${RESUME_FLAG:-no}"
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

# KR 수집
KR_SUCCESS=true
if [[ "$MARKET" == "kr" || "$MARKET" == "all" ]]; then
    echo ""
    echo "[1/3] Collecting KR stocks..."
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

# US 수집
US_SUCCESS=true
if [[ "$MARKET" == "us" || "$MARKET" == "all" ]]; then
    echo ""
    echo "[2/3] Collecting US stocks..."
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

# 수집된 데이터가 있으면 백업
if [[ -d "data/prices" ]] && [[ -n "$(ls -A data/prices/ 2>/dev/null)" ]]; then
    echo ""
    echo "[3/3] Backing up to Google Drive..."
    rclone copy data/prices/ gdrive:stock-screener-backup/prices/ --progress
    rclone copy data/financials/ gdrive:stock-screener-backup/financials/ --progress
    echo "Backup completed!"
else
    echo ""
    echo "[3/3] No data to backup, skipping..."
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
