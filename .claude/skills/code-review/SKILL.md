---
name: code-review
description: 코드 리뷰. "코드 리뷰", "리뷰해줘", "검토해줘" 등에 반응
allowed-tools: Read, Grep, Glob
---

# 코드 리뷰

$ARGUMENTS에 지정된 파일 또는 변경사항을 리뷰합니다.

## 사용법
- `/code-review backend/app/main.py` - 특정 파일 리뷰
- `/code-review backend/` - 디렉토리 리뷰
- `/code-review` - 최근 변경사항 리뷰 (git diff)

## 체크리스트

### 보안
- [ ] API 키/시크릿 노출 확인
- [ ] SQL Injection 가능성
- [ ] XSS 취약점
- [ ] 입력값 검증 (화이트리스트)

### 성능
- [ ] N+1 쿼리
- [ ] 불필요한 렌더링
- [ ] 대용량 데이터 처리
- [ ] 메모리 누수 가능성

### 코드 품질
- [ ] 타입 안전성 (TypeScript/Python)
- [ ] 에러 핸들링
- [ ] 테스트 커버리지
- [ ] 불필요한 의존성

### 프로젝트 규칙
- [ ] CLAUDE.md 규칙 준수
- [ ] 다크모드 스타일 적용 (프론트엔드)
- [ ] Conventional Commits 형식
- [ ] 문서화 (필요시)

## 리뷰 출력 형식

```markdown
## 리뷰 결과: [파일명]

### 심각도: Critical / Warning / Info

#### [항목]
- **위치**: `파일:라인`
- **문제**: 설명
- **제안**: 개선 방안
```
