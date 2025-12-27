# 데이터 전략 및 백업 정책

## 하이브리드 저장 방식

| 저장소 | 용도 | 용량 | 비용 |
|--------|------|------|------|
| Supabase | 최신 데이터 (API 서빙) | ~100MB | 무료 |
| Google Drive | 히스토리 아카이브 | 15GB | 무료 |
| GitHub | 코드만 (데이터 제외) | - | 무료 |

---

## Supabase (최신 데이터)

API 서빙용 최신 데이터만 유지 (무료 티어 제한 대응)

| 테이블 | 보관 정책 |
|--------|----------|
| companies | 전체 (마스터 데이터) |
| metrics | 최신만 (덮어쓰기) |
| prices | 최근 1개월 |
| watchlist | 전체 (사용자 데이터) |
| alerts | 전체 (사용자 데이터) |

---

## Google Drive (히스토리 아카이브)

장기 보관 데이터

```
gdrive:stock-screener-backup/
├── prices/
│   ├── us_prices_20250101.csv
│   ├── us_prices_20250102.csv
│   └── ...
├── financials/
│   ├── us_metrics_20250101.csv
│   └── ...
└── backups/
    ├── supabase_20250105.sql
    └── ...
```

---

## 백업 정책

| 데이터 | 주기 | 보관 기간 | 방식 |
|--------|------|----------|------|
| 일별 가격 | 매일 | 무기한 | CSV → Google Drive |
| 재무제표 | 분기 | 무기한 | CSV → Google Drive |
| Supabase 전체 | 주 1회 | 4주 롤링 | pg_dump → Google Drive |

---

## 구현 방식

### 필요 도구
- **rclone**: Google Drive 연동 CLI
- **GitHub Actions**: 스케줄 실행

### 설정

1. Google Cloud 서비스 계정 생성
2. Google Drive API 활성화
3. 서비스 계정에 Drive 폴더 공유
4. GitHub Secrets에 credentials 저장

### 워크플로우 예시

```yaml
# .github/workflows/backup-to-gdrive.yml
name: Backup to Google Drive

on:
  schedule:
    - cron: '0 0 * * 0'  # 매주 일요일 00:00 UTC
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup rclone
        run: |
          curl https://rclone.org/install.sh | sudo bash
          mkdir -p ~/.config/rclone
          echo "${{ secrets.RCLONE_CONFIG }}" > ~/.config/rclone/rclone.conf

      - name: Backup data files
        run: |
          rclone copy ./data gdrive:stock-screener-backup/data --progress

      - name: Backup Supabase (optional)
        run: |
          # pg_dump 또는 Supabase CLI 사용
          # supabase db dump > backup.sql
          # rclone copy backup.sql gdrive:stock-screener-backup/backups/
```

### rclone.conf 예시

```ini
[gdrive]
type = drive
scope = drive
service_account_file = /path/to/credentials.json
root_folder_id = <folder-id>
```

---

## 복구 절차

### 일별 가격 복구
```bash
rclone copy gdrive:stock-screener-backup/prices/us_prices_20250101.csv ./data/prices/
```

### Supabase 복구
```bash
# 백업 다운로드
rclone copy gdrive:stock-screener-backup/backups/supabase_20250105.sql ./

# Supabase에 복원
psql $DATABASE_URL < supabase_20250105.sql
```

---

## 데이터 정리 (Supabase 용량 관리)

### 오래된 가격 데이터 삭제
```sql
-- 1개월 이전 가격 데이터 삭제
DELETE FROM prices
WHERE date < NOW() - INTERVAL '1 month';
```

### 자동화 (GitHub Actions)
```yaml
- name: Clean old prices
  run: |
    psql ${{ secrets.DATABASE_URL }} -c "DELETE FROM prices WHERE date < NOW() - INTERVAL '1 month';"
```
