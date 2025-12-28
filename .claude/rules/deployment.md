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

## 데이터 수집 인프라

### 현재: 로컬 통합 파이프라인

```bash
./scripts/collect-and-backup.sh         # 전체 (KR → US → 백업 → DB)
./scripts/collect-and-backup.sh --no-db # DB 적재 제외
```

**파이프라인 단계:**
1. KR 수집 (품질검사 + 자동재수집)
2. US 수집 (품질검사 + 자동재수집)
3. Google Drive 백업 (rclone)
4. Supabase 적재 (csv_to_db)

| 항목 | 설명 |
|------|------|
| 수집 | 로컬 Mac에서 수동 실행 |
| 품질검사 | 유니버스 커버리지 95%, 대형주 누락 검사 |
| 백업 | rclone → Google Drive |
| DB 적재 | CSV → Supabase (companies, metrics, prices) |
| 장점 | 빠른 속도, 무료, Rate Limit 회피 용이 |
| 단점 | 수동 실행 필요 |

### 참고: Self-hosted Runner (미사용)

EC2 t3.micro의 리소스 제한(1GB RAM, 스레드 한계)으로 현재 미사용.
향후 Oracle Cloud (24GB RAM 무료) 또는 스펙 업그레이드 시 재검토.

설정 가이드: @.claude/rules/self-hosted-runner.md
