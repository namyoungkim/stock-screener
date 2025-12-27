// Financial metrics glossary (Korean explanations)
export const metricsGlossary: Record<string, string> = {
  // Valuation metrics
  pe_ratio: "주가수익비율(PER). 주가 ÷ 주당순이익. 낮을수록 저평가",
  pb_ratio: "주가순자산비율(PBR). 주가 ÷ 주당순자산. 1 미만이면 자산가치보다 저평가",
  ps_ratio: "주가매출비율(PSR). 시총 ÷ 매출. 성장주 평가에 사용",
  ev_ebitda: "기업가치 ÷ 영업이익. 기업 인수 시 회수기간 추정에 활용",

  // Profitability metrics
  roe: "자기자본이익률. 순이익 ÷ 자본. 높을수록 자본 효율이 좋음",
  roa: "총자산이익률. 순이익 ÷ 총자산. 자산 활용 효율성 측정",
  gross_margin: "매출총이익률. (매출-원가) ÷ 매출",
  net_margin: "순이익률. 순이익 ÷ 매출. 최종 수익성 지표",

  // Financial health metrics
  debt_equity: "부채비율. 부채 ÷ 자본. 낮을수록 재무 안정",
  current_ratio: "유동비율. 유동자산 ÷ 유동부채. 1 이상이 안전",

  // Dividend
  dividend_yield: "배당수익률. 주당배당금 ÷ 주가",

  // Market data
  market_cap: "시가총액. 주가 × 발행주식수",

  // Graham Number
  eps: "주당순이익(EPS). 순이익 ÷ 발행주식수",
  book_value_per_share: "주당순자산(BPS). 순자산 ÷ 발행주식수",
  graham_number:
    "그레이엄 넘버. √(22.5 × EPS × BPS). 현재가보다 높으면 저평가 가능성",
};

// Table header labels to glossary key mapping
export const headerToGlossaryKey: Record<string, string> = {
  "P/E": "pe_ratio",
  "P/B": "pb_ratio",
  "P/S": "ps_ratio",
  "EV/EBITDA": "ev_ebitda",
  ROE: "roe",
  ROA: "roa",
  "Gross Margin": "gross_margin",
  "Net Margin": "net_margin",
  "Debt/Equity": "debt_equity",
  "Current Ratio": "current_ratio",
  "Div Yield": "dividend_yield",
  "Dividend Yield": "dividend_yield",
  "Market Cap": "market_cap",
  EPS: "eps",
  BPS: "book_value_per_share",
  "Graham Number": "graham_number",
};

// Preset strategies glossary (Korean explanations)
export const presetGlossary: Record<string, string> = {
  graham_classic:
    "벤저민 그레이엄의 가치투자 전략. 낮은 P/E(<15), 낮은 P/B(<1.5), 안정적 재무구조를 가진 저평가 종목 발굴",
  buffett_quality:
    "워렌 버핏 스타일 투자. 높은 ROE(>15%), 안정적 수익, 지속적 경쟁우위를 가진 우량 기업 선별",
  dividend_value:
    "배당 가치투자 전략. 높은 배당수익률과 안정적인 배당 지속성을 가진 종목 선별",
  deep_value:
    "심층 가치투자 전략. 극도로 저평가된 주식 발굴. 낮은 P/B(<1), 낮은 EV/EBITDA 기준",
};

// Preset ID to glossary key mapping
export const presetIdToGlossaryKey: Record<string, string> = {
  graham_classic: "graham_classic",
  buffett_quality: "buffett_quality",
  dividend_value: "dividend_value",
  deep_value: "deep_value",
  // Alternative naming conventions
  "Graham Classic": "graham_classic",
  "Buffett Quality": "buffett_quality",
  "Dividend Value": "dividend_value",
  "Deep Value": "deep_value",
};

// Helper function to get metric tooltip
export function getMetricTooltip(label: string): string | undefined {
  const key = headerToGlossaryKey[label];
  return key ? metricsGlossary[key] : undefined;
}

// Helper function to get preset tooltip
export function getPresetTooltip(presetId: string): string | undefined {
  const key = presetIdToGlossaryKey[presetId];
  return key ? presetGlossary[key] : undefined;
}
