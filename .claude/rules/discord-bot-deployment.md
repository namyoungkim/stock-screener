# 디스코드 봇 배포 가이드

## 현재 상태

| 항목 | 상태 |
|------|------|
| 디스코드 봇 | 로컬 Mac 수동 실행 |
| 백엔드 API | Render 배포 완료 |
| 데이터 수집 | 로컬 Mac 수동 실행 |

---

## 배포 옵션 비교

| 옵션 | 비용 | 안정성 | 설정 난이도 | 24/7 |
|------|------|--------|------------|------|
| Mac 자체 호스팅 | 무료 | ⭐⭐⭐ | 쉬움 | Mac 켜야 함 |
| AWS EC2 t3.micro | 무료(1년)→$8/월 | ⭐⭐⭐⭐⭐ | 중간 | ✅ |
| Fly.io | 무료 | ⭐⭐⭐⭐ | 쉬움 | ✅ |
| Railway | 무료($5)→과금 | ⭐⭐⭐⭐ | 쉬움 | ✅ |
| Oracle Cloud | 무료 | ⭐⭐⭐⭐ | 중간 | ✅ |

---

## 옵션 1: Mac 자체 호스팅 (LaunchAgent)

### 장점
- 완전 무료
- 설정 간단
- 로컬 백엔드 연동 가능

### 단점
- Mac 항상 켜야 함
- 정전/재부팅 시 수동 확인 필요

### 설정 방법

```bash
# LaunchAgent plist 생성
nano ~/Library/LaunchAgents/com.stock-screener.discord-bot.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock-screener.discord-bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/leo/.local/bin/uv</string>
        <string>run</string>
        <string>--package</string>
        <string>stock-screener-discord-bot</string>
        <string>python</string>
        <string>-m</string>
        <string>bot.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/leo/project/stock-screener</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DISCORD_BOT_TOKEN</key>
        <string>YOUR_TOKEN_HERE</string>
        <key>API_BASE_URL</key>
        <string>https://stock-screener-api-c0kc.onrender.com</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/discord-bot.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/discord-bot.error.log</string>
</dict>
</plist>
```

```bash
# 등록 및 시작
launchctl load ~/Library/LaunchAgents/com.stock-screener.discord-bot.plist

# 상태 확인
launchctl list | grep discord

# 중지
launchctl unload ~/Library/LaunchAgents/com.stock-screener.discord-bot.plist

# 로그 확인
tail -f /tmp/discord-bot.log
```

---

## 옵션 2: AWS EC2

### 장점
- 안정적인 24/7 운영
- 고정 IP (Elastic IP)
- Self-hosted Runner 겸용 가능
- 무료 티어 1년

### 단점
- 무료 티어 종료 후 월 $8-10
- t3.micro 메모리 1GB 제한

### 비용

| 인스턴스 | 사양 | 비용 |
|----------|------|------|
| t3.micro | 2 vCPU, 1GB RAM | 무료(1년) → ~$8/월 |
| t3.nano | 2 vCPU, 0.5GB RAM | ~$4/월 |
| t3.small | 2 vCPU, 2GB RAM | ~$15/월 |

### 설정 방법

```bash
# 1. EC2 접속 후 환경 설정
sudo apt update && sudo apt upgrade -y
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 2. 프로젝트 클론
git clone https://github.com/<your-repo>/stock-screener.git
cd stock-screener
uv sync

# 3. 환경 변수 설정
echo 'export DISCORD_BOT_TOKEN="your_token"' >> ~/.bashrc
echo 'export API_BASE_URL="https://stock-screener-api-c0kc.onrender.com"' >> ~/.bashrc
source ~/.bashrc

# 4. systemd 서비스 생성
sudo nano /etc/systemd/system/discord-bot.service
```

**systemd 서비스 파일:**

```ini
[Unit]
Description=Stock Screener Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/stock-screener
Environment="DISCORD_BOT_TOKEN=your_token_here"
Environment="API_BASE_URL=https://stock-screener-api-c0kc.onrender.com"
ExecStart=/home/ubuntu/.local/bin/uv run --package stock-screener-discord-bot python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

# 상태 확인
sudo systemctl status discord-bot

# 로그 확인
journalctl -u discord-bot -f
```

### EC2 + Self-hosted Runner 통합

EC2를 사용한다면 봇과 데이터 수집 Runner를 같이 운영 가능:

```
EC2 t3.micro (또는 t3.small)
├── Discord Bot (systemd 서비스)
├── GitHub Actions Runner (데이터 수집용)
└── 비용: 무료(1년) 또는 ~$8-10/월
```

---

## 옵션 3: Fly.io (무료)

### 장점
- 무료 티어 (3개 VM)
- 설정 간단
- 자동 배포 (GitHub 연동)

### 단점
- 무료 VM 256MB RAM 제한
- 리소스 제한으로 가끔 재시작

### 설정 방법

```bash
# 1. Fly CLI 설치
brew install flyctl

# 2. 로그인
fly auth login

# 3. fly.toml 생성
cd discord-bot
fly launch --no-deploy
```

**fly.toml:**

```toml
app = "stock-screener-discord-bot"
primary_region = "nrt"  # Tokyo

[build]
  dockerfile = "Dockerfile"

[env]
  API_BASE_URL = "https://stock-screener-api-c0kc.onrender.com"

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# uv 설치
RUN pip install uv

# 의존성 복사 및 설치
COPY pyproject.toml .
COPY bot/ bot/
RUN uv sync --package stock-screener-discord-bot

# 환경 변수는 fly secrets로 설정
CMD ["uv", "run", "--package", "stock-screener-discord-bot", "python", "-m", "bot.main"]
```

```bash
# 시크릿 설정
fly secrets set DISCORD_BOT_TOKEN=your_token_here

# 배포
fly deploy
```

---

## 옵션 4: Railway

### 장점
- GitHub 연동 자동 배포
- 설정 매우 간단
- 로그/모니터링 UI

### 단점
- 무료 $5 크레딧 (1-2주)
- 이후 사용량 기반 과금

### 설정 방법

1. [Railway](https://railway.app) 가입
2. **New Project** → **Deploy from GitHub repo**
3. `stock-screener` 리포지토리 선택
4. **Settings** → **Root Directory**: `discord-bot`
5. **Variables** 추가:
   - `DISCORD_BOT_TOKEN`
   - `API_BASE_URL`
6. **Deploy**

---

## 옵션 5: Oracle Cloud (무료)

### 장점
- 완전 무료 (Always Free Tier)
- 넉넉한 스펙 (1 OCPU, 1GB RAM)
- ARM 인스턴스: 최대 4 OCPU, 24GB RAM 무료

### 단점
- 계정 생성 어려움 (카드 검증 실패 빈번)
- 리전별 가용성 제한
- UI 복잡

### 설정 방법

EC2와 동일한 systemd 방식 사용.

---

## 권장 구성

### 무료 우선

```
1순위: Mac 자체 호스팅 (Mac 항상 켜 둘 수 있다면)
2순위: Fly.io (간단하고 무료)
3순위: Oracle Cloud (계정 생성 성공 시)
```

### 안정성 우선

```
1순위: AWS EC2 (무료 1년 + 이후 $8/월)
2순위: Mac 자체 호스팅 + UPS
```

### 통합 운영 (봇 + 데이터 수집)

```
AWS EC2 t3.small (~$15/월)
├── Discord Bot
├── Self-hosted Runner
└── 장점: 단일 서버에서 모든 작업 관리
```

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| `.claude/rules/discord-bot.md` | 디스코드 봇 개발 가이드 |
| `.claude/rules/self-hosted-runner.md` | EC2 Runner 설정 가이드 |
| `discord-bot/USAGE.md` | 사용자용 명령어 가이드 |
