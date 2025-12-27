# Stock Screener

미국(S&P 500 + 400 + 600 + Russell 2000) 및 한국(KOSPI + KOSDAQ) 시장을 지원하는 가치투자 스크리닝 도구입니다.

## 주요 기능

### 스크리닝
- **프리셋 전략**: Graham Classic, Buffett Quality, Dividend Value, Deep Value
- **커스텀 필터**: P/E, P/B, ROE, Dividend Yield 등 다양한 지표로 필터링
- **페이지네이션**: 대량 데이터 효율적 탐색 (페이지당 50개)

### 인증 및 개인화
- **GitHub OAuth**: Supabase Auth 기반 소셜 로그인
- **워치리스트**: 관심 종목 저장 및 관리 (로그인 필요)

### 기술 지표
- **기본 지표**: P/E, P/B, P/S, EV/EBITDA, ROE, ROA, Margin 등
- **모멘텀 지표**: RSI, MACD, 볼린저 밴드, MFI
- **가격 지표**: 52주 고/저, 50일/200일 이동평균, Beta

### 추가 기능
- **디스코드 봇**: 디스코드에서 직접 스크리닝 (/stock, /screen, /presets)

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

### Backend / Data Pipeline (.env)

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_key

# DART (한국 재무제표)
DART_API_KEY=your_dart_key

# Discord
DISCORD_BOT_TOKEN=your_discord_token
```

### Frontend (.env.local)

```bash
# Supabase (공개 가능한 키)
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000  # 로컬
# NEXT_PUBLIC_API_URL=https://stock-screener-api-c0kc.onrender.com  # 프로덕션
```

## 배포

### 배포 URL

| 서비스 | 플랫폼 | URL |
|--------|--------|-----|
| Frontend | Vercel | https://stock-screener-inky.vercel.app |
| Backend | Render | https://stock-screener-api-c0kc.onrender.com |
| Database | Supabase | (대시보드에서 확인) |

### Vercel (Frontend)

1. GitHub 저장소 연결
2. 환경 변수 설정:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL`
3. `main` 브랜치 푸시 시 자동 배포

### Render (Backend)

1. GitHub 저장소 연결
2. Build Command: `pip install -r backend/requirements.txt`
3. Start Command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. 환경 변수 설정:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
5. `main` 브랜치 푸시 시 자동 배포

### Supabase

1. 프로젝트 생성 후 `supabase/schema.sql` 실행
2. Authentication > Providers에서 GitHub OAuth 활성화
3. Site URL 및 Redirect URL 설정:
   - Site URL: `https://your-domain.vercel.app`
   - Redirect URL: `https://your-domain.vercel.app/auth/callback`

## 라이선스

MIT
