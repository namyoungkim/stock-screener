// Financial metrics glossary (Korean explanations)
export const metricsGlossary: Record<string, string> = {
  // Valuation metrics
  pe_ratio: "주가수익비율(PER). 주가 ÷ 주당순이익. 낮을수록 저평가",
  pb_ratio: "주가순자산비율(PBR). 주가 ÷ 주당순자산. 1 미만이면 자산가치보다 저평가",
  ps_ratio: "주가매출비율(PSR). 시총 ÷ 매출. 성장주 평가에 사용",
  ev_ebitda: "기업가치 ÷ 영업이익. 기업 인수 시 회수기간 추정에 활용",
  peg_ratio: "PEG 비율. P/E ÷ 예상 성장률. 1 미만이면 성장 대비 저평가",

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

  // Price Range
  fifty_two_week_high: "52주 최고가. 최근 1년간 최고 거래가격",
  fifty_two_week_low: "52주 최저가. 최근 1년간 최저 거래가격",

  // Risk
  beta: "베타. 시장 대비 변동성. 1보다 크면 시장보다 변동성이 큼",

  // Moving Averages
  fifty_day_average: "50일 이동평균. 최근 50거래일 평균 가격",
  two_hundred_day_average: "200일 이동평균. 최근 200거래일 평균 가격. 장기 추세 판단에 사용",

  // Graham Number
  eps: "주당순이익(EPS). 순이익 ÷ 발행주식수",
  book_value_per_share: "주당순자산(BPS). 순자산 ÷ 발행주식수",
  graham_number:
    "그레이엄 넘버. √(22.5 × EPS × BPS). 현재가보다 높으면 저평가 가능성",

  // Technical Indicators
  rsi: "RSI(상대강도지수). 14일 기준. 30 이하 과매도, 70 이상 과매수 신호",
  volume_change: "거래량 변화율. 20일 평균 대비 현재 거래량 변화(%)",
  macd: "MACD(이동평균수렴확산). 12일 EMA - 26일 EMA. 추세 방향과 모멘텀 측정",
  macd_signal: "MACD 시그널선. MACD의 9일 EMA. MACD가 시그널 상향돌파 시 매수 신호",
  macd_histogram: "MACD 히스토그램. MACD - 시그널. 양수면 상승 모멘텀, 음수면 하락 모멘텀",
  bb_upper: "볼린저 상단. 20일 SMA + 2×표준편차. 저항선 역할",
  bb_middle: "볼린저 중심. 20일 단순이동평균(SMA)",
  bb_lower: "볼린저 하단. 20일 SMA - 2×표준편차. 지지선 역할",
  bb_percent: "볼린저 %B. 밴드 내 위치(%). 0% 이하 과매도, 100% 이상 과매수",
  mfi: "MFI(자금흐름지수). 거래량 가중 RSI. 20 이하 과매도, 80 이상 과매수",
};

// Table header labels to glossary key mapping
export const headerToGlossaryKey: Record<string, string> = {
  "P/E": "pe_ratio",
  "P/B": "pb_ratio",
  "P/S": "ps_ratio",
  "EV/EBITDA": "ev_ebitda",
  PEG: "peg_ratio",
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
  "52W High": "fifty_two_week_high",
  "52W Low": "fifty_two_week_low",
  Beta: "beta",
  "MA 50": "fifty_day_average",
  "MA 200": "two_hundred_day_average",
  RSI: "rsi",
  "Vol Chg": "volume_change",
  MACD: "macd",
  Signal: "macd_signal",
  Histogram: "macd_histogram",
  "BB Upper": "bb_upper",
  "BB Middle": "bb_middle",
  "BB Lower": "bb_lower",
  "BB %": "bb_percent",
  MFI: "mfi",
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
