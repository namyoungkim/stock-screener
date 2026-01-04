"""Common configuration for data pipeline."""

from pathlib import Path

# Data directories
DATA_DIR = Path(__file__).parent.parent.parent / "data"
COMPANIES_DIR = DATA_DIR / "companies"

# Date format for directory naming
DATE_FORMAT = "%Y-%m-%d"

# =============================================================================
# Rate Limit 설정 (수집기 공통)
# =============================================================================

# 배치 크기
BATCH_SIZE_INFO = 10  # .info 호출 배치 (yfinance rate limit에 민감)
BATCH_SIZE_HISTORY = 500  # history 다운로드 배치 (yf.download는 관대함)
BATCH_SIZE_PRICES = 500  # prices 다운로드 배치

# 딜레이 설정 (초)
BASE_DELAY_INFO = 2.5  # .info 호출 후 기본 딜레이
DELAY_JITTER_INFO = 1.0  # .info 랜덤 지터 (0 ~ 이 값)

BASE_DELAY_HISTORY = 0.5  # history 다운로드 후 기본 딜레이
DELAY_JITTER_HISTORY = 0.5  # history 랜덤 지터

# 연속 실패 감지
MAX_CONSECUTIVE_FAILURES = 10  # 이 횟수만큼 연속 실패 시 백오프

# 점진적 백오프 시간 (초) - 인덱스는 backoff_count
BACKOFF_TIMES = [60, 120, 180, 300, 600]  # 1분, 2분, 3분, 5분, 10분
MAX_BACKOFFS = 5  # 최대 백오프 횟수 (초과 시 중단)

# 전체 라운드 재시도 대기 시간 (초)
RATE_LIMIT_WAIT_HISTORY = 120  # 2분 (history용 - yf.download는 관대함)
RATE_LIMIT_WAIT_INFO = 600  # 10분 (metrics용 - .info()는 민감함)

# 타임아웃 설정 (초)
YFINANCE_INFO_TIMEOUT = 30  # stock.info 호출 타임아웃
YFINANCE_HISTORY_TIMEOUT = 60  # stock.history 호출 타임아웃
YFINANCE_DOWNLOAD_TIMEOUT = 120  # yf.download 호출 타임아웃
