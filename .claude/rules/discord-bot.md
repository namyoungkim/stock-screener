# 디스코드 봇 가이드

## 개요

Stock Screener 디스코드 봇은 서버 멤버들이 주식 정보를 조회하고, 개인 워치리스트와 알림을 관리할 수 있게 해줍니다.

---

## 명령어

### 조회 (공용)

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/stock {ticker}` | 종목 정보 조회 | `/stock AAPL` |
| `/search {query}` | 종목 검색 | `/search 삼성` |
| `/screen {preset}` | 프리셋 스크리닝 | `/screen graham` |
| `/presets` | 프리셋 목록 | `/presets` |

### 워치리스트 (개인)

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/watch {ticker}` | 워치리스트에 추가 | `/watch AAPL` |
| `/watchlist` | 내 워치리스트 조회 | `/watchlist` |
| `/unwatch {ticker}` | 워치리스트에서 삭제 | `/unwatch AAPL` |

### 알림 (개인)

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/alert {ticker} {metric} {operator} {value}` | 알림 생성 | `/alert AAPL pe_ratio <= 15` |
| `/alerts` | 내 알림 목록 | `/alerts` |
| `/delalert {alert_id}` | 알림 삭제 | `/delalert abc123...` |
| `/togglealert {alert_id}` | 알림 활성화/비활성화 | `/togglealert abc123...` |

---

## 지원 지표 (알림용)

| 이름 | 값 | 설명 |
|------|-----|------|
| P/E Ratio | `pe_ratio` | 주가수익비율 |
| P/B Ratio | `pb_ratio` | 주가순자산비율 |
| ROE | `roe` | 자기자본이익률 |
| RSI | `rsi` | 상대강도지수 (0-100) |
| Dividend Yield | `dividend_yield` | 배당수익률 |
| Price | `latest_price` | 현재가 |
| Graham Number | `graham_number` | 그레이엄 넘버 |
| 52W High | `fifty_two_week_high` | 52주 최고가 |
| 52W Low | `fifty_two_week_low` | 52주 최저가 |

---

## 프리셋 전략

| 프리셋 | 설명 |
|--------|------|
| `graham` | Graham Classic - P/E < 15, P/B < 1.5, D/E < 0.5 |
| `buffett` | Buffett Quality - ROE > 15%, Net Margin > 10% |
| `dividend` | Dividend Value - 배당수익률 > 3% |
| `deep_value` | Deep Value - P/B < 1, P/E < 10 |

---

## 개인화

각 디스코드 사용자는 Discord User ID로 식별되어 **개인화된 데이터**를 가집니다:

- 워치리스트: 각자 별도 관리
- 알림: 각자 별도 관리
- 다른 사용자의 데이터 접근 불가

> **참고**: 웹사이트와 디스코드는 별도의 데이터를 사용합니다. 웹에서 추가한 워치리스트는 디스코드에서 보이지 않습니다.

---

## 봇 설정 (관리자용)

### 1. Discord Developer Portal

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. **New Application** → 이름 입력 → **Create**
3. **Bot** 메뉴 → **Reset Token** → 토큰 복사
4. **OAuth2** → **URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`
5. 생성된 URL로 서버에 봇 초대

### 2. 환경변수

```bash
# .env
DISCORD_BOT_TOKEN=your_bot_token_here
API_BASE_URL=http://localhost:8000  # 또는 프로덕션 URL
```

### 3. 데이터베이스

Supabase SQL Editor에서 실행:
```bash
supabase/discord_schema.sql
```

### 4. 봇 실행

```bash
# 백엔드 서버 (터미널 1)
uv run --package stock-screener-backend uvicorn app.main:app --reload

# 디스코드 봇 (터미널 2)
uv run --package stock-screener-discord-bot python -m bot.main
```

---

## 관련 파일

| 파일 | 설명 |
|------|------|
| `discord-bot/bot/main.py` | 봇 메인 코드, 슬래시 명령어 |
| `discord-bot/bot/api.py` | 백엔드 API 클라이언트 |
| `backend/app/api/discord.py` | 디스코드 전용 API 엔드포인트 |
| `backend/app/services/discord_service.py` | 디스코드 서비스 로직 |
| `backend/app/models/discord.py` | Pydantic 모델 |
| `supabase/discord_schema.sql` | 디스코드 전용 테이블 |

---

## 문제 해결

### 슬래시 명령어가 안 보임

- 봇 재시작 후 1-2분 대기 (Discord 동기화 시간)
- 봇에 `applications.commands` 권한 확인

### "Stock not found" 오류

- 티커 대소문자 확인 (AAPL, 005930)
- 한국 주식은 숫자 티커 사용

### 워치리스트/알림 오류

- 백엔드 서버 실행 확인
- `discord_schema.sql` 테이블 생성 확인
