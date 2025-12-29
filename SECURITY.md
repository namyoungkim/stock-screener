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
- 입력 검증 강화 (아래 섹션 참조)
- API 키 노출 방지 (아래 섹션 참조)

#### 향후 구현 예정
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

## API 키 노출 방지

### 개념

API 키 노출 방지는 민감한 환경변수가 로그나 에러 메시지에 노출되지 않도록 보호합니다.

### 구현 상세

#### 환경변수 검증 (서버 시작 시)

`backend/app/core/config.py`:

```python
@model_validator(mode="after")
def validate_required_settings(self) -> "Settings":
    missing = []
    if not self.supabase_url:
        missing.append("SUPABASE_URL")
    if not self.supabase_key:
        missing.append("SUPABASE_KEY")

    if missing:
        # 프로덕션에서는 서버 시작 실패
        if os.getenv("RENDER") or os.getenv("VERCEL"):
            sys.exit(1)
```

#### 로그 마스킹

민감한 정보는 마스킹되어 로그에 출력됩니다:

```python
def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value for safe logging."""
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"
```

출력 예시:
```
SUPABASE_URL: https://abc123456...supabase.co
SUPABASE_KEY: eyJh...key1
```

#### DB 연결 검증 (서버 시작 시)

`backend/app/main.py`의 lifespan 이벤트:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 연결 검증
    client = get_supabase_client()
    client.table("companies").select("id").limit(1).execute()
    logger.info("Database connection verified successfully")
```

### 보호되는 환경변수

| 변수 | 용도 | 필수 |
|------|------|------|
| `SUPABASE_URL` | Supabase 프로젝트 URL | Yes |
| `SUPABASE_KEY` | Supabase Service Role Key | Yes |
| `SUPABASE_JWT_SECRET` | JWT 검증 (미사용) | No |

### 프로덕션 동작

프로덕션 환경 (`RENDER` 또는 `VERCEL` 환경변수 존재 시):
- 필수 환경변수 누락 시 **서버 시작 실패** (`sys.exit(1)`)
- 로그에 민감한 정보 마스킹

개발 환경:
- 경고 로그 출력 후 서버 시작 (DB 연결 없이 테스트 가능)

---

## 입력 검증 (Input Validation)

### 개념

입력 검증은 API 요청 데이터를 검증하여 SQL Injection, XSS, DoS 공격을 방지합니다.

### 구현 상세

`backend/app/models/common.py`에 공통 타입 정의:

#### MetricType Enum (화이트리스트)

`metric` 필드는 33개의 허용된 값만 수용합니다:

```python
class MetricType(str, Enum):
    PE_RATIO = "pe_ratio"
    PB_RATIO = "pb_ratio"
    ROE = "roe"
    RSI = "rsi"
    # ... 총 33개 지표
```

잘못된 metric 값 요청 시:
```json
{
  "detail": [
    {
      "type": "enum",
      "loc": ["body", "filters", 0, "metric"],
      "msg": "Input should be 'pe_ratio', 'pb_ratio', ..."
    }
  ]
}
```

#### 숫자 범위 제한

```python
MetricValue = Annotated[float, Field(ge=-1e12, le=1e12)]
TargetPrice = Annotated[float, Field(gt=0, le=1e9)]
```

#### UUID 형식 검증

```python
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
CompanyId = Annotated[str, Field(pattern=UUID_PATTERN)]
```

#### 문자열 길이 제한

```python
NotesField = Annotated[str, Field(max_length=1000)]
DescriptionField = Annotated[str, Field(max_length=500)]
```

### 검증 적용 엔드포인트

| 엔드포인트 | 검증 항목 |
|------------|----------|
| `POST /api/screen` | `metric` 화이트리스트, `value` 범위 |
| `POST /api/alerts` | `company_id` UUID, `metric` 화이트리스트, `value` 범위 |
| `POST /api/watchlist` | `company_id` UUID, `notes` 길이, `target_price` 범위 |
| `POST /api/user-presets` | `description` 길이, `filters` 검증 |
| `GET /api/stocks/{ticker}` | `ticker` 패턴 (`^[A-Za-z0-9.\-]+$`) |
| `GET /api/stocks?search=` | `search` 길이 (1-100자) |

### 잘못된 입력 예시

```bash
# SQL Injection 시도 - 400 에러로 차단
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{"filters": [{"metric": "pe_ratio; DROP TABLE--", "operator": "<", "value": 15}]}'

# 범위 초과 - 400 에러로 차단
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{"filters": [{"metric": "pe_ratio", "operator": "<", "value": 1e15}]}'
```

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

### 422 Validation Error

```json
{"detail": [{"type": "enum", "loc": ["body", "filters", 0, "metric"], "msg": "Input should be..."}]}
```

**원인:** 입력 값이 검증 규칙에 맞지 않음

**확인 사항:**
1. `metric` 필드가 허용된 값인지 확인 (pe_ratio, pb_ratio, roe 등)
2. `value` 필드가 범위 내인지 확인 (-1e12 ~ 1e12)
3. `company_id`가 올바른 UUID v4 형식인지 확인 (소문자)
4. 문자열 길이가 제한을 초과하지 않는지 확인
