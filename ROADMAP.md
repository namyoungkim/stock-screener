# Stock Screener Roadmap

가치투자 스크리닝 도구의 장기 개발 로드맵입니다.

---

## Phase 1: 펀더멘털 완성 (현재)

### 목표
기본적인 가치투자 스크리닝이 가능한 MVP 완성

### 완료된 작업
- [x] Supabase 스키마 설계 및 적용
- [x] US/KR 데이터 수집기 구현
- [x] FastAPI 백엔드 API
- [x] Next.js 프론트엔드
- [x] Preset 전략 (Graham, Buffett, Dividend, Deep Value)
- [x] Tooltip UX (금융 용어 설명)

### 진행 중
- [ ] 전체 데이터 수집 (S&P 500 + KOSPI/KOSDAQ)
- [ ] 하이브리드 데이터 저장 전략
- [ ] 백업 자동화

### 예정
- [ ] Graham Number 계산 추가
- [ ] 52주 최고/최저가 추가

---

## Phase 2: 타이밍 지표 추가

### 목표
매수 타이밍 판단을 위한 기본 기술적 지표 추가

### 예정 지표
| 지표 | 용도 |
|------|------|
| RSI (14일) | 과매수/과매도 판단 |
| 52주 최고/최저가 | 현재 가격 위치 파악 |
| 이동평균 (20, 50, 200일) | 추세 판단 |
| 거래량 변화율 | 관심도 변화 감지 |

### 구현 계획
- prices 테이블에 기술적 지표 컬럼 추가
- 수집기에서 계산 후 저장
- 프론트엔드에 차트 추가 (선택)

---

## Phase 3: 고급 분석

### 목표
심화 분석 및 알림 기능

### 예정 기능
| 기능 | 설명 |
|------|------|
| MACD | 추세 전환 신호 |
| Money Flow Index | 자금 흐름 분석 |
| 볼린저 밴드 | 변동성 기반 매매 신호 |
| 알림 시스템 | 조건 충족 시 디스코드/이메일 알림 |
| 포트폴리오 추적 | 보유 종목 성과 분석 |

---

## 데이터 전략

### 하이브리드 저장 방식

**Supabase (무료 티어, ~100MB 제한)**
- companies: 전체 종목 마스터
- metrics: 최신 지표만 유지
- prices: 최근 1개월
- watchlist/alerts: 사용자 데이터

**로컬/GitHub (무제한)**
- `data/prices/`: 전체 가격 히스토리 (CSV)
- `data/financials/`: 분기별 재무제표 (CSV)
- `data/backup/`: 주간 Supabase 백업

### 비용 계획
| 단계 | 예상 비용 |
|------|----------|
| MVP (현재) | 무료 (Supabase Free + Vercel Free) |
| 확장 시 | Neon ($0) 또는 Supabase Pro ($25/월) |

---

## 기술 스택

### 현재
- **Backend**: FastAPI, Python 3.11+
- **Frontend**: Next.js 14, React, TailwindCSS
- **Database**: Supabase (PostgreSQL)
- **Data**: yfinance, pykrx, OpenDartReader

### 고려 중
- **차트**: Recharts 또는 Lightweight Charts
- **알림**: Discord Webhook, Resend (이메일)
- **배포**: Vercel (Frontend), Railway/Fly.io (Backend)

---

## 마일스톤

| 마일스톤 | 설명 | 상태 |
|---------|------|------|
| M1 | MVP 완성 (스크리닝 동작) | 진행 중 |
| M2 | 전체 데이터 수집 완료 | 예정 |
| M3 | 배포 (Vercel + Backend) | 예정 |
| M4 | Phase 2 지표 추가 | 예정 |
| M5 | 알림 시스템 | 예정 |
