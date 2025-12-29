"use client";

import type { Metrics } from "@/lib/api";
import { detectRisks, getRiskLevelConfig, type RiskLevel } from "@/lib/risks";

interface RiskAlertProps {
  metrics?: Metrics;
}

const LEVEL_ICONS: Record<RiskLevel, string> = {
  HIGH: "🚨",
  MEDIUM: "⚠️",
  LOW: "ℹ️",
};

export function RiskAlert({ metrics }: RiskAlertProps) {
  const assessment = detectRisks(metrics);

  if (assessment.risks.length === 0) {
    return null;
  }

  const highRisks = assessment.risks.filter((r) => r.level === "HIGH");
  const mediumRisks = assessment.risks.filter((r) => r.level === "MEDIUM");

  return (
    <div
      className={`rounded-lg border p-4 ${
        assessment.hasHighRisk
          ? "border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20"
          : "border-orange-300 dark:border-orange-700 bg-orange-50 dark:bg-orange-900/20"
      }`}
    >
      <h3
        className={`text-sm font-medium mb-3 ${
          assessment.hasHighRisk
            ? "text-red-800 dark:text-red-300"
            : "text-orange-800 dark:text-orange-300"
        }`}
      >
        {LEVEL_ICONS[assessment.hasHighRisk ? "HIGH" : "MEDIUM"]} 리스크 경고
      </h3>

      <div className="space-y-2">
        {highRisks.map((risk, index) => (
          <RiskItem key={`high-${index}`} risk={risk} />
        ))}
        {mediumRisks.map((risk, index) => (
          <RiskItem key={`medium-${index}`} risk={risk} />
        ))}
      </div>
    </div>
  );
}

function RiskItem({
  risk,
}: {
  risk: {
    level: RiskLevel;
    category: string;
    message: string;
    value: number | null;
    threshold: string;
  };
}) {
  const config = getRiskLevelConfig(risk.level);

  return (
    <div className="flex items-start gap-2 text-sm">
      <span className={`font-medium ${config.color}`}>
        [{risk.category}]
      </span>
      <span className="text-gray-700 dark:text-slate-300">{risk.message}</span>
      {risk.value != null && (
        <span className="text-gray-500 dark:text-slate-400 text-xs">
          ({risk.threshold}: {risk.value.toFixed(2)})
        </span>
      )}
    </div>
  );
}

// Compact badge for lists
export function RiskBadge({ metrics }: RiskAlertProps) {
  const assessment = detectRisks(metrics);

  if (assessment.risks.length === 0) {
    return null;
  }

  if (assessment.hasHighRisk) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">
        🚨 위험 {assessment.riskCount.high}건
      </span>
    );
  }

  if (assessment.hasMediumRisk) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300">
        ⚠️ 주의 {assessment.riskCount.medium}건
      </span>
    );
  }

  return null;
}
