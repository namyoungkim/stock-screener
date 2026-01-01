# OpenSearch AI 분석 인덱스 스키마

> Phase 4: AI 분석을 위한 OpenSearch 인덱스 설계

## 인덱스: `stock_analysis`

티커별 AI 분석 결과를 저장하는 인덱스.

### 매핑

```json
{
  "mappings": {
    "properties": {
      "ticker": {
        "type": "keyword"
      },
      "name": {
        "type": "text",
        "analyzer": "nori_analyzer",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "market": {
        "type": "keyword"
      },
      "sector": {
        "type": "keyword"
      },
      "analysis_date": {
        "type": "date"
      },
      "summary": {
        "type": "text",
        "analyzer": "nori_analyzer"
      },
      "metrics_summary": {
        "type": "object",
        "properties": {
          "price": { "type": "float" },
          "market_cap": { "type": "long" },
          "pe_ratio": { "type": "float" },
          "pb_ratio": { "type": "float" },
          "roe": { "type": "float" },
          "rsi": { "type": "float" },
          "graham_number": { "type": "float" },
          "dividend_yield": { "type": "float" }
        }
      },
      "news_summary": {
        "type": "text",
        "analyzer": "nori_analyzer"
      },
      "news_items": {
        "type": "nested",
        "properties": {
          "title": { "type": "text", "analyzer": "nori_analyzer" },
          "source": { "type": "keyword" },
          "date": { "type": "date" },
          "sentiment": { "type": "keyword" }
        }
      },
      "investment_insight": {
        "type": "text",
        "analyzer": "nori_analyzer"
      },
      "signal": {
        "type": "keyword"
      },
      "score": {
        "type": "integer"
      },
      "risks": {
        "type": "nested",
        "properties": {
          "level": { "type": "keyword" },
          "message": { "type": "text", "analyzer": "nori_analyzer" }
        }
      },
      "action_guide": {
        "type": "text",
        "analyzer": "nori_analyzer"
      },
      "created_at": {
        "type": "date"
      },
      "updated_at": {
        "type": "date"
      }
    }
  },
  "settings": {
    "index": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "analysis": {
      "analyzer": {
        "nori_analyzer": {
          "type": "custom",
          "tokenizer": "nori_tokenizer",
          "filter": ["lowercase", "nori_readingform"]
        }
      }
    }
  }
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `ticker` | keyword | 종목 티커 (AAPL, 005930 등) |
| `name` | text | 종목명 (한글/영문) |
| `market` | keyword | 시장 (US, KOSPI, KOSDAQ) |
| `sector` | keyword | 섹터 |
| `analysis_date` | date | 분석 날짜 |
| `summary` | text | AI 종합 분석 요약 |
| `metrics_summary` | object | 주요 재무 지표 스냅샷 |
| `news_summary` | text | 최근 뉴스/이슈 요약 |
| `news_items` | nested | 개별 뉴스 항목 |
| `investment_insight` | text | 투자 인사이트 (매수/관망/회피 근거) |
| `signal` | keyword | 투자 신호 (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL) |
| `score` | integer | 투자 점수 (0-100) |
| `risks` | nested | 리스크 요인 목록 |
| `action_guide` | text | 구체적 행동 제안 |
| `created_at` | date | 생성 시각 |
| `updated_at` | date | 수정 시각 |

### 샘플 문서

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "market": "US",
  "sector": "Technology",
  "analysis_date": "2026-01-01",
  "summary": "AAPL은 P/E 28.5로 역사적 평균 대비 약간 고평가 상태이나, ROE 147%와 Net Margin 25%로 수익성이 매우 우수합니다. 최근 AI 투자 확대 뉴스가 긍정적입니다.",
  "metrics_summary": {
    "price": 192.53,
    "market_cap": 2980000000000,
    "pe_ratio": 28.5,
    "pb_ratio": 47.2,
    "roe": 147.0,
    "rsi": 45.0,
    "graham_number": 38.5,
    "dividend_yield": 0.5
  },
  "news_summary": "Apple, AI 기반 Siri 업그레이드 발표. iPhone 16 판매 호조세 지속.",
  "news_items": [
    {
      "title": "Apple announces AI-powered Siri upgrade",
      "source": "Reuters",
      "date": "2025-12-28",
      "sentiment": "positive"
    }
  ],
  "investment_insight": "수익성은 우수하나 밸류에이션이 높아 신규 진입보다는 조정 시 매수를 권장합니다. Graham Number 대비 약 400% 프리미엄 상태입니다.",
  "signal": "HOLD",
  "score": 52,
  "risks": [
    {
      "level": "MEDIUM",
      "message": "P/E 28.5로 섹터 평균(25) 대비 고평가"
    }
  ],
  "action_guide": "현재가 대비 10% 하락 시($173) 매수 고려. 분할 매수 전략 권장.",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

### 쿼리 예시

#### 티커로 분석 조회
```json
{
  "query": {
    "term": { "ticker": "AAPL" }
  }
}
```

#### STRONG_BUY 신호 종목
```json
{
  "query": {
    "term": { "signal": "STRONG_BUY" }
  },
  "sort": [{ "score": "desc" }]
}
```

#### 한국어 뉴스 검색
```json
{
  "query": {
    "match": {
      "news_summary": "삼성 반도체"
    }
  }
}
```

### 관련 문서

- PRD Phase 4: `docs/PRD.md` 6절
- OpenSearch 스킬: `.claude/skills/opensearch-client/SKILL.md`
