"use client";

import Link from "next/link";
import { CompanyWithMetrics } from "@/lib/api";
import { formatMarketCap, formatPercent, formatRatio } from "@/lib/utils";

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
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Ticker
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Name
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Market
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Market Cap
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              P/E
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              P/B
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              ROE
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Div Yield
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {stocks.map((stock) => (
            <tr key={stock.id} className="hover:bg-gray-50">
              <td className="whitespace-nowrap px-4 py-4">
                <Link
                  href={`/stocks/${stock.ticker}?market=${stock.market}`}
                  className="font-medium text-blue-600 hover:underline"
                >
                  {stock.ticker}
                </Link>
              </td>
              <td className="px-4 py-4">
                <div className="max-w-xs truncate">{stock.name}</div>
              </td>
              <td className="whitespace-nowrap px-4 py-4">
                <span
                  className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                    stock.market === "US"
                      ? "bg-blue-100 text-blue-800"
                      : stock.market === "KOSPI"
                        ? "bg-green-100 text-green-800"
                        : "bg-purple-100 text-purple-800"
                  }`}
                >
                  {stock.market}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right">
                {formatMarketCap(stock.market_cap)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right">
                {formatRatio(stock.pe_ratio)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right">
                {formatRatio(stock.pb_ratio)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right">
                {formatPercent(stock.roe)}
              </td>
              <td className="whitespace-nowrap px-4 py-4 text-right">
                {formatPercent(stock.dividend_yield)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
