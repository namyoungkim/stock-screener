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

### 현재: Python CLI 파이프라인 (자동화)

```bash
cd data-pipeline
uv run python -m cli.main collect all       # 전체 (KR → US → 백업 → DB)
uv run python -m cli.main collect all --no-db  # DB 적재 제외
```

**파이프라인 단계:**
1. KR 수집 (FDR + Naver)
2. US 수집 (yfinance)
3. Google Drive 백업 (rclone)
4. Supabase 적재

| 항목 | 설명 |
|------|------|
| 수집 | 로컬 Mac에서 자동 실행 (LaunchAgent) |
| 스케줄 | 화~토 오전 8시 (미국장 마감 후) |
| 백업 | rclone → Google Drive |
| DB 적재 | CSV → Supabase (companies, metrics, prices) |
| 장점 | 빠른 속도, 무료, Rate Limit 회피 용이, 자동화 |

### LaunchAgent 설정

**파일 위치:**
- plist: `~/Library/LaunchAgents/com.stock-screener.data-pipeline.plist`
- wrapper script: `scripts/run-pipeline.sh`

**Wrapper Script** (`scripts/run-pipeline.sh`):
```bash
#!/bin/bash
set -e
cd /Users/leo/project/stock-screener

# Load environment variables from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

echo "Pipeline started at $(date '+%Y-%m-%d %H:%M:%S')"
cd data-pipeline
uv run python -m cli.main collect all
echo "Pipeline completed at $(date '+%Y-%m-%d %H:%M:%S')"
```

**LaunchAgent plist:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock-screener.data-pipeline</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-i</string>
        <string>/Users/leo/project/stock-screener/scripts/run-pipeline.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/leo/project/stock-screener</string>

    <!-- 화~토 오전 8시 (미국장 마감 후) -->
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>6</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
    </array>

    <key>StandardOutPath</key>
    <string>/tmp/stock-screener-pipeline.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/stock-screener-pipeline.error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/Users/leo/.local/bin</string>
    </dict>
</dict>
</plist>
```

**관리 명령어:**

```bash
# 등록
launchctl load ~/Library/LaunchAgents/com.stock-screener.data-pipeline.plist

# 상태 확인
launchctl list | grep stock-screener

# 즉시 테스트 실행
launchctl start com.stock-screener.data-pipeline

# 로그 확인
tail -f /tmp/stock-screener-pipeline.log

# 해제
launchctl unload ~/Library/LaunchAgents/com.stock-screener.data-pipeline.plist
```

### Mac 자동 시작 (pmset)

Mac이 꺼져있거나 잠자기 상태여도 자동으로 깨어나도록 설정:

```bash
# 화~토 오전 7:55에 자동 시작 (파이프라인 5분 전)
sudo pmset repeat wakeorpoweron TWRFS 07:55:00

# 설정 확인
pmset -g sched

# 취소
sudo pmset repeat cancel
```

**요일 코드:** T(화), W(수), R(목), F(금), S(토)

**동작 흐름:**
1. 7:55 - Mac 자동 시작 (잠자기/꺼짐 상태에서 깨어남)
2. 8:00 - 데이터 수집 시작 (caffeinate로 잠자기 방지)
3. 완료 후 - 자동 잠자기 (시스템 sleep 설정에 따름)

> **참고:** 전원 어댑터 연결 권장. 배터리 모드에서는 자동 깨우기가 제한될 수 있음.

### 참고: Self-hosted Runner (미사용)

EC2 t3.micro의 리소스 제한(1GB RAM, 스레드 한계)으로 현재 미사용.
향후 Oracle Cloud (24GB RAM 무료) 또는 스펙 업그레이드 시 재검토.

설정 가이드: @.claude/rules/self-hosted-runner.md
