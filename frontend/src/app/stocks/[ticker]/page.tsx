"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { formatMarketCap, formatPercent, formatRatio } from "@/lib/utils";

export default function StockDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const ticker = params.ticker as string;
  const market = searchParams.get("market") ?? undefined;

  const { data, isLoading, error } = useQuery({
    queryKey: ["stock", ticker, market],
    queryFn: () => api.getStock(ticker, market),
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="text-center text-red-600">
          Error loading stock data.
        </div>
      </div>
    );
  }

  const { company, metrics, price } = data;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Back button */}
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Screener
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-gray-900">{company.ticker}</h1>
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${
              company.market === "US"
                ? "bg-blue-100 text-blue-800"
                : company.market === "KOSPI"
                  ? "bg-green-100 text-green-800"
                  : "bg-purple-100 text-purple-800"
            }`}
          >
            {company.market}
          </span>
        </div>
        <p className="mt-1 text-xl text-gray-600">{company.name}</p>
        {company.sector && (
          <p className="mt-1 text-sm text-gray-500">
            {company.sector} {company.industry && `· ${company.industry}`}
          </p>
        )}
      </div>

      {/* Price Info */}
      {price && (
        <div className="mb-8 rounded-lg border bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold">Price</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-sm text-gray-500">Close</p>
              <p className="text-2xl font-bold">
                {price.close?.toLocaleString()} {company.currency}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Market Cap</p>
              <p className="text-lg font-semibold">
                {formatMarketCap(price.market_cap)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Volume</p>
              <p className="text-lg font-semibold">
                {price.volume?.toLocaleString() ?? "-"}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Date</p>
              <p className="text-lg font-semibold">{price.date}</p>
            </div>
          </div>
        </div>
      )}

      {/* Metrics */}
      {metrics && (
        <div className="rounded-lg border bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold">Key Metrics</h2>

          <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
            {/* Valuation */}
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                P/E Ratio
              </p>
              <p className="text-lg font-semibold">
                {formatRatio(metrics.pe_ratio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                P/B Ratio
              </p>
              <p className="text-lg font-semibold">
                {formatRatio(metrics.pb_ratio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                P/S Ratio
              </p>
              <p className="text-lg font-semibold">
                {formatRatio(metrics.ps_ratio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                EV/EBITDA
              </p>
              <p className="text-lg font-semibold">
                {formatRatio(metrics.ev_ebitda)}
              </p>
            </div>

            {/* Profitability */}
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">ROE</p>
              <p className="text-lg font-semibold">
                {formatPercent(metrics.roe)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">ROA</p>
              <p className="text-lg font-semibold">
                {formatPercent(metrics.roa)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                Gross Margin
              </p>
              <p className="text-lg font-semibold">
                {formatPercent(metrics.gross_margin)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                Net Margin
              </p>
              <p className="text-lg font-semibold">
                {formatPercent(metrics.net_margin)}
              </p>
            </div>

            {/* Financial Health */}
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                Debt/Equity
              </p>
              <p className="text-lg font-semibold">
                {formatRatio(metrics.debt_equity)}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                Current Ratio
              </p>
              <p className="text-lg font-semibold">
                {formatRatio(metrics.current_ratio)}
              </p>
            </div>

            {/* Dividend */}
            <div>
              <p className="text-xs font-medium uppercase text-gray-500">
                Dividend Yield
              </p>
              <p className="text-lg font-semibold">
                {formatPercent(metrics.dividend_yield)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
