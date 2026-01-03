# 데이터 전략 및 백업 정책

## 구현 상태

| 항목 | 상태 |
|------|------|
| Supabase 저장 | ✅ 구현됨 |
| CSV 로컬 저장 | ✅ 구현됨 |
| GitHub Artifacts 백업 | ✅ 구현됨 (30일 보관) |
| Google Drive 백업 | ✅ 워크플로우 구현됨 (RCLONE_CONFIG 설정 필요) |
| prices 자동 정리 | ✅ 구현됨 (1개월 이전 삭제) |

---

## Supabase 무료 티어 제한 (2025)

| 항목 | 제한 |
|------|------|
| 데이터베이스 스토리지 | **500MB** |
| 파일 스토리지 | 1GB |
| 대역폭 | 10GB |
| 월간 활성 사용자 (MAU) | 10,000명 |
| 무료 프로젝트 | 2개 |
| 비활성 시 | 자동 일시중지 |

> 500MB 초과 시 읽기 전용 모드로 전환됩니다.

### 예상 사용량

| 테이블 | 예상 용량 | 비고 |
|--------|----------|------|
| companies | ~3MB | 마스터 데이터 |
| metrics | ~6MB | 최신만 (upsert) |
| prices | ~25MB | 1개월 유지 |
| watchlist | ~1MB | 사용자 데이터 |
| alerts | ~1MB | 사용자 데이터 |
| user_presets | ~1MB | 사용자 데이터 |
| discord_watchlist | ~1MB | 디스코드 사용자 데이터 |
| discord_alerts | ~1MB | 디스코드 사용자 데이터 |
| 인덱스 | ~20MB | 데이터의 30~50% |
| **총계** | **~60MB** | 제한의 12% |

---

## 하이브리드 저장 방식

| 저장소 | 용도 | 용량 | 비용 |
|--------|------|------|------|
| Supabase | 최신 데이터 (API 서빙) | ~60MB | 무료 |
| Google Drive | 히스토리 아카이브 | 15GB | 무료 |
| GitHub | 코드만 (데이터 제외) | - | 무료 |

---

## Supabase (최신 데이터)

API 서빙용 최신 데이터만 유지 (무료 티어 제한 대응)

| 테이블 | 보관 정책 | 구현 |
|--------|----------|------|
| companies | 전체 (마스터 데이터) | ✅ |
| metrics | 최신만 (덮어쓰기) | ✅ upsert |
| prices | 최근 1개월 | ✅ backup.yml에서 자동 삭제 |
| watchlist | 전체 (웹 사용자 데이터) | ✅ |
| alerts | 전체 (웹 사용자 데이터) | ✅ |
| user_presets | 전체 (웹 사용자 데이터) | ✅ |
| discord_watchlist | 전체 (디스코드 사용자 데이터) | ✅ |
| discord_alerts | 전체 (디스코드 사용자 데이터) | ✅ |

---

## Google Drive (히스토리 아카이브)

장기 보관 데이터

> **NOTE**: rclone `gdrive:` 리모트는 `root_folder_id`로 `stock-screener-backup` 폴더를 가리킴.
> 따라서 `gdrive:2026-01-03/v1/`은 `Google Drive/stock-screener-backup/2026-01-03/v1/`을 의미함.

```
Google Drive/stock-screener-backup/  (rclone root)
├── 2026-01-03/                      # 날짜별 수집 데이터
│   └── v1/                          # 버전별 디렉토리
│       ├── us_prices.csv
│       ├── us_metrics.csv
│       ├── kr_prices.csv
│       └── kr_metrics.csv
├── companies/                       # 기업 마스터 데이터
│   ├── us_companies.csv
│   └── kr_companies.csv
└── supabase/                        # Supabase 백업 (4주 롤링)
    └── 2026-01-03/
        ├── companies.csv
        ├── metrics.csv
        └── prices.csv
```

---

## 백업 정책

| 데이터 | 주기 | 보관 기간 | 방식 |
|--------|------|----------|------|
| 일별 가격 | 평일 매일 | 무기한 | CSV → Google Drive |
| 재무제표 | 평일 매일 | 무기한 | CSV → Google Drive |
| Supabase 전체 | 평일 매일 | 4주 롤링 | CSV → Google Drive |

---

## 구현 방식

### 필요 도구
- **rclone**: Google Drive 연동 CLI
- **GitHub Actions**: 스케줄 실행

### Google Drive 설정 가이드 (OAuth 인증)

> **참고**: 개인 Google 계정에서는 Service Account가 동작하지 않으므로 OAuth 인증을 사용합니다.

#### 1. Google Cloud 프로젝트 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **APIs & Services > Library** 이동
4. "Google Drive API" 검색 후 **Enable** 클릭

#### 2. OAuth 동의 화면 설정

1. **APIs & Services > OAuth consent screen** 이동
2. User Type: **External** 선택
3. 앱 이름, 이메일 등 필수 정보 입력
4. Scopes: 기본값 유지 (추가 불필요)
5. Test users: 본인 이메일 추가
6. **PUBLISH APP** 클릭하여 Production 모드로 전환 (토큰 만료 방지)

#### 3. OAuth 클라이언트 ID 생성

1. **APIs & Services > Credentials** 이동
2. **+ CREATE CREDENTIALS > OAuth client ID** 클릭
3. Application type: **Desktop app**
4. Name: `rclone`
5. **Authorized redirect URIs**에 추가: `http://127.0.0.1:53682/`
6. **CREATE** 클릭
7. Client ID와 Client Secret 복사

#### 4. 로컬에서 rclone 설정

```bash
# rclone 설치 (macOS)
brew install rclone

# 설정 시작
rclone config
```

대화형 설정:
```
n                           # 새 리모트 생성
gdrive                      # 이름
drive                       # Google Drive 선택
[Client ID 붙여넣기]
[Client Secret 붙여넣기]
1                           # Full access
Enter                       # service_account_file 비움
n                           # 고급 설정 스킵
y                           # 자동 설정 (브라우저 열림)
→ 브라우저에서 Google 로그인 후 허용
n                           # 팀 드라이브 아님
y                           # 설정 확인
q                           # 종료
```

#### 5. root_folder_id 추가

1. Google Drive에서 `stock-screener-backup` 폴더 생성
2. 폴더 URL에서 ID 복사: `https://drive.google.com/drive/folders/[폴더ID]`
3. rclone 설정에 추가:
```bash
rclone config
# e (edit) > gdrive 선택 > root_folder_id 항목에 폴더 ID 입력
```

#### 6. 연결 테스트

```bash
# 연결 확인
rclone lsd gdrive:

# 테스트 업로드
echo "test" > /tmp/test.txt
rclone copy /tmp/test.txt gdrive:
rclone ls gdrive:
```

#### 7. GitHub Secret 설정

1. 설정 파일 내용 확인:
```bash
cat ~/.config/rclone/rclone.conf
```

2. Repository **Settings > Secrets and variables > Actions**
3. **New repository secret** 클릭
4. Name: `RCLONE_CONFIG`
5. Value: rclone.conf 내용 전체 붙여넣기 (token 포함)

### 워크플로우

`backup.yml`에 Google Drive 백업이 자동으로 포함됨:
- `RCLONE_CONFIG` secret이 설정되면 자동 활성화
- 설정되지 않으면 GitHub Artifacts만 사용 (기존 동작)

---

## 복구 절차

### 일별 가격 복구
```bash
# gdrive: 리모트는 stock-screener-backup 폴더를 가리킴
rclone copy gdrive:prices/us_prices_20250101.csv ./data/prices/
```

### Supabase 복구
```bash
# 백업 다운로드
rclone copy gdrive:backups/supabase_20250105.sql ./

# Supabase에 복원
psql $DATABASE_URL < supabase_20250105.sql
```

---

## 데이터 정리 (Supabase 용량 관리)

### 자동화 (backup.yml)

prices 테이블은 backup.yml에서 자동으로 정리됩니다:
- 데이터 수집 완료 후 자동 실행 (workflow_run 트리거)
- 1개월 이전 데이터 삭제

### 수동 정리 (필요 시)
```sql
-- 1개월 이전 가격 데이터 삭제
DELETE FROM prices
WHERE date < NOW() - INTERVAL '1 month';
```

---

## 용량 확인 방법

### Supabase 대시보드

1. [Organization Usage](https://supabase.com/dashboard/org/_/usage) - 조직 전체 사용량
2. Project Overview 페이지 - 프로젝트별 사용량

### SQL 쿼리 (테이블별 용량)

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname || '.' || tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname || '.' || tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
```

### SQL 쿼리 (전체 데이터베이스)

```sql
SELECT pg_size_pretty(pg_database_size(current_database()));
```
