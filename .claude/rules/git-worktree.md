# Git Worktree 가이드

## 개요

Git worktree는 하나의 Git 저장소에서 여러 작업 디렉토리를 동시에 사용할 수 있게 해주는 기능입니다.

**주요 목적**: 여러 Claude 인스턴스가 병렬로 작업할 수 있게 함

---

## 기본 명령어

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `git worktree add` | 워크트리 생성 | `git worktree add ../feature-1 -b feature/auth` |
| `git worktree list` | 워크트리 목록 | `git worktree list` |
| `git worktree remove` | 워크트리 삭제 | `git worktree remove ../feature-1` |
| `git worktree prune` | 정리 (삭제된 디렉토리 정리) | `git worktree prune` |

---

## Claude 병렬 작업 (핵심 시나리오)

### 여러 기능 동시 개발

여러 Claude 인스턴스가 각각 다른 기능을 개발할 때:

```
Claude A: stock-screener-1/에서 feature/auth 작업
Claude B: stock-screener-2/에서 feature/dashboard 작업
→ 충돌 없이 병렬 진행
```

### 워크플로우

```bash
# 1. 워크트리 생성 (각 Claude 인스턴스용)
git worktree add ../stock-screener-1 -b feature/auth
git worktree add ../stock-screener-2 -b feature/dashboard

# 2. 각 워크트리에서 의존성 설치
cd ../stock-screener-1 && uv sync && cd frontend && npm install
cd ../stock-screener-2 && uv sync && cd frontend && npm install

# 3. 각 터미널에서 Claude 실행
# 터미널 1
cd ../stock-screener-1 && claude

# 터미널 2
cd ../stock-screener-2 && claude

# 4. 작업 완료 후 PR 생성
# (각 Claude가 작업 완료 후 커밋 & 푸시)

# 5. 워크트리 정리
git worktree remove ../stock-screener-1
git worktree remove ../stock-screener-2
```

### 장점

- 브랜치 전환 없이 여러 작업 병렬 진행
- 각 Claude가 독립된 작업 디렉토리 사용
- 파일 충돌/덮어쓰기 방지
- stash 없이 컨텍스트 스위칭 가능

---

## 기타 활용 시나리오

### 긴급 버그 수정

feature 작업 중 main에서 hotfix가 필요할 때:

```bash
# 현재 작업 유지한 채 hotfix 워크트리 생성
git worktree add ../stock-screener-hotfix main

# hotfix 작업
cd ../stock-screener-hotfix
git checkout -b fix/critical-bug
# ... 수정 ...
git commit -m "fix: critical bug"
git push

# 정리
git worktree remove ../stock-screener-hotfix
```

### PR 리뷰

다른 브랜치 코드를 stash 없이 확인:

```bash
git worktree add ../review-pr-123 origin/feature/new-feature
cd ../review-pr-123
# 코드 확인, 테스트 실행
git worktree remove ../review-pr-123
```

### 빌드 테스트

현재 작업 유지하면서 다른 브랜치 빌드 확인:

```bash
git worktree add ../build-test main
cd ../build-test && npm run build
git worktree remove ../build-test
```

---

## 권장 디렉토리 구조

```
~/project/
├── stock-screener/           # main (기본 워크트리)
├── stock-screener-1/         # Claude A 작업용
├── stock-screener-2/         # Claude B 작업용
└── stock-screener-hotfix/    # 긴급 수정용
```

---

## 주의사항

| 주의 | 설명 |
|------|------|
| 브랜치 중복 불가 | 같은 브랜치를 두 워크트리에서 체크아웃할 수 없음 |
| 삭제 전 정리 | 워크트리 삭제 전 변경사항 커밋 또는 스태시 필요 |
| `.git` 파일 | 추가 워크트리는 `.git` 폴더가 아닌 `.git` 파일을 가짐 |
| 의존성 별도 설치 | 각 워크트리에서 `uv sync`, `npm install` 별도 실행 필요 |
| node_modules | 각 워크트리마다 별도의 node_modules 필요 (디스크 공간 고려) |

---

## 빠른 참조

```bash
# 새 기능 브랜치로 워크트리 생성
git worktree add ../새폴더 -b feature/새기능

# 기존 브랜치로 워크트리 생성
git worktree add ../새폴더 기존브랜치명

# 원격 브랜치로 워크트리 생성
git worktree add ../새폴더 origin/브랜치명

# 모든 워크트리 확인
git worktree list

# 워크트리 삭제
git worktree remove ../폴더명

# 강제 삭제 (변경사항 있어도)
git worktree remove --force ../폴더명

# 삭제된 워크트리 정리
git worktree prune
```
