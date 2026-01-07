#!/bin/bash
# Stock Screener Data Pipeline Runner
# This script is called by LaunchAgent to run the data collection pipeline

set -e

# Change to project root
cd /Users/leo/project/stock-screener

# Load environment variables from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Log start time
echo "=========================================="
echo "Pipeline started at $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# Run the data pipeline CLI
cd data-pipeline
uv run python -m cli.main collect all

# Log end time
echo "=========================================="
echo "Pipeline completed at $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
