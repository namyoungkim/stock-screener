# Security

이 문서는 Stock Screener의 보안 관련 설정과 개념을 설명합니다.

## CORS (Cross-Origin Resource Sharing)

### 개념

CORS는 웹 브라우저의 보안 메커니즘으로, 다른 도메인에서 API 요청을 허용할지 결정합니다.

**동작 원리:**
1. 브라우저가 다른 도메인으로 API 요청 시도
2. 브라우저가 `OPTIONS` 요청(preflight)을 먼저 전송
3. 서버가 `Access-Control-Allow-Origin` 헤더로 허용 여부 응답
4. 허용된 경우에만 실제 요청 진행

### 현재 설정

허용된 도메인 목록 (`backend/app/core/config.py`):

```python
DEFAULT_CORS_ORIGINS = [
    "https://stock-screener-inky.vercel.app",  # 프로덕션 프론트엔드
    "http://localhost:3000",                    # 로컬 개발
    "http://localhost:3001",                    # 대체 포트
]
```

### 커스터마이징

새 도메인을 추가하려면 `config.py`의 `DEFAULT_CORS_ORIGINS` 리스트에 추가:

```python
DEFAULT_CORS_ORIGINS = [
    "https://stock-screener-inky.vercel.app",
    "https://your-custom-domain.com",  # 추가
    "http://localhost:3000",
]
```

---

## 인증 (Authentication)

### OAuth 흐름

GitHub/Google OAuth를 통한 인증 흐름:

```
1. 사용자가 "Continue with GitHub" 또는 "Continue with Google" 클릭
   └─> Supabase Auth가 해당 OAuth 제공자로 리다이렉트

2. OAuth 제공자에서 인증 후 코드 발급
   └─> /auth/callback으로 리다이렉트

3. 프론트엔드가 코드를 세션으로 교환
   └─> Supabase가 JWT 토큰 발급

4. JWT가 localStorage에 저장
   └─> 이후 API 요청에 Authorization 헤더로 포함
```

### 지원 OAuth 제공자

| 제공자 | 설정 위치 |
|--------|----------|
| GitHub | Supabase Dashboard > Authentication > Providers |
| Google | Supabase Dashboard + Google Cloud Console |

### JWT 토큰 검증

Supabase Auth는 **ES256 알고리즘**으로 JWT를 서명합니다.

백엔드 검증 방식 (`backend/app/core/auth.py`):

```python
# JWKS (JSON Web Key Set) 엔드포인트에서 공개키 조회
jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"

# ES256 알고리즘으로 토큰 검증
decoded = jwt.decode(
    token,
    key=public_key,
    algorithms=["ES256"],
    audience="authenticated"
)
```

**주의:** HS256이 아닌 ES256을 사용합니다. Supabase의 JWT Secret은 JWKS 기반 검증에서는 사용되지 않습니다.

### 환경 변수

| 변수 | 용도 | 필요 위치 |
|------|------|----------|
| `SUPABASE_URL` | Supabase 프로젝트 URL | Backend, Frontend |
| `SUPABASE_KEY` | Service Role Key (비공개) | Backend only |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon Key (공개 가능) | Frontend |

---

## API 보안

### 인증 필요 엔드포인트

| 엔드포인트 | 메서드 | 인증 필요 | 설명 |
|------------|--------|-----------|------|
| `/api/stocks` | GET | No | 종목 목록 조회 |
| `/api/stocks/{ticker}` | GET | No | 종목 상세 조회 |
| `/api/screen` | POST | No | 스크리닝 |
| `/api/watchlist` | GET | **Yes** | 워치리스트 조회 |
| `/api/watchlist` | POST | **Yes** | 워치리스트 추가 |
| `/api/watchlist/{ticker}` | DELETE | **Yes** | 워치리스트 삭제 |

### 인증 헤더 형식

```
Authorization: Bearer <jwt_token>
```

### 보안 고려사항

#### 현재 구현됨
- CORS 도메인 제한
- JWT 토큰 검증 (ES256/JWKS)
- 인증 필요 엔드포인트 보호
- Rate Limiting (slowapi)

#### 향후 구현 예정
- [ ] API 키 노출 방지 (환경변수 검증)
- [ ] 입력 검증 강화
- [ ] 로깅 및 모니터링

---

## Rate Limiting

### 개념

Rate Limiting은 API 남용을 방지하기 위해 일정 시간 내 요청 횟수를 제한합니다.

### 현재 설정

`slowapi` 라이브러리 사용 (`backend/app/core/rate_limit.py`):

| 엔드포인트 | 제한 | 설명 |
|------------|------|------|
| `/api/screen` | 30/minute | 스크리닝 (무거운 연산) |
| `/api/stocks` | 100/minute | 종목 목록/상세 |
| `/api/screen/presets` | 100/minute | 프리셋 조회 |

### Rate Limit 초과 시

```json
{
  "error": "Rate limit exceeded: 30 per 1 minute"
}
```

HTTP 상태 코드: `429 Too Many Requests`

---

## 문제 해결

### CORS 에러

```
Access to fetch at 'https://api.example.com' from origin 'https://frontend.com'
has been blocked by CORS policy
```

**해결:** `DEFAULT_CORS_ORIGINS`에 프론트엔드 도메인 추가

### 401 Unauthorized

```
{"detail": "Invalid token"}
```

**확인 사항:**
1. JWT 토큰이 만료되지 않았는지 확인
2. Authorization 헤더 형식이 `Bearer <token>`인지 확인
3. 토큰이 올바른 Supabase 프로젝트에서 발급되었는지 확인

### 로그인 후 리다이렉트 안됨

**확인 사항:**
1. Supabase Dashboard > Authentication > URL Configuration 확인
2. Redirect URL에 `/auth/callback` 경로 포함 여부
3. Vercel 환경변수 설정 후 재배포 여부
