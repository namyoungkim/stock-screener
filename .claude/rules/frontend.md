# 프론트엔드 스타일 가이드

## 다크모드

### 전략
Tailwind CSS `dark:` 클래스 전략 사용. `<html class="dark">`로 토글.

### 색상 매핑

#### 배경색
| 라이트 | 다크 | 용도 |
|--------|------|------|
| `bg-white` | `dark:bg-slate-800` | 카드, 테이블 바디 |
| `bg-gray-50` | `dark:bg-slate-700` | 호버, 서브 영역 |
| `bg-slate-800` | `dark:bg-slate-900` | 테이블 헤더 |

#### 테두리
| 라이트 | 다크 | 용도 |
|--------|------|------|
| `border-gray-200` | `dark:border-slate-700` | 카드, 테이블 외곽 |
| `border-gray-100` | `dark:border-slate-600` | 섹션 구분선 |
| `divide-gray-200` | `dark:divide-slate-700` | 테이블 행 구분 |

#### 텍스트
| 라이트 | 다크 | 용도 |
|--------|------|------|
| `text-slate-900` | `dark:text-white` | 제목, 강조 값 |
| `text-gray-900` | `dark:text-white` | 주요 텍스트 |
| `text-slate-700` | `dark:text-slate-200` | 부제목 |
| `text-slate-600` | `dark:text-slate-300` | 본문 |
| `text-gray-600` | `dark:text-gray-400` | 설명 텍스트 |
| `text-gray-500` | `dark:text-gray-400` | 보조 텍스트 |
| `text-gray-400` | `dark:text-gray-500` | placeholder, 빈 값 |
| `text-gray-300` | `dark:text-gray-600` | 비활성 아이콘 |

#### 링크
| 라이트 | 다크 |
|--------|------|
| `text-blue-600 hover:text-blue-800` | `dark:text-blue-400 dark:hover:text-blue-300` |

#### 컬러 지표 (밝기 조정)
다크모드에서는 600 → 400으로 밝기 증가:
| 라이트 | 다크 | 용도 |
|--------|------|------|
| `text-emerald-600` | `dark:text-emerald-400` | 긍정 지표 (ROE, 상승) |
| `text-green-600` | `dark:text-green-400` | 저평가, 과매도 |
| `text-red-600` | `dark:text-red-400` | 부정 지표, 과매수 |
| `text-orange-600` | `dark:text-orange-400` | 경고, 배당 |
| `text-blue-600` | `dark:text-blue-400` | 정보 |
| `text-violet-600` | `dark:text-violet-400` | 특수 지표 |

### 마켓 배지
```tsx
// US
"bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300"

// KOSPI
"bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-300"

// KOSDAQ
"bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300"
```

### 컴포넌트 패턴

#### 카드
```tsx
<div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm">
```

#### 테이블
```tsx
<table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
  <thead className="bg-slate-800 dark:bg-slate-900">
    <tr>
      <th className="text-white">...</th>
    </tr>
  </thead>
  <tbody className="divide-y divide-gray-200 dark:divide-slate-700 bg-white dark:bg-slate-800">
    <tr className="hover:bg-gray-50 dark:hover:bg-slate-700">
      <td className="text-gray-900 dark:text-white">...</td>
    </tr>
  </tbody>
</table>
```

#### 버튼 (비활성)
```tsx
<button className="bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600">
```

#### 입력 필드
```tsx
<input className="border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500" />
```

### 체크리스트

새 페이지/컴포넌트 작성 시 확인:

- [ ] `bg-white` → `bg-white dark:bg-slate-800`
- [ ] `border-gray-*` → `border-gray-* dark:border-slate-*`
- [ ] `text-gray-900` / `text-slate-900` → `dark:text-white`
- [ ] `text-gray-600` / `text-slate-600` → `dark:text-slate-300` 또는 `dark:text-gray-400`
- [ ] 링크에 `dark:text-blue-400 dark:hover:text-blue-300` 추가
- [ ] 컬러 지표에 `dark:*-400` 추가
- [ ] 마켓 배지에 다크모드 변형 추가
- [ ] 호버 상태에 `dark:hover:bg-slate-700` 추가
