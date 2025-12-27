"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { formatMarketCap, formatPercent, formatRatio } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import { metricsGlossary } from "@/lib/glossary";

function MetricLabel({ label, glossaryKey }: { label: string; glossaryKey: string }) {
  const tooltip = metricsGlossary[glossaryKey];
  return (
    <p className="text-xs font-semibold uppercase text-slate-500">
      {tooltip ? (
        <Tooltip content={tooltip} position="bottom">
          <span className="border-b border-dashed border-slate-400">{label}</span>
        </Tooltip>
      ) : (
        label
      )}
    </p>
  );
}

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
              <p className="text-sm font-medium text-slate-500">
                <Tooltip content={metricsGlossary.market_cap} position="bottom">
                  <span className="border-b border-dashed border-slate-400">Market Cap</span>
                </Tooltip>
              </p>
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

          {/* 52 Week Range */}
          {metrics && (metrics.fifty_two_week_high || metrics.fifty_two_week_low) && (
            <div className="mt-6 border-t border-gray-100 pt-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">52 Week Range</h3>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-slate-500">
                    <Tooltip content={metricsGlossary.fifty_two_week_low} position="bottom">
                      <span className="border-b border-dashed border-slate-400">52W Low</span>
                    </Tooltip>
                  </p>
                  <p className="text-lg font-bold text-red-600">
                    {metrics.fifty_two_week_low?.toLocaleString() ?? "-"} {company.currency}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-500">
                    <Tooltip content={metricsGlossary.fifty_two_week_high} position="bottom">
                      <span className="border-b border-dashed border-slate-400">52W High</span>
                    </Tooltip>
                  </p>
                  <p className="text-lg font-bold text-green-600">
                    {metrics.fifty_two_week_high?.toLocaleString() ?? "-"} {company.currency}
                  </p>
                </div>
                {price.close && metrics.fifty_two_week_low && metrics.fifty_two_week_high && (
                  <div>
                    <p className="text-sm font-medium text-slate-500">Position</p>
                    <p className="text-lg font-bold text-slate-900">
                      {(((price.close - metrics.fifty_two_week_low) / (metrics.fifty_two_week_high - metrics.fifty_two_week_low)) * 100).toFixed(1)}%
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Moving Averages */}
          {metrics && (metrics.fifty_day_average || metrics.two_hundred_day_average) && (
            <div className="mt-6 border-t border-gray-100 pt-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-600">Moving Averages</h3>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-slate-500">
                    <Tooltip content={metricsGlossary.fifty_day_average} position="bottom">
                      <span className="border-b border-dashed border-slate-400">MA 50</span>
                    </Tooltip>
                  </p>
                  <p className={`text-lg font-bold ${
                    price?.close && metrics.fifty_day_average && price.close > metrics.fifty_day_average
                      ? "text-green-600" : "text-red-600"
                  }`}>
                    {metrics.fifty_day_average?.toLocaleString(undefined, {maximumFractionDigits: 2}) ?? "-"} {company.currency}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-500">
                    <Tooltip content={metricsGlossary.two_hundred_day_average} position="bottom">
                      <span className="border-b border-dashed border-slate-400">MA 200</span>
                    </Tooltip>
                  </p>
                  <p className={`text-lg font-bold ${
                    price?.close && metrics.two_hundred_day_average && price.close > metrics.two_hundred_day_average
                      ? "text-green-600" : "text-red-600"
                  }`}>
                    {metrics.two_hundred_day_average?.toLocaleString(undefined, {maximumFractionDigits: 2}) ?? "-"} {company.currency}
                  </p>
                </div>
                {price?.close && metrics.fifty_day_average && metrics.two_hundred_day_average && (
                  <div>
                    <p className="text-sm font-medium text-slate-500">Trend</p>
                    <p className={`text-lg font-bold ${
                      metrics.fifty_day_average > metrics.two_hundred_day_average ? "text-green-600" : "text-red-600"
                    }`}>
                      {metrics.fifty_day_average > metrics.two_hundred_day_average ? "↑ Bullish" : "↓ Bearish"}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Metrics */}
      {metrics && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-bold text-slate-800">Key Metrics</h2>

          <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
            {/* Valuation */}
            <div>
              <MetricLabel label="P/E Ratio" glossaryKey="pe_ratio" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.pe_ratio)}
              </p>
            </div>
            <div>
              <MetricLabel label="P/B Ratio" glossaryKey="pb_ratio" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.pb_ratio)}
              </p>
            </div>
            <div>
              <MetricLabel label="P/S Ratio" glossaryKey="ps_ratio" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.ps_ratio)}
              </p>
            </div>
            <div>
              <MetricLabel label="EV/EBITDA" glossaryKey="ev_ebitda" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.ev_ebitda)}
              </p>
            </div>

            {/* Profitability */}
            <div>
              <MetricLabel label="ROE" glossaryKey="roe" />
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.roe)}
              </p>
            </div>
            <div>
              <MetricLabel label="ROA" glossaryKey="roa" />
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.roa)}
              </p>
            </div>
            <div>
              <MetricLabel label="Gross Margin" glossaryKey="gross_margin" />
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.gross_margin)}
              </p>
            </div>
            <div>
              <MetricLabel label="Net Margin" glossaryKey="net_margin" />
              <p className="text-lg font-bold text-emerald-600">
                {formatPercent(metrics.net_margin)}
              </p>
            </div>

            {/* Financial Health */}
            <div>
              <MetricLabel label="Debt/Equity" glossaryKey="debt_equity" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.debt_equity)}
              </p>
            </div>
            <div>
              <MetricLabel label="Current Ratio" glossaryKey="current_ratio" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.current_ratio)}
              </p>
            </div>

            {/* Dividend */}
            <div>
              <MetricLabel label="Dividend Yield" glossaryKey="dividend_yield" />
              <p className="text-lg font-bold text-orange-600">
                {formatPercent(metrics.dividend_yield)}
              </p>
            </div>

            {/* Graham Number */}
            <div>
              <MetricLabel label="EPS" glossaryKey="eps" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.eps)}
              </p>
            </div>
            <div>
              <MetricLabel label="BPS" glossaryKey="book_value_per_share" />
              <p className="text-lg font-bold text-slate-900">
                {formatRatio(metrics.book_value_per_share)}
              </p>
            </div>
            <div>
              <MetricLabel label="Graham Number" glossaryKey="graham_number" />
              <p className="text-lg font-bold text-violet-600">
                {formatRatio(metrics.graham_number)}
              </p>
            </div>

            {/* Risk */}
            <div>
              <MetricLabel label="Beta" glossaryKey="beta" />
              <p className={`text-lg font-bold ${
                metrics.beta && metrics.beta > 1.5 ? "text-red-600" :
                metrics.beta && metrics.beta < 0.8 ? "text-green-600" :
                "text-slate-900"
              }`}>
                {formatRatio(metrics.beta)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
