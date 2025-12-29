# Stock Screener Roadmap

> **비전**: 채팅 기반 AI Agent가 가치투자를 제안하고 컨설팅하는 개인 투자 어드바이저

상세: @.claude/rules/vision.md

---

## Phase 요약

| Phase | 설명 | 상태 |
|-------|------|------|
| 1 | 펀더멘털 MVP | ✅ 완료 |
| 2 | 타이밍 지표 | ✅ 완료 |
| 3 | 고급 분석 + 인증 | ✅ 완료 |
| 3.5 | 투자 인사이트 (규칙 기반) | ✅ 완료 |
| 4 | RAG 기반 AI 분석 | 예정 |
| 5 | AI 투자 어드바이저 | 예정 |

---

## 마일스톤

| # | 설명 | 상태 |
|---|------|------|
| M1-M6 | MVP ~ 워치리스트 | ✅ |
| M7 | 알림 시스템 | ✅ |
| M7.5 | 투자 인사이트 | ✅ |
| M8 | 디스코드 봇 배포 | 의사결정 필요 |
| M9 | RAG 인프라 | 예정 |
| M10 | AI 종목 분석 | 예정 |
| M11 | 채팅 AI 에이전트 | 예정 |

---

## 디스코드 봇 배포 (의사결정 필요)

현재 로컬 Mac에서 수동 실행 중. 24/7 운영을 위한 배포 방식 결정 필요.

| 옵션 | 비용 | 특징 |
|------|------|------|
| Mac 자체 호스팅 | 무료 | Mac 항상 켜야 함 |
| AWS EC2 | 무료(1년)→$8/월 | 안정적, Runner 겸용 가능 |
| Fly.io | 무료 | 설정 간단 |
| Railway | $5 크레딧 | 자동 배포 |
| Oracle Cloud | 무료 | 계정 생성 어려움 |

상세: @.claude/rules/discord-bot-deployment.md

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI, Python 3.11+ |
| Frontend | Next.js 14, TailwindCSS |
| Database | Supabase (PostgreSQL) |
| Data | yfinance, pykrx |
| AI (예정) | Claude API, pgvector |

---

## 데이터 전략

상세: @.claude/rules/data-policy.md

| 저장소 | 용도 |
|--------|------|
| Supabase | 최신 데이터 (API) |
| Google Drive | 히스토리 아카이브 |
| GitHub | 코드만 |

---

## 수익 모델 (향후)

| 티어 | 가격 | 기능 |
|------|------|------|
| Free | $0 | 기본 스크리닝, 워치리스트 5개 |
| Pro | $9/월 | 전체 기능 + 알림 |
| Premium | $19/월 | Pro + AI 컨설팅 |
