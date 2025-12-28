# EC2 Self-hosted Runner 설정 가이드

## 개요

GitHub Actions 공유 IP에서 yfinance rate limit 문제를 해결하기 위해 EC2에 Self-hosted Runner를 설정합니다.

---

## 1. EC2 인스턴스 생성

| 설정 | 권장값 |
|------|--------|
| 인스턴스 타입 | `t3.micro` (무료 티어) 또는 `t3.small` |
| OS | Ubuntu 22.04 LTS |
| 스토리지 | 20GB |
| 보안 그룹 | SSH (22) 인바운드만 |

---

## 2. 초기 환경 설정

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
sudo apt install -y curl git

# uv 설치 (Python 관리)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Python 3.11 설치
uv python install 3.11

# rclone 설치 (Google Drive 백업용)
curl https://rclone.org/install.sh | sudo bash
```

---

## 3. rclone 설정

로컬에서 설정한 rclone.conf를 EC2에 복사:

```bash
mkdir -p ~/.config/rclone
nano ~/.config/rclone/rclone.conf
# 로컬의 ~/.config/rclone/rclone.conf 내용 붙여넣기
```

연결 테스트:
```bash
rclone lsd gdrive:
```

---

## 4. GitHub Actions Runner 설치

### 4.1 토큰 발급

1. GitHub 리포지토리 > **Settings > Actions > Runners**
2. **New self-hosted runner** 클릭
3. Linux / x64 선택
4. 표시된 토큰 복사

### 4.2 Runner 설치

```bash
mkdir actions-runner && cd actions-runner

# 최신 버전 다운로드 (GitHub에서 표시된 URL 사용)
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# 설정
./config.sh --url https://github.com/<owner>/<repo> --token <YOUR_TOKEN>

# 서비스로 설치 (재부팅 후 자동 시작)
sudo ./svc.sh install
sudo ./svc.sh start
```

### 4.3 상태 확인

```bash
sudo ./svc.sh status
```

GitHub에서 **Settings > Actions > Runners**에서 "Idle" 상태 확인

---

## 5. 환경 변수 설정

### 옵션 A: systemd 서비스에 직접 추가

```bash
# 서비스 파일 수정
sudo nano /etc/systemd/system/actions.runner.*.service

# [Service] 섹션에 추가:
Environment="SUPABASE_URL=https://xxx.supabase.co"
Environment="SUPABASE_KEY=eyJ..."

# 서비스 재시작
sudo systemctl daemon-reload
sudo ./svc.sh stop
sudo ./svc.sh start
```

### 옵션 B: .env 파일 사용

```bash
# Runner 디렉토리에 .env 파일 생성
cd ~/actions-runner
nano .env

# 내용:
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
```

> **참고**: GitHub Secrets도 여전히 사용 가능합니다. 워크플로우에서 `${{ secrets.SUPABASE_URL }}`로 접근.

---

## 6. 워크플로우 설정

Runner가 등록되면 워크플로우에서 `runs-on: self-hosted` 사용:

```yaml
jobs:
  collect-us:
    runs-on: self-hosted  # ubuntu-latest 대신
    steps:
      - uses: actions/checkout@v4
      # ...
```

---

## 7. 테스트

1. GitHub에서 워크플로우 수동 실행 (workflow_dispatch)
2. Runner 로그 확인:
   ```bash
   journalctl -u actions.runner.* -f
   ```

---

## 8. 유지보수

### Runner 업데이트

Runner는 자동 업데이트됩니다. 수동 업데이트 필요 시:

```bash
cd ~/actions-runner
sudo ./svc.sh stop
# 새 버전 다운로드 및 압축 해제
sudo ./svc.sh start
```

### 로그 확인

```bash
# 서비스 로그
journalctl -u actions.runner.* --since "1 hour ago"

# 워크플로우 실행 로그
ls ~/actions-runner/_work/<repo>/<repo>/
```

### Runner 제거

```bash
cd ~/actions-runner
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove --token <REMOVE_TOKEN>
```

---

## 비용 예상

| 항목 | 비용 |
|------|------|
| EC2 t3.micro | 무료 티어 (1년) 또는 ~$8/월 |
| EBS 20GB | ~$2/월 |
| 데이터 전송 | 무시할 수준 |
| **합계** | **~$10/월** (무료 티어 이후) |

---

## 다중 프로젝트 공유 (향후)

같은 Runner를 다른 리포지토리에서도 사용하려면:

1. Organization-level Runner로 등록
2. 또는 각 리포지토리에 동일 Runner 추가 등록

```bash
# 추가 리포지토리에 등록
./config.sh --url https://github.com/<owner>/<another-repo> --token <TOKEN>
```
