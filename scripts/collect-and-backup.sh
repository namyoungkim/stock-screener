#!/bin/bash
# 로컬 데이터 파이프라인: 수집 → 품질검사 → 백업 → DB 적재
#
# 사용법: ./scripts/collect-and-backup.sh [kr|us|all] [--resume] [--no-db] [--limit N]
#
# 옵션:
#   kr|us|all  - 수집할 시장 (기본값: all)
#   --resume   - Rate Limit 후 이어서 수집
#   --no-db    - Supabase 적재 건너뛰기
#   --limit N  - 각 시장별 N개만 수집 (테스트용)
#
# Exit codes:
#   0 - 성공
#   1 - 일반 오류
#   2 - Rate Limit 감지 (진행 상황 저장됨, --resume으로 재시작 가능)

# MARKET 결정: kr, us, all 중 하나만 허용
MARKET="all"
for arg in "$@"; do
    case "$arg" in
        kr|us|all)
            MARKET="$arg"
            break
            ;;
    esac
done

RESUME_FLAG=""
SKIP_DB=false
LIMIT=""

# 플래그 파싱
args=("$@")
for i in "${!args[@]}"; do
    arg="${args[$i]}"
    case "$arg" in
        --resume)
            RESUME_FLAG="--resume"
            ;;
        --no-db)
            SKIP_DB=true
            ;;
        --limit)
            # 다음 인자에서 숫자 가져오기
            next_idx=$((i + 1))
            if [[ $next_idx -lt ${#args[@]} ]]; then
                next_val="${args[$next_idx]}"
                # 숫자인지 확인
                if [[ "$next_val" =~ ^[0-9]+$ ]]; then
                    LIMIT="$next_val"
                else
                    echo "Error: --limit requires a numeric argument, got: $next_val"
                    exit 1
                fi
            fi
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
echo "Limit: ${LIMIT:-all}"
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

    # --limit 옵션 처리
    KR_TICKERS_ARGS=""
    if [[ -n "$LIMIT" ]]; then
        echo "Limiting to $LIMIT tickers..."
        KR_TICKERS_FILE="/tmp/kr_limit_tickers.txt"
        # CSV 파일에서 직접 티커 추출 (헤더 제외, 첫 번째 열)
        tail -n +2 "$PROJECT_DIR/data/companies/kr_companies.csv" \
            | cut -d',' -f1 \
            | head -$LIMIT > "$KR_TICKERS_FILE"
        KR_TICKERS_ARGS="--tickers-file $KR_TICKERS_FILE"
        echo "Created ticker file with $(wc -l < "$KR_TICKERS_FILE") tickers"
    fi

    if uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks --csv-only $RESUME_FLAG $KR_TICKERS_ARGS; then
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

    # --limit 옵션 처리
    US_TICKERS_ARGS=""
    if [[ -n "$LIMIT" ]]; then
        echo "Limiting to $LIMIT tickers..."
        US_TICKERS_FILE="/tmp/us_limit_tickers.txt"
        # CSV 파일에서 직접 티커 추출 (헤더 제외, 첫 번째 열)
        tail -n +2 "$PROJECT_DIR/data/companies/us_companies.csv" \
            | cut -d',' -f1 \
            | head -$LIMIT > "$US_TICKERS_FILE"
        US_TICKERS_ARGS="--tickers-file $US_TICKERS_FILE"
        echo "Created ticker file with $(wc -l < "$US_TICKERS_FILE") tickers"
    fi

    if uv run --package stock-screener-data-pipeline python -m collectors.us_stocks --csv-only $RESUME_FLAG $US_TICKERS_ARGS; then
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

# Phase 3: Google Drive 백업 (수집 데이터)
# NOTE: rclone gdrive: 는 root_folder_id로 stock-screener-backup 폴더를 가리킴
# 새 구조: data/YYYY-MM-DD/vN/ -> gdrive:YYYY-MM-DD/vN/
# YYYY-MM-DD = 실제 거래일 (파이프라인 실행일 아님)
# 예: 일요일(2026-01-05)에 실행 시 -> 2026-01-03/ (금요일 거래일) 백업
if [[ -L "data/latest" ]]; then
    echo ""
    echo "[3/5] Backing up collection data to Google Drive..."

    # Get the relative path from 'latest' symlink (e.g., "2026-01-03/v1")
    LATEST_PATH=$(readlink data/latest)
    echo "Backing up: $LATEST_PATH"

    # Backup versioned data (e.g., 2026-01-03/v1/)
    rclone copy "data/$LATEST_PATH" "gdrive:$LATEST_PATH" --progress

    # Backup companies (master data)
    if [[ -d "data/companies" ]]; then
        rclone copy data/companies/ gdrive:companies/ --progress
    fi

    echo "Collection data backup completed!"
else
    echo ""
    echo "[3/5] No 'latest' symlink found, skipping collection backup..."
fi

# Phase 4: Supabase 백업
echo ""
echo "[4/5] Backing up Supabase to Google Drive..."
uv run --package stock-screener-data-pipeline python -c "
import os
import pandas as pd
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print('SUPABASE_URL/KEY not set, skipping Supabase backup')
    exit(0)

client = create_client(url, key)

# Create backup directory: data/supabase/YYYY-MM-DD/
# NOTE: Supabase 백업은 실행일(today) 기준 (point-in-time 백업)
# 수집 데이터(data/YYYY-MM-DD/)와 달리 거래일이 아닌 실행일 사용
today = date.today().strftime('%Y-%m-%d')
backup_dir = Path('data/supabase') / today
backup_dir.mkdir(parents=True, exist_ok=True)

def export_table(client, table_name, output_path):
    '''Export all rows from a table with pagination.'''
    all_data = []
    offset = 0
    page_size = 1000

    while True:
        result = client.table(table_name).select('*').range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_data.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(output_path, index=False)
        print(f'Exported {len(all_data):,} {table_name}')

export_table(client, 'companies', backup_dir / 'companies.csv')
export_table(client, 'metrics', backup_dir / 'metrics.csv')
export_table(client, 'prices', backup_dir / 'prices.csv')

print(f'Supabase backup saved to {backup_dir}')
"

# Upload Supabase backup to Google Drive
if [[ -d "data/supabase" ]]; then
    rclone copy data/supabase/ gdrive:supabase/ --progress
    echo "Supabase backup uploaded to Google Drive!"
fi

# Phase 5: Supabase 적재
if [[ "$SKIP_DB" == false ]]; then
    echo ""
    echo "[5/5] Loading to Supabase..."

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
    echo "[5/5] Skipping Supabase loading (--no-db)"
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
