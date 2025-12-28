# 데이터 전략 및 백업 정책

## 구현 상태

| 항목 | 상태 |
|------|------|
| Supabase 저장 | ✅ 구현됨 |
| CSV 로컬 저장 | ✅ 구현됨 |
| GitHub Artifacts 백업 | ✅ 구현됨 (30일 보관) |
| Google Drive 백업 | ✅ 워크플로우 구현됨 (RCLONE_CONFIG 설정 필요) |

---

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
| 일별 가격 | 평일 매일 | 무기한 | CSV → Google Drive |
| 재무제표 | 평일 매일 | 무기한 | CSV → Google Drive |
| Supabase 전체 | 평일 매일 | 4주 롤링 | 스냅샷 → Google Drive |

---

## 구현 방식

### 필요 도구
- **rclone**: Google Drive 연동 CLI
- **GitHub Actions**: 스케줄 실행

### Google Drive 설정 가이드

#### 1. Google Cloud 서비스 계정 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **APIs & Services > Credentials** 이동
4. **Create Credentials > Service Account** 클릭
5. 서비스 계정 이름 입력 후 생성
6. **Keys** 탭에서 **Add Key > Create new key > JSON** 선택
7. JSON 키 파일 다운로드

#### 2. Google Drive API 활성화

1. **APIs & Services > Library** 이동
2. "Google Drive API" 검색
3. **Enable** 클릭

#### 3. Drive 폴더 공유

1. Google Drive에서 `stock-screener-backup` 폴더 생성
2. 폴더 우클릭 > **Share**
3. 서비스 계정 이메일 추가 (형식: `xxx@xxx.iam.gserviceaccount.com`)
4. **Editor** 권한 부여

#### 4. rclone.conf 생성

```ini
[gdrive]
type = drive
scope = drive
service_account_file_contents = <JSON 키 파일 내용 (한 줄로)>
root_folder_id = <Drive 폴더 ID (URL에서 추출)>
```

**팁**: JSON을 한 줄로 변환하려면:
```bash
cat credentials.json | jq -c .
```

#### 5. GitHub Secret 설정

1. Repository **Settings > Secrets and variables > Actions**
2. **New repository secret** 클릭
3. Name: `RCLONE_CONFIG`
4. Value: 위에서 생성한 rclone.conf 내용 전체 붙여넣기

### 워크플로우

`backup.yml`에 Google Drive 백업이 자동으로 포함됨:
- `RCLONE_CONFIG` secret이 설정되면 자동 활성화
- 설정되지 않으면 GitHub Artifacts만 사용 (기존 동작)

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
