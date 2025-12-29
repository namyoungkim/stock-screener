"use client";

import type { Metrics, Price } from "@/lib/api";

interface ActionGuideProps {
  metrics?: Metrics;
  price?: Price;
  currency?: string;
}

interface ActionItem {
  type: "positive" | "negative" | "neutral";
  text: string;
}

function formatCurrency(value: number, currency: string = "USD"): string {
  if (currency === "KRW") {
    return `₩${value.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
  }
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

function generateActionItems(
  metrics: Metrics | undefined,
  price: Price | undefined,
  currency: string
): ActionItem[] {
  const items: ActionItem[] = [];

  if (!metrics) return items;

  const currentPrice = price?.close;

  // Graham Number comparison
  if (metrics.graham_number != null && currentPrice != null) {
    const diff =
      ((metrics.graham_number - currentPrice) / metrics.graham_number) * 100;
    if (diff > 0) {
      items.push({
        type: "positive",
        text: `Graham ${formatCurrency(metrics.graham_number, currency)} 대비 ${diff.toFixed(0)}% 저평가`,
      });
    } else if (diff < -20) {
      items.push({
        type: "negative",
        text: `Graham ${formatCurrency(metrics.graham_number, currency)} 대비 ${Math.abs(diff).toFixed(0)}% 고평가`,
      });
    }
  }

  // 52-week range
  if (
    metrics.fifty_two_week_low != null &&
    metrics.fifty_two_week_high != null &&
    currentPrice != null
  ) {
    const range = metrics.fifty_two_week_high - metrics.fifty_two_week_low;
    const position = ((currentPrice - metrics.fifty_two_week_low) / range) * 100;

    if (position < 20) {
      items.push({
        type: "positive",
        text: "52주 저점 근접 - 추가 매수 기회 가능",
      });
    } else if (position > 90) {
      items.push({
        type: "negative",
        text: "52주 고점 근접 - 조정 가능성 주의",
      });
    }
  }

  // RSI based action
  if (metrics.rsi != null) {
    if (metrics.rsi < 30) {
      items.push({
        type: "positive",
        text: `RSI ${metrics.rsi.toFixed(0)} 과매도 - 기술적 반등 기대`,
      });
    } else if (metrics.rsi > 70) {
      items.push({
        type: "neutral",
        text: `RSI ${metrics.rsi.toFixed(0)} 과매수 - 단기 조정 후 진입 고려`,
      });
    }
  }

  // Dividend yield opportunity
  if (metrics.dividend_yield != null && metrics.dividend_yield > 4) {
    items.push({
      type: "positive",
      text: `배당수익률 ${metrics.dividend_yield.toFixed(1)}% - 배당 투자 매력`,
    });
  }

  // MA trend
  if (
    metrics.fifty_day_average != null &&
    metrics.two_hundred_day_average != null
  ) {
    if (metrics.fifty_day_average > metrics.two_hundred_day_average) {
      items.push({
        type: "positive",
        text: "상승 추세 (골든크로스) - 추세 추종 유리",
      });
    } else {
      items.push({
        type: "neutral",
        text: "하락 추세 (데드크로스) - 추세 반전 확인 필요",
      });
    }
  }

  return items;
}

export function ActionGuide({ metrics, price, currency = "USD" }: ActionGuideProps) {
  const actionItems = generateActionItems(metrics, price, currency);

  if (actionItems.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <h3 className="text-sm font-medium text-gray-700 dark:text-slate-300 mb-3">
        액션 가이드
      </h3>
      <ul className="space-y-2">
        {actionItems.map((item, index) => (
          <li key={index} className="flex items-start gap-2 text-sm">
            <span
              className={`mt-0.5 flex-shrink-0 ${
                item.type === "positive"
                  ? "text-emerald-500"
                  : item.type === "negative"
                    ? "text-red-500"
                    : "text-gray-400 dark:text-slate-500"
              }`}
            >
              {item.type === "positive"
                ? "●"
                : item.type === "negative"
                  ? "●"
                  : "○"}
            </span>
            <span className="text-gray-700 dark:text-slate-300">{item.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
