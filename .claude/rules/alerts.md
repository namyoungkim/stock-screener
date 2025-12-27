# 알림 시스템 가이드

## 개요

사용자가 특정 종목의 지표 조건을 설정하고, 조건 충족 시 알림을 받는 시스템.
GitHub OAuth 로그인 필요.

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/alerts | 알림 목록 조회 |
| POST | /api/alerts | 알림 생성 |
| GET | /api/alerts/{id} | 알림 상세 조회 |
| PATCH | /api/alerts/{id} | 알림 수정 |
| DELETE | /api/alerts/{id} | 알림 삭제 |
| POST | /api/alerts/{id}/toggle | 활성화/비활성화 토글 |
| GET | /api/alerts/company/{company_id} | 특정 종목의 알림 조회 |

---

## 지원 지표

| 지표 | 필드명 | 설명 |
|------|--------|------|
| P/E Ratio | `pe_ratio` | 주가수익비율 |
| P/B Ratio | `pb_ratio` | 주가순자산비율 |
| P/S Ratio | `ps_ratio` | 주가매출비율 |
| ROE | `roe` | 자기자본이익률 (%) |
| ROA | `roa` | 총자산이익률 (%) |
| Debt/Equity | `debt_equity` | 부채비율 |
| Dividend Yield | `dividend_yield` | 배당수익률 (%) |
| RSI | `rsi` | 상대강도지수 (0-100) |
| MFI | `mfi` | 자금흐름지수 (0-100) |
| Bollinger %B | `bb_percent` | 볼린저밴드 %B (%) |
| Graham Number | `graham_number` | 그레이엄 넘버 |
| 52W High | `fifty_two_week_high` | 52주 최고가 |
| 52W Low | `fifty_two_week_low` | 52주 최저가 |

---

## 연산자

| 연산자 | 의미 |
|--------|------|
| `<` | 미만 |
| `<=` | 이하 |
| `=` | 같음 |
| `>=` | 이상 |
| `>` | 초과 |

---

## 프론트엔드

| 경로/컴포넌트 | 용도 |
|--------------|------|
| `/alerts` | 알림 목록 관리 페이지 |
| `AlertForm` | 종목 상세 페이지에서 알림 생성 모달 |

---

## 사용 예시

### 저평가 알림
```
지표: P/E Ratio
조건: <= 15
의미: P/E가 15 이하가 되면 알림
```

### 과매도 알림
```
지표: RSI
조건: <= 30
의미: RSI가 30 이하(과매도 구간)가 되면 알림
```

### 고배당 알림
```
지표: Dividend Yield
조건: >= 4
의미: 배당수익률이 4% 이상이 되면 알림
```

---

## 관련 파일

### 백엔드
- `backend/app/api/alerts.py` - API 라우트
- `backend/app/services/alerts.py` - 비즈니스 로직
- `backend/app/models/alert.py` - Pydantic 모델

### 프론트엔드
- `frontend/src/app/alerts/page.tsx` - 알림 목록 페이지
- `frontend/src/components/AlertForm.tsx` - 알림 생성 모달
- `frontend/src/lib/api.ts` - API 클라이언트 (AlertItem, AlertResponse 타입)

### 데이터베이스
- `supabase/schema.sql` - alerts 테이블, RLS 정책

---

## 알림 데이터 모델

```typescript
interface AlertItem {
  id: string;
  user_id: string;
  company_id: string;
  metric: string;        // 지표 필드명
  operator: OperatorType; // "<" | "<=" | "=" | ">=" | ">"
  value: number;         // 임계값
  is_active: boolean;    // 활성화 상태
  triggered_at?: string; // 마지막 트리거 시점
  triggered_count: number; // 트리거 횟수
  created_at: string;
  updated_at: string;
  // 조인된 종목 정보
  ticker?: string;
  name?: string;
  market?: string;
}
```
