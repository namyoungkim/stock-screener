# 개발 프로세스 및 배포

## 로컬 테스트 후 배포 (필수)

프론트엔드/백엔드 변경 시 **반드시 로컬에서 테스트 후 커밋/푸시**:

```bash
# 1. 백엔드 서버 실행
uv run --package stock-screener-backend uvicorn app.main:app --reload

# 2. 프론트엔드 서버 실행 (별도 터미널)
cd frontend && npm run dev

# 3. http://localhost:3000 에서 테스트

# 4. 테스트 완료 후 커밋 & 푸시
git add . && git commit -m "변경 내용" && git push
```

## 배포 환경

| 서비스 | 플랫폼 | URL |
|--------|--------|-----|
| Frontend | Vercel | https://stock-screener-inky.vercel.app |
| Backend | Render | https://stock-screener-api-c0kc.onrender.com |
| Database | Supabase | (대시보드에서 확인) |

- **Vercel**: `main` 브랜치 푸시 시 자동 배포
- **Render**: `main` 브랜치 푸시 시 자동 배포 (무료 티어: 15분 비활성 시 슬립)

---

## 자동화 인프라

| 구성요소 | 설정 |
|---------|------|
| 데이터 수집 | EC2 Self-hosted Runner (yfinance rate limit 회피) |
| 스케줄 | 평일 매일 00:00 UTC (update-data.yml) |
| 백업 | 수집 완료 후 자동 실행 (backup.yml - workflow_run) |

자세한 설정: @.claude/rules/self-hosted-runner.md
