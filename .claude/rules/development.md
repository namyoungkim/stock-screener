# 개발 프로세스 가이드

## Git 워크플로우 (GitHub Flow)

### 브랜치 전략
- `main`: 항상 배포 가능 상태 (Vercel/Render 자동 배포)
- 작업 브랜치: `feature/*`, `fix/*`, `refactor/*`, `docs/*`, `chore/*`

### 워크플로우
1. `git checkout -b feature/xxx` - main에서 브랜치 생성
2. 개발 및 커밋
3. `git push -u origin feature/xxx` - PR 생성, Vercel Preview 확인
4. main에 머지 → 자동 배포
5. 로컬 브랜치 정리: `git branch -d feature/xxx`

### 브랜치 네이밍
| 접두사 | 용도 | 예시 |
|--------|------|------|
| `feature/` | 새 기능 | `feature/watchlist-export` |
| `fix/` | 버그 수정 | `fix/login-redirect` |
| `refactor/` | 리팩토링 | `refactor/api-structure` |
| `docs/` | 문서 | `docs/api-guide` |
| `chore/` | 설정/유지보수 | `chore/update-deps` |

### 예외
- 타이포, 1줄 수정 등 사소한 변경은 main 직접 커밋 허용
- dev 브랜치 불필요 (Vercel Preview가 스테이징 역할)

---

## 테스트 우선 개발

### 원칙
1. 새 기능 구현 전 테스트 작성
2. 테스트 통과 후 코드 리팩토링
3. PR 전 모든 테스트 통과 확인

### 테스트 실행

```bash
# Frontend 테스트
cd frontend && npm test          # 워치 모드
cd frontend && npm run test:run  # 단일 실행
cd frontend && npm run test:coverage  # 커버리지

# Backend 테스트
uv run --package stock-screener-backend pytest tests/backend/ -v

# 전체 테스트
npm run test:run && uv run --package stock-screener-backend pytest tests/
```

### 테스트 파일 위치

| 영역 | 위치 | 명명 규칙 |
|------|------|----------|
| Frontend | `frontend/src/__tests__/` | `*.test.tsx` |
| Backend | `tests/backend/` | `test_*.py` |

### 테스트 작성 가이드

**Frontend (Vitest + React Testing Library)**
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

describe("ComponentName", () => {
  it("should render correctly", () => {
    render(<Component />);
    expect(screen.getByText("expected text")).toBeInTheDocument();
  });
});
```

**Backend (pytest)**
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_endpoint(client):
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

---

## UX 설계 프로세스

### 기능 구현 전 체크리스트

#### 상태 처리
- [ ] **로딩 상태**: 스켈레톤 또는 스피너 표시
- [ ] **에러 상태**: 구체적 메시지 + 재시도 버튼
- [ ] **빈 상태**: 안내 메시지 + 다음 액션 유도
- [ ] **성공 상태**: 토스트 알림으로 피드백

#### 접근성
- [ ] **키보드 네비게이션**: Tab으로 모든 인터랙티브 요소 접근 가능
- [ ] **aria-label**: 아이콘 버튼에 라벨 추가
- [ ] **포커스 인디케이터**: 포커스 상태 시각적으로 표시

#### 반응형
- [ ] **모바일 레이아웃**: 768px 이하에서 정상 표시
- [ ] **터치 타겟**: 최소 44x44px

### 공통 UX 컴포넌트

| 컴포넌트 | 위치 | 용도 |
|---------|------|------|
| `Tooltip` | `components/ui/Tooltip.tsx` | 툴팁 표시 |
| `Pagination` | `components/ui/Pagination.tsx` | 페이지네이션 |
| `Toast` | (예정) | 알림 메시지 |
| `Skeleton` | (예정) | 로딩 플레이스홀더 |

### 다크모드 스타일링

`.claude/rules/frontend.md` 참조. 주요 패턴:

```tsx
// 배경
"bg-white dark:bg-slate-800"

// 텍스트
"text-gray-900 dark:text-white"

// 테두리
"border-gray-200 dark:border-slate-700"
```

---

## 코드 리뷰 체크리스트

### 기능
- [ ] 요구사항 충족
- [ ] 엣지 케이스 처리
- [ ] 에러 핸들링

### 테스트
- [ ] 단위 테스트 작성
- [ ] 테스트 통과

### UX
- [ ] 로딩/에러/빈 상태 처리
- [ ] 접근성 고려
- [ ] 다크모드 지원

### 코드 품질
- [ ] 린트 통과 (`uv run ruff check .`)
- [ ] 타입 체크 통과 (`uv run ty check`)
- [ ] 불필요한 console.log 제거
