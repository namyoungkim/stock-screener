# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

미국(S&P 500 + 400 + 600 + Russell 2000) 및 한국(KOSPI + KOSDAQ) 시장을 지원하는 가치투자 스크리닝 도구. FastAPI 백엔드, 데이터 수집 파이프라인, 디스코드 봇, Next.js 프론트엔드로 구성된 멀티 서비스 모노레포.

## 핵심 가치

> **가치투자를 할만한 종목을 찾고 어떤 액션을 지금 해야하는지 인사이트 제공**

### 설계 원칙

1. **인사이트 우선**: 데이터 나열 < 의미 있는 해석. "이 종목 살만해?"에 명확한 답변
2. **액션 지향**: 모든 분석에는 다음 행동 제안 포함 (매수/관망/회피)
3. **리스크 명시**: 위험 요소는 항상 눈에 띄게 표시, 면책 조항 포함
4. **컨텍스트 제공**: 절대 수치보다 상대적 위치 강조 (섹터/시장 평균 대비)

상세 요구사항: `docs/PRD.md` 참조

## 상세 문서 (자동 로드)

- 실행 명령어: @.claude/rules/commands.md
- 아키텍처 및 데이터 흐름: @.claude/rules/architecture.md
- 개발 프로세스 및 배포: @.claude/rules/deployment.md
- 프론트엔드 스타일 가이드: @.claude/rules/frontend.md
- 비전 및 AI 로드맵: @.claude/rules/vision.md
- 데이터 백업 정책: @.claude/rules/data-policy.md
- 알림 시스템 가이드: @.claude/rules/alerts.md
- 디스코드 봇 가이드: @.claude/rules/discord-bot.md
- 디스코드 봇 배포 옵션: @.claude/rules/discord-bot-deployment.md
- 개발 프로세스 가이드: @.claude/rules/development.md
- Self-hosted Runner 설정: @.claude/rules/self-hosted-runner.md

## 문서 계층 구조

PRD.md → ROADMAP.md → TODO.md 순서로 일관성을 유지해야 합니다.

| 문서 | 역할 | 변경 시 |
|------|------|---------|
| `docs/PRD.md` | 무엇을 (요구사항) | ROADMAP, TODO에 반영 |
| `ROADMAP.md` | 언제/순서 (마일스톤) | TODO에 반영 |
| `TODO.md` | 구체적 작업 목록 | PRD 기준 확인 |

## 관련 문서 (필요 시 참조)

| 문서 | 용도 | 언제 참조 |
|------|------|----------|
| `docs/PRD.md` | 제품 요구사항 (핵심 가치, 설계 원칙, UX) | 기능 구현, 제품 방향 결정 시 |
| `README.md` | 프로젝트 소개 | 새 기여자 온보딩, GitHub 페이지 |
| `SECURITY.md` | 보안 설정 (CORS, 인증, API) | 보안 관련 작업 시 |
| `ROADMAP.md` | 마일스톤 (Phase 1-5) | 다음 Phase 계획 시 |
| `TODO.md` | 상세 작업 목록 | 구현할 기능 선택 시 |

## 환경 변수

`.env` 파일에 필요:
- `SUPABASE_URL`, `SUPABASE_KEY` - 데이터베이스 (필수)
- `DISCORD_BOT_TOKEN` - 디스코드 봇 (봇 사용 시)

## 현재 상태

**구현됨**:
- 미국/한국 주식 데이터 수집기 (US 2,810개 + KR 2,788개 = 5,598개)
- 통합 데이터 파이프라인 (`./scripts/collect-and-backup.sh`)
  - 수집 → 품질검사 → 자동재수집 → Google Drive 백업 → Supabase 적재
- 품질검사 자동화 (유니버스 커버리지, 대형주 누락, 지표 완성도)
- KR 수집기 최적화 (pykrx + yfinance 하이브리드)
- 기술적 지표 수집 (RSI, MFI, MACD, Bollinger Bands, Volume Change)
- 가치투자 지표 (EPS, BPS, Graham Number)
- 하이브리드 저장 (Supabase + CSV)
- yfinance Rate Limit 대처 (진행 상황 저장 + `--resume` 재시작)
- FastAPI 백엔드 API
- Next.js 프론트엔드 (Preset 전략, Tooltip UX, 페이지네이션)
- Vercel + Render 배포
- 소셜 로그인 (GitHub + Google OAuth, Supabase Auth)
- 워치리스트 기능 (추가/삭제/조회)
- CORS 도메인 제한 (프로덕션 보안)
- Rate Limiting (slowapi: 스크리닝 30/min, 일반 100/min)
- 다크모드 (Tailwind class 전략, localStorage 저장)
- 알림 시스템 (지표 기반 알림 CRUD, /alerts 페이지)
- Advanced Filters (커스텀 지표 필터링, 20개 지표 지원)
- 프리셋 관리 페이지 (/presets, 사용자 프리셋 CRUD)
- 테스트 인프라 (Vitest + pytest)
- 입력 검증 강화 (MetricType Enum 화이트리스트, UUID/범위/길이 검증)
- API 키 노출 방지 (환경변수 검증, 로그 마스킹, DB 연결 검증)
- 디스코드 봇 워치리스트/알림 연동 (/watch, /watchlist, /alert, /alerts 등)
- 투자 인사이트 (Phase 3.5) - 규칙 기반 점수/신호, 액션 가이드, 리스크 경고

**다음 단계** (Phase 4): AI 분석 - RAG 인프라, Claude API 연동

**미구현**: Phase 5 (AI 어드바이저), 운영/인프라 (봇 배포, i18n, 도메인)
