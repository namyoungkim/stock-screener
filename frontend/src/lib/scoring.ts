import type { Metrics, Price } from "./api";

// Investment signal types
export type SignalType =
  | "STRONG_BUY"
  | "BUY"
  | "HOLD"
  | "SELL"
  | "STRONG_SELL";

export interface ScoreBreakdown {
  metric: string;
  value: number | null;
  score: number;
  reason: string;
}

export interface InvestmentScore {
  totalScore: number;
  signal: SignalType;
  signalLabel: string;
  breakdown: ScoreBreakdown[];
  positiveFactors: string[];
  negativeFactors: string[];
}

// Signal configuration
const SIGNAL_CONFIG: Record<
  SignalType,
  { label: string; minScore: number; color: string }
> = {
  STRONG_BUY: { label: "강력 매수", minScore: 70, color: "emerald" },
  BUY: { label: "매수 고려", minScore: 55, color: "green" },
  HOLD: { label: "관망", minScore: 40, color: "yellow" },
  SELL: { label: "매도 고려", minScore: 25, color: "orange" },
  STRONG_SELL: { label: "회피", minScore: 0, color: "red" },
};

// Get signal from score
function getSignalFromScore(score: number): SignalType {
  if (score >= 70) return "STRONG_BUY";
  if (score >= 55) return "BUY";
  if (score >= 40) return "HOLD";
  if (score >= 25) return "SELL";
  return "STRONG_SELL";
}

// Calculate investment score
export function calculateInvestmentScore(
  metrics: Metrics | undefined,
  price: Price | undefined
): InvestmentScore {
  const breakdown: ScoreBreakdown[] = [];
  const positiveFactors: string[] = [];
  const negativeFactors: string[] = [];

  let totalScore = 50; // Base score

  if (!metrics) {
    return {
      totalScore: 50,
      signal: "HOLD",
      signalLabel: SIGNAL_CONFIG.HOLD.label,
      breakdown: [],
      positiveFactors: [],
      negativeFactors: ["지표 데이터 없음"],
    };
  }

  const currentPrice = price?.close ?? metrics.graham_number;

  // P/E Ratio
  if (metrics.pe_ratio != null) {
    let score = 0;
    let reason = "";
    if (metrics.pe_ratio < 15) {
      score = 15;
      reason = "저평가 구간 (< 15)";
      positiveFactors.push(`P/E ${metrics.pe_ratio.toFixed(1)} - 저평가`);
    } else if (metrics.pe_ratio <= 25) {
      score = 5;
      reason = "적정 범위 (15-25)";
    } else {
      score = -10;
      reason = "고평가 구간 (> 25)";
      negativeFactors.push(`P/E ${metrics.pe_ratio.toFixed(1)} - 고평가`);
    }
    breakdown.push({ metric: "P/E", value: metrics.pe_ratio, score, reason });
    totalScore += score;
  }

  // P/B Ratio
  if (metrics.pb_ratio != null) {
    let score = 0;
    let reason = "";
    if (metrics.pb_ratio < 1) {
      score = 15;
      reason = "저평가 구간 (< 1)";
      positiveFactors.push(`P/B ${metrics.pb_ratio.toFixed(2)} - 자산 대비 저평가`);
    } else if (metrics.pb_ratio <= 1.5) {
      score = 5;
      reason = "적정 범위 (1-1.5)";
    } else if (metrics.pb_ratio > 3) {
      score = -10;
      reason = "고평가 구간 (> 3)";
      negativeFactors.push(`P/B ${metrics.pb_ratio.toFixed(2)} - 고평가`);
    }
    breakdown.push({ metric: "P/B", value: metrics.pb_ratio, score, reason });
    totalScore += score;
  }

  // ROE
  if (metrics.roe != null) {
    let score = 0;
    let reason = "";
    if (metrics.roe > 20) {
      score = 15;
      reason = "우수한 수익성 (> 20%)";
      positiveFactors.push(`ROE ${metrics.roe.toFixed(1)}% - 우수한 수익성`);
    } else if (metrics.roe >= 10) {
      score = 10;
      reason = "양호한 수익성 (10-20%)";
    } else if (metrics.roe < 5) {
      score = -10;
      reason = "낮은 수익성 (< 5%)";
      negativeFactors.push(`ROE ${metrics.roe.toFixed(1)}% - 낮은 수익성`);
    }
    breakdown.push({ metric: "ROE", value: metrics.roe, score, reason });
    totalScore += score;
  }

  // Debt/Equity
  if (metrics.debt_equity != null) {
    let score = 0;
    let reason = "";
    if (metrics.debt_equity < 0.5) {
      score = 10;
      reason = "건전한 재무구조 (< 0.5)";
      positiveFactors.push(`D/E ${metrics.debt_equity.toFixed(2)} - 건전한 재무구조`);
    } else if (metrics.debt_equity > 2) {
      score = -15;
      reason = "높은 부채비율 (> 2)";
      negativeFactors.push(`D/E ${metrics.debt_equity.toFixed(2)} - 높은 부채`);
    }
    breakdown.push({
      metric: "D/E",
      value: metrics.debt_equity,
      score,
      reason,
    });
    totalScore += score;
  }

  // RSI
  if (metrics.rsi != null) {
    let score = 0;
    let reason = "";
    if (metrics.rsi < 30) {
      score = 10;
      reason = "과매도 구간 (< 30)";
      positiveFactors.push(`RSI ${metrics.rsi.toFixed(0)} - 과매도 (매수 기회)`);
    } else if (metrics.rsi > 70) {
      score = -10;
      reason = "과매수 구간 (> 70)";
      negativeFactors.push(`RSI ${metrics.rsi.toFixed(0)} - 과매수 (조정 주의)`);
    }
    breakdown.push({ metric: "RSI", value: metrics.rsi, score, reason });
    totalScore += score;
  }

  // Graham Number comparison
  if (metrics.graham_number != null && currentPrice != null) {
    let score = 0;
    let reason = "";
    const grahamDiff =
      ((metrics.graham_number - currentPrice) / metrics.graham_number) * 100;

    if (currentPrice < metrics.graham_number) {
      score = 15;
      reason = `Graham Number 대비 ${Math.abs(grahamDiff).toFixed(0)}% 저평가`;
      positiveFactors.push(
        `Graham $${metrics.graham_number.toFixed(0)} 대비 ${Math.abs(grahamDiff).toFixed(0)}% 저평가`
      );
    } else {
      reason = `Graham Number 대비 ${Math.abs(grahamDiff).toFixed(0)}% 고평가`;
    }
    breakdown.push({
      metric: "Graham",
      value: grahamDiff,
      score,
      reason,
    });
    totalScore += score;
  }

  // MA Trend (Bullish if 50MA > 200MA)
  if (
    metrics.fifty_day_average != null &&
    metrics.two_hundred_day_average != null
  ) {
    let score = 0;
    let reason = "";
    if (metrics.fifty_day_average > metrics.two_hundred_day_average) {
      score = 5;
      reason = "상승 추세 (50MA > 200MA)";
      positiveFactors.push("상승 추세 (골든크로스)");
    } else {
      reason = "하락 추세 (50MA < 200MA)";
    }
    breakdown.push({
      metric: "MA Trend",
      value: metrics.fifty_day_average - metrics.two_hundred_day_average,
      score,
      reason,
    });
    totalScore += score;
  }

  // MACD Histogram
  if (metrics.macd_histogram != null) {
    let score = 0;
    let reason = "";
    if (metrics.macd_histogram > 0) {
      score = 5;
      reason = "상승 모멘텀 (Histogram > 0)";
      positiveFactors.push("MACD 상승 모멘텀");
    } else {
      reason = "하락 모멘텀 (Histogram < 0)";
    }
    breakdown.push({
      metric: "MACD",
      value: metrics.macd_histogram,
      score,
      reason,
    });
    totalScore += score;
  }

  // Clamp score to 0-100
  totalScore = Math.max(0, Math.min(100, totalScore));

  const signal = getSignalFromScore(totalScore);

  return {
    totalScore,
    signal,
    signalLabel: SIGNAL_CONFIG[signal].label,
    breakdown,
    positiveFactors,
    negativeFactors,
  };
}

// Get signal display configuration
export function getSignalConfig(signal: SignalType) {
  return SIGNAL_CONFIG[signal];
}

// Get all signals for display
export function getAllSignals() {
  return Object.entries(SIGNAL_CONFIG).map(([key, value]) => ({
    signal: key as SignalType,
    ...value,
  }));
}
