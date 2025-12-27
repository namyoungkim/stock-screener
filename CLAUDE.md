# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

미국(S&P 500 + 400 + 600 + Russell 2000) 및 한국(KOSPI + KOSDAQ) 시장을 지원하는 가치투자 스크리닝 도구. FastAPI 백엔드, 데이터 수집 파이프라인, 디스코드 봇, Next.js 프론트엔드로 구성된 멀티 서비스 모노레포.

## 상세 문서

- 실행 명령어: @.claude/rules/commands.md
- 아키텍처 및 데이터 흐름: @.claude/rules/architecture.md
- 개발 프로세스 및 배포: @.claude/rules/deployment.md

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
- Next.js 프론트엔드 (Preset 전략, Tooltip UX)
- Vercel + Render 배포

**미구현**: 워치리스트, 알림, 디스코드 봇 로직

**코드 내 알려진 TODO**:
- CORS가 "*"로 설정됨 (프로덕션에서는 제한 필요)
