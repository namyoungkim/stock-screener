# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

미국(S&P 500) 및 한국 시장을 지원하는 가치투자 스크리닝 도구. FastAPI 백엔드, 데이터 수집 파이프라인, 디스코드 봇, Next.js 프론트엔드로 구성된 멀티 서비스 모노레포 (프론트엔드는 아직 미구현).

## 실행 명령어

### 의존성 설치
```bash
uv sync
```

### 백엔드
```bash
uv run --package stock-screener-backend uvicorn app.main:app --reload
```

### 데이터 파이프라인
```bash
uv run --package stock-screener-data-pipeline python -m collectors.us_stocks   # 미국 주식
uv run --package stock-screener-data-pipeline python -m collectors.kr_stocks   # 한국 주식
```

### 코드 품질
```bash
uv run ruff check .      # 린트 검사
uv run ruff format .     # 포맷팅
uv run ty check          # 타입 체크
uv run pytest            # 테스트
```

## 아키텍처

```
stock-screener/
├── pyproject.toml        # 루트 (uv 워크스페이스 + 도구 설정)
├── backend/              # FastAPI REST API (Python 3.11+)
│   ├── pyproject.toml    # 백엔드 의존성
│   └── app/
│       ├── main.py       # 진입점 (CORS, 헬스체크)
│       ├── api/          # 라우트 핸들러 (스캐폴드)
│       ├── models/       # Pydantic 모델 (스캐폴드)
│       ├── services/     # 비즈니스 로직 (스캐폴드)
│       └── core/         # 설정 및 유틸리티 (스캐폴드)
├── data-pipeline/        # 데이터 수집 스크립트
│   ├── pyproject.toml    # 파이프라인 의존성
│   ├── collectors/
│   │   ├── us_stocks.py  # S&P 500 수집 (yfinance + FMP API)
│   │   └── kr_stocks.py  # 한국 주식 수집 (OpenDartReader)
│   └── processors/       # 데이터 변환 (스캐폴드)
├── discord-bot/          # 디스코드 인터페이스
│   └── pyproject.toml    # 봇 의존성
├── tests/                # 테스트 디렉토리
└── .github/workflows/    # GitHub Actions 스케줄 데이터 수집
```

### 데이터 흐름
- **미국 주식**: Wikipedia (S&P 500 티커) → yfinance (가격/재무) → Supabase
- **한국 주식**: OpenDartReader (DART API) → Supabase
- **자동화**: GitHub Actions가 매주 일요일 00:00 UTC에 수집기 실행

### 주요 의존성
- 백엔드: FastAPI, asyncpg, Pydantic, httpx
- 데이터 파이프라인: yfinance, opendartreader, pandas, supabase-py
- 데이터베이스: Supabase (PostgreSQL)

## 환경 변수

`.env` 파일에 필요 (`.env.example` 참고):
- `SUPABASE_URL`, `SUPABASE_KEY` - 데이터베이스
- `FMP_API_KEY` - Financial Modeling Prep (미국 주식)
- `DART_API_KEY` - 한국 DART 시스템
- `DISCORD_BOT_TOKEN` - 디스코드 봇

## 현재 상태

**구현됨**: 미국/한국 주식 데이터 수집기, GitHub Actions 워크플로우, FastAPI 스켈레톤
**미구현**: API 라우트, Pydantic 모델, 서비스 레이어, 스크리닝 로직, 워치리스트, 알림, 프론트엔드, 디스코드 봇 로직

**코드 내 알려진 TODO**:
- `kr_stocks.py`: KRX 티커 가져오기 미구현
- CORS가 "*"로 설정됨 (프로덕션에서는 제한 필요)
