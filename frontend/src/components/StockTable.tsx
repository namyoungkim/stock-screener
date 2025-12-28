"use client";

import Link from "next/link";
import { CompanyWithMetrics } from "@/lib/api";
import { formatMarketCap, formatPercent, formatRatio } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import { getMetricTooltip } from "@/lib/glossary";
import { WatchlistButton } from "@/components/WatchlistButton";
import { SkeletonTable } from "@/components/ui/Skeleton";

function MetricHeader({ label, align = "right" }: { label: string; align?: "left" | "right" }) {
  const tooltip = getMetricTooltip(label);
  const alignClass = align === "right" ? "text-right" : "text-left";

  return (
    <th className={`px-4 py-3 ${alignClass} text-xs font-semibold uppercase tracking-wider text-white`}>
      {tooltip ? (
        <Tooltip content={tooltip} position="bottom">
          <span className="border-b border-dashed border-white/50">{label}</span>
        </Tooltip>
      ) : (
        label
      )}
    </th>
  );
}

interface StockTableProps {
  stocks: CompanyWithMetrics[];
  isLoading?: boolean;
}

export function StockTable({ stocks, isLoading }: StockTableProps) {
  if (isLoading) {
    return <SkeletonTable rows={10} columns={9} />;
  }

  if (stocks.length === 0) {
    return (
      <div className="py-12 text-center text-gray-500 dark:text-gray-400">
        No stocks found. Try adjusting your filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
        <thead className="bg-slate-800 dark:bg-slate-900">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-white">
              Ticker
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-white">
              Name
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-white">
              Market
            </th>
            <MetricHeader label="Market Cap" />
            <MetricHeader label="P/E" />
            <MetricHeader label="P/B" />
            <MetricHeader label="ROE" />
            <MetricHeader label="Div Yield" />
            <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-white">
              Watch
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-slate-700 bg-white dark:bg-slate-800">
          {stocks.map((stock) => (
            <tr key={stock.id} className="hover:bg-blue-50 dark:hover:bg-slate-700 transition-colors">
              <td className="whitespace-nowrap px-4 py-4">
                <Link
                  href={`/stocks/${stock.ticker}?market=${stock.market}`}
                  className="font-bold text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline"
                >
                  {stock.ticker}
                </Link>
              </td>
              <td className="px-4 py-4 text-gray-900 dark:text-gray-100 font-medium">
                <Tooltip content={stock.name} position="bottom">
                  <div className="w-[180px] truncate cursor-default">{stock.name}</div>
                </Tooltip>
              </td>
              <td className="whitespace-nowrap px-4 py-4">
                <span
                  className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                    stock.market === "US"
                      ? "bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300"
                      : stock.market === "KOSPI"
                        ? "bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-300"
                        : "bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300"
                  }`}
                >
                  {stock.market}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-gray-900 dark:text-gray-100 font-medium">
                {formatMarketCap(stock.market_cap)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-gray-900 dark:text-gray-100">
                {formatRatio(stock.pe_ratio)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-gray-900 dark:text-gray-100">
                {formatRatio(stock.pb_ratio)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-emerald-600 dark:text-emerald-400 font-medium">
                {formatPercent(stock.roe)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-orange-600 dark:text-orange-400 font-medium">
                {formatPercent(stock.dividend_yield)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-center">
                <WatchlistButton companyId={stock.id} size="sm" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
