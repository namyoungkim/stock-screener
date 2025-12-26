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
        className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Screener
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-slate-900">{company.ticker}</h1>
          <span
            className={`rounded-full px-3 py-1 text-sm font-semibold ${
              company.market === "US"
                ? "bg-blue-100 text-blue-800"
                : company.market === "KOSPI"
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-purple-100 text-purple-800"
            }`}
          >
            {company.market}
          </span>
        </div>
        <p className="mt-1 text-xl text-slate-700 font-medium">{company.name}</p>
        {company.sector && (
          <p className="mt-1 text-sm text-slate-500">
            {company.sector} {company.industry && `· ${company.industry}`}
          </p>
        )}
      </div>

      {/* Price Info */}
      {price && (
        <div className="mb-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-bold text-slate-800">Price</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-sm font-medium text-slate-500">Close</p>
              <p className="text-2xl font-bold text-blue-600">
                {price.close?.toLocaleString()} {company.currency}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">Market Cap</p>
              <p className="text-lg font-bold text-slate-900">
                {formatMarketCap(price.market_cap)}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">Volume</p>
              <p className="text-lg font-bold text-slate-900">
                {price.volume?.toLocaleString() ?? "-"}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">Date</p>
              <p className="text-lg font-bold text-slate-900">{price.date}</p>
            </div>
          </div>
        </div>
      )}

      {/* Metrics */}
      {metrics && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-bold text-slate-800">Key Metrics</h2>

          <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
            {/* Valuation */}
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                P/E Ratio
              </p>
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.pe_ratio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                P/B Ratio
              </p>
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.pb_ratio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                P/S Ratio
              </p>
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.ps_ratio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                EV/EBITDA
              </p>
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.ev_ebitda)}
              </p>
            </div>

            {/* Profitability */}
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">ROE</p>
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.roe)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">ROA</p>
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.roa)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Gross Margin
              </p>
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.gross_margin)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Net Margin
              </p>
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.net_margin)}
              </p>
            </div>

            {/* Financial Health */}
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Debt/Equity
              </p>
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.debt_equity)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Current Ratio
              </p>
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.current_ratio)}
              </p>
            </div>

            {/* Dividend */}
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Dividend Yield
              </p>
              <p className="text-lg font-bold text-orange-600">
                {formatPercent(metrics.dividend_yield)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
