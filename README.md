# Stock Screener

미국(S&P 500 + 400 + 600 + Russell 2000) 및 한국(KOSPI + KOSDAQ) 시장을 지원하는 가치투자 스크리닝 도구입니다.

## 주요 기능

- **스크리닝**: 밸류에이션, 수익성, 재무 건전성 지표로 주식 필터링
- **워치리스트**: 관심 종목 저장 및 추적
- **알림**: 조건 충족 시 알림 수신
- **다국어 지원**: 영어/한국어 지원
- **디스코드 봇**: 디스코드에서 직접 스크리닝

## 기술 스택

- **프론트엔드**: Next.js 14, Tailwind CSS, next-intl
- **백엔드**: FastAPI
- **데이터베이스**: Supabase (PostgreSQL)
- **봇**: discord.py
- **데이터**: yfinance, pykrx, OpenDartReader
- **배포**: Vercel (Frontend), Render (Backend)

## 프로젝트 구조

```
stock-screener/
├── backend/           # FastAPI 서버
├── frontend/          # Next.js 앱
├── data-pipeline/     # 데이터 수집 스크립트
├── discord-bot/       # 디스코드 봇
└── .github/workflows/ # GitHub Actions
```

## 시작하기

### 필수 조건

- Python 3.11+
- Node.js 18+
- Supabase 계정
- FMP API 키 (무료)
- 디스코드 봇 토큰

### 설치

1. 저장소 클론
```bash
git clone https://github.com/namyoungkim/stock-screener.git
cd stock-screener
```

2. 의존성 설치
```bash
uv sync
```

3. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

## 환경 변수

```
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# FMP (Financial Modeling Prep)
FMP_API_KEY=your_fmp_key

# DART (한국)
DART_API_KEY=your_dart_key

# Discord
DISCORD_BOT_TOKEN=your_discord_token
```

## 배포 URL

- **Frontend**: https://stock-screener-inky.vercel.app
- **Backend API**: https://stock-screener-api-c0kc.onrender.com

## 라이선스

MIT
