"use client";

import Link from "next/link";
import { CompanyWithMetrics } from "@/lib/api";
import { formatMarketCap, formatPercent, formatRatio } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import { getMetricTooltip } from "@/lib/glossary";

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
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (stocks.length === 0) {
    return (
      <div className="py-12 text-center text-gray-500">
        No stocks found. Try adjusting your filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-slate-800">
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
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {stocks.map((stock) => (
            <tr key={stock.id} className="hover:bg-blue-50 transition-colors">
              <td className="whitespace-nowrap px-4 py-4">
                <Link
                  href={`/stocks/${stock.ticker}?market=${stock.market}`}
                  className="font-bold text-blue-600 hover:text-blue-800 hover:underline"
                >
                  {stock.ticker}
                </Link>
              </td>
              <td className="px-4 py-4 text-gray-900 font-medium">
                <Tooltip content={stock.name} position="bottom">
                  <div className="w-[180px] truncate cursor-default">{stock.name}</div>
                </Tooltip>
              </td>
              <td className="whitespace-nowrap px-4 py-4">
                <span
                  className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                    stock.market === "US"
                      ? "bg-blue-100 text-blue-800"
                      : stock.market === "KOSPI"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-purple-100 text-purple-800"
                  }`}
                >
                  {stock.market}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-gray-900 font-medium">
                {formatMarketCap(stock.market_cap)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-gray-900">
                {formatRatio(stock.pe_ratio)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-gray-900">
                {formatRatio(stock.pb_ratio)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-emerald-600 font-medium">
                {formatPercent(stock.roe)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right text-orange-600 font-medium">
                {formatPercent(stock.dividend_yield)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
