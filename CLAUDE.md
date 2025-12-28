# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

미국(S&P 500 + 400 + 600 + Russell 2000) 및 한국(KOSPI + KOSDAQ) 시장을 지원하는 가치투자 스크리닝 도구. FastAPI 백엔드, 데이터 수집 파이프라인, 디스코드 봇, Next.js 프론트엔드로 구성된 멀티 서비스 모노레포.

## 상세 문서 (자동 로드)

- 실행 명령어: @.claude/rules/commands.md
- 아키텍처 및 데이터 흐름: @.claude/rules/architecture.md
- 개발 프로세스 및 배포: @.claude/rules/deployment.md
- 프론트엔드 스타일 가이드: @.claude/rules/frontend.md
- 비전 및 AI 로드맵: @.claude/rules/vision.md
- 데이터 백업 정책: @.claude/rules/data-policy.md
- 알림 시스템 가이드: @.claude/rules/alerts.md
- 개발 프로세스 가이드: @.claude/rules/development.md

## 관련 문서 (필요 시 참조)

| 문서 | 용도 | 언제 참조 |
|------|------|----------|
| `README.md` | 프로젝트 소개 | 새 기여자 온보딩, GitHub 페이지 |
| `SECURITY.md` | 보안 설정 (CORS, 인증, API) | 보안 관련 작업 시 |
| `ROADMAP.md` | 장기 로드맵 (Phase 1-3) | 다음 Phase 계획 시 |
| `TODO.md` | 상세 작업 목록 | 구현할 기능 선택 시 |

## 환경 변수

`.env` 파일에 필요:
- `SUPABASE_URL`, `SUPABASE_KEY` - 데이터베이스 (필수)
- `DART_API_KEY` - 한국 DART 재무제표 (KR 수집 시 필수)
- `DISCORD_BOT_TOKEN` - 디스코드 봇 (봇 사용 시)

## 현재 상태

**구현됨**:
- 미국/한국 주식 데이터 수집기 (전체 유니버스)
- 하이브리드 저장 (Supabase + CSV)
- GitHub Actions 워크플로우 (수집 + 백업)
- FastAPI 백엔드 API
- Next.js 프론트엔드 (Preset 전략, Tooltip UX, 페이지네이션)
- Vercel + Render 배포
- GitHub OAuth 인증 (Supabase Auth)
- 워치리스트 기능 (추가/삭제/조회)
- CORS 도메인 제한 (프로덕션 보안)
- Rate Limiting (slowapi: 스크리닝 30/min, 일반 100/min)
- 다크모드 (Tailwind class 전략, localStorage 저장)
- 알림 시스템 (지표 기반 알림 CRUD, /alerts 페이지)
- Advanced Filters (커스텀 지표 필터링, 20개 지표 지원)
- 프리셋 관리 페이지 (/presets, 사용자 프리셋 CRUD)
- 테스트 인프라 (Vitest + pytest)

**미구현**: 디스코드 봇 워치리스트/알림 연동, i18n, Toast/Skeleton 컴포넌트

**코드 내 알려진 TODO**:
- 입력 검증 강화
