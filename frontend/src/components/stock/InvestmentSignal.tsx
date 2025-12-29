"use client";

import type { Metrics, Price } from "@/lib/api";
import { calculateInvestmentScore, type SignalType } from "@/lib/scoring";

interface InvestmentSignalProps {
  metrics?: Metrics;
  price?: Price;
}

const SIGNAL_STYLES: Record<SignalType, string> = {
  STRONG_BUY:
    "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700",
  BUY: "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-300 dark:border-green-700",
  HOLD: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 border-yellow-300 dark:border-yellow-700",
  SELL: "bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300 border-orange-300 dark:border-orange-700",
  STRONG_SELL:
    "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-300 dark:border-red-700",
};

const SCORE_BAR_COLORS: Record<SignalType, string> = {
  STRONG_BUY: "bg-emerald-500",
  BUY: "bg-green-500",
  HOLD: "bg-yellow-500",
  SELL: "bg-orange-500",
  STRONG_SELL: "bg-red-500",
};

export function InvestmentSignal({ metrics, price }: InvestmentSignalProps) {
  const score = calculateInvestmentScore(metrics, price);

  return (
    <div
      className={`rounded-lg border p-4 ${SIGNAL_STYLES[score.signal]}`}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium opacity-80">투자 신호</h3>
        <span className="text-xs opacity-70">규칙 기반 분석</span>
      </div>

      <div className="flex items-center gap-4 mb-3">
        <div className="text-2xl font-bold">{score.signalLabel}</div>
        <div className="text-3xl font-bold">{score.totalScore}</div>
        <div className="text-sm opacity-70">/100</div>
      </div>

      {/* Score bar */}
      <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full mb-4">
        <div
          className={`h-full rounded-full transition-all ${SCORE_BAR_COLORS[score.signal]}`}
          style={{ width: `${score.totalScore}%` }}
        />
      </div>

      {/* Summary */}
      {(score.positiveFactors.length > 0 ||
        score.negativeFactors.length > 0) && (
        <div className="text-sm space-y-2">
          {score.positiveFactors.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {score.positiveFactors.slice(0, 3).map((factor, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-white/50 dark:bg-black/20"
                >
                  <span className="mr-1">+</span>
                  {factor}
                </span>
              ))}
            </div>
          )}
          {score.negativeFactors.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {score.negativeFactors.slice(0, 2).map((factor, i) => (
                <span
                  key={i}
                  className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-black/10 dark:bg-white/10"
                >
                  <span className="mr-1">-</span>
                  {factor}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Compact version for watchlist page
export function InvestmentSignalBadge({
  metrics,
  price,
}: InvestmentSignalProps) {
  const score = calculateInvestmentScore(metrics, price);

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium border ${SIGNAL_STYLES[score.signal]}`}
    >
      <span>{score.signalLabel}</span>
      <span className="opacity-70">({score.totalScore})</span>
    </span>
  );
}
