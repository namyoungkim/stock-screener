import type { Metrics } from "./api";

// Risk level types
export type RiskLevel = "HIGH" | "MEDIUM" | "LOW";

export interface RiskItem {
  level: RiskLevel;
  category: string;
  message: string;
  value: number | null;
  threshold: string;
}

export interface RiskAssessment {
  hasHighRisk: boolean;
  hasMediumRisk: boolean;
  risks: RiskItem[];
  riskCount: {
    high: number;
    medium: number;
    low: number;
  };
}

// Risk level configuration
const RISK_LEVEL_CONFIG: Record<
  RiskLevel,
  { label: string; color: string; bgColor: string }
> = {
  HIGH: {
    label: "높음",
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-900/20",
  },
  MEDIUM: {
    label: "중간",
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-50 dark:bg-orange-900/20",
  },
  LOW: {
    label: "낮음",
    color: "text-yellow-600 dark:text-yellow-400",
    bgColor: "bg-yellow-50 dark:bg-yellow-900/20",
  },
};

// Detect risks from metrics
export function detectRisks(metrics: Metrics | undefined): RiskAssessment {
  const risks: RiskItem[] = [];

  if (!metrics) {
    return {
      hasHighRisk: false,
      hasMediumRisk: false,
      risks: [],
      riskCount: { high: 0, medium: 0, low: 0 },
    };
  }

  // HIGH: Debt/Equity > 2
  if (metrics.debt_equity != null && metrics.debt_equity > 2) {
    risks.push({
      level: "HIGH",
      category: "재무 위험",
      message: "높은 부채 비율 - 재무 건전성 주의",
      value: metrics.debt_equity,
      threshold: "D/E > 2",
    });
  }

  // HIGH: Current Ratio < 1
  if (metrics.current_ratio != null && metrics.current_ratio < 1) {
    risks.push({
      level: "HIGH",
      category: "유동성 위험",
      message: "단기 채무 상환 능력 부족",
      value: metrics.current_ratio,
      threshold: "Current Ratio < 1",
    });
  }

  // HIGH: Net Margin < 0
  if (metrics.net_margin != null && metrics.net_margin < 0) {
    risks.push({
      level: "HIGH",
      category: "수익성 위험",
      message: "순손실 기업 - 수익성 개선 필요",
      value: metrics.net_margin,
      threshold: "Net Margin < 0",
    });
  }

  // MEDIUM: Beta > 1.5
  if (metrics.beta != null && metrics.beta > 1.5) {
    risks.push({
      level: "MEDIUM",
      category: "변동성 위험",
      message: "시장 대비 높은 변동성",
      value: metrics.beta,
      threshold: "Beta > 1.5",
    });
  }

  // MEDIUM: RSI > 80
  if (metrics.rsi != null && metrics.rsi > 80) {
    risks.push({
      level: "MEDIUM",
      category: "기술적 위험",
      message: "과매수 상태 - 조정 가능성",
      value: metrics.rsi,
      threshold: "RSI > 80",
    });
  }

  // MEDIUM: P/E > 50 (extreme overvaluation)
  if (metrics.pe_ratio != null && metrics.pe_ratio > 50) {
    risks.push({
      level: "MEDIUM",
      category: "밸류에이션 위험",
      message: "극단적 고평가 - 기대치 미달 시 급락 가능",
      value: metrics.pe_ratio,
      threshold: "P/E > 50",
    });
  }

  // Count risks by level
  const riskCount = {
    high: risks.filter((r) => r.level === "HIGH").length,
    medium: risks.filter((r) => r.level === "MEDIUM").length,
    low: risks.filter((r) => r.level === "LOW").length,
  };

  return {
    hasHighRisk: riskCount.high > 0,
    hasMediumRisk: riskCount.medium > 0,
    risks,
    riskCount,
  };
}

// Get risk level configuration
export function getRiskLevelConfig(level: RiskLevel) {
  return RISK_LEVEL_CONFIG[level];
}

// Get overall risk summary
export function getRiskSummary(assessment: RiskAssessment): string {
  if (assessment.riskCount.high > 0) {
    return `높은 위험 ${assessment.riskCount.high}건 발견`;
  }
  if (assessment.riskCount.medium > 0) {
    return `중간 위험 ${assessment.riskCount.medium}건 발견`;
  }
  return "특별한 위험 요소 없음";
}
