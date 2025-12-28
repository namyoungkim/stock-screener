"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { WatchlistButton } from "@/components/WatchlistButton";
import { AlertForm } from "@/components/AlertForm";
import { formatMarketCap, formatPercent, formatRatio } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import { metricsGlossary } from "@/lib/glossary";
import { SkeletonStockDetail } from "@/components/ui/Skeleton";

function MetricLabel({ label, glossaryKey }: { label: string; glossaryKey: string }) {
  const tooltip = metricsGlossary[glossaryKey];
  return (
    <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
      {tooltip ? (
        <Tooltip content={tooltip} position="bottom">
          <span className="border-b border-dashed border-slate-400 dark:border-slate-500">{label}</span>
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
    return <SkeletonStockDetail />;
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="text-center text-red-600 dark:text-red-400">
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
        className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Screener
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">{company.ticker}</h1>
          <span
            className={`rounded-full px-3 py-1 text-sm font-semibold ${
              company.market === "US"
                ? "bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300"
                : company.market === "KOSPI"
                  ? "bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-300"
                  : "bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300"
            }`}
          >
            {company.market}
          </span>
          <WatchlistButton companyId={company.id} />
          <AlertForm companyId={company.id} ticker={company.ticker} companyName={company.name} />
        </div>
        <p className="mt-1 text-xl text-slate-700 dark:text-slate-200 font-medium">{company.name}</p>
        {company.sector && (
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {company.sector} {company.industry && `· ${company.industry}`}
          </p>
        )}
      </div>

      {/* Price Info */}
      {price && (
        <div className="mb-8 rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-bold text-slate-800 dark:text-white">Price</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Close</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {price.close?.toLocaleString()} {company.currency}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                <Tooltip content={metricsGlossary.market_cap} position="bottom">
                  <span className="border-b border-dashed border-slate-400 dark:border-slate-500">Market Cap</span>
                </Tooltip>
              </p>
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatMarketCap(price.market_cap)}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Volume</p>
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {price.volume?.toLocaleString() ?? "-"}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Date</p>
              <p className="text-lg font-bold text-slate-900 dark:text-white">{price.date}</p>
            </div>
          </div>

          {/* 52 Week Range */}
          {metrics && (metrics.fifty_two_week_high || metrics.fifty_two_week_low) && (
            <div className="mt-6 border-t border-gray-100 dark:border-slate-600 pt-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">52 Week Range</h3>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    <Tooltip content={metricsGlossary.fifty_two_week_low} position="bottom">
                      <span className="border-b border-dashed border-slate-400 dark:border-slate-500">52W Low</span>
                    </Tooltip>
                  </p>
                  <p className="text-lg font-bold text-red-600 dark:text-red-400">
                    {metrics.fifty_two_week_low?.toLocaleString() ?? "-"} {company.currency}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    <Tooltip content={metricsGlossary.fifty_two_week_high} position="bottom">
                      <span className="border-b border-dashed border-slate-400 dark:border-slate-500">52W High</span>
                    </Tooltip>
                  </p>
                  <p className="text-lg font-bold text-green-600 dark:text-green-400">
                    {metrics.fifty_two_week_high?.toLocaleString() ?? "-"} {company.currency}
                  </p>
                </div>
                {price.close && metrics.fifty_two_week_low && metrics.fifty_two_week_high && (
                  <div>
                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Position</p>
                    <p className="text-lg font-bold text-slate-900 dark:text-white">
                      {(((price.close - metrics.fifty_two_week_low) / (metrics.fifty_two_week_high - metrics.fifty_two_week_low)) * 100).toFixed(1)}%
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Moving Averages */}
          {metrics && (metrics.fifty_day_average || metrics.two_hundred_day_average) && (
            <div className="mt-6 border-t border-gray-100 dark:border-slate-600 pt-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">Moving Averages</h3>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    <Tooltip content={metricsGlossary.fifty_day_average} position="bottom">
                      <span className="border-b border-dashed border-slate-400 dark:border-slate-500">MA 50</span>
                    </Tooltip>
                  </p>
                  <p className={`text-lg font-bold ${
                    price?.close && metrics.fifty_day_average && price.close > metrics.fifty_day_average
                      ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                  }`}>
                    {metrics.fifty_day_average?.toLocaleString(undefined, {maximumFractionDigits: 2}) ?? "-"} {company.currency}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    <Tooltip content={metricsGlossary.two_hundred_day_average} position="bottom">
                      <span className="border-b border-dashed border-slate-400 dark:border-slate-500">MA 200</span>
                    </Tooltip>
                  </p>
                  <p className={`text-lg font-bold ${
                    price?.close && metrics.two_hundred_day_average && price.close > metrics.two_hundred_day_average
                      ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                  }`}>
                    {metrics.two_hundred_day_average?.toLocaleString(undefined, {maximumFractionDigits: 2}) ?? "-"} {company.currency}
                  </p>
                </div>
                {price?.close && metrics.fifty_day_average && metrics.two_hundred_day_average && (
                  <div>
                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Trend</p>
                    <p className={`text-lg font-bold ${
                      metrics.fifty_day_average > metrics.two_hundred_day_average ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
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
        <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-bold text-slate-800 dark:text-white">Key Metrics</h2>

          <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-4">
            {/* Valuation */}
            <div>
              <MetricLabel label="P/E Ratio" glossaryKey="pe_ratio" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.pe_ratio)}
              </p>
            </div>
            <div>
              <MetricLabel label="P/B Ratio" glossaryKey="pb_ratio" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.pb_ratio)}
              </p>
            </div>
            <div>
              <MetricLabel label="P/S Ratio" glossaryKey="ps_ratio" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.ps_ratio)}
              </p>
            </div>
            <div>
              <MetricLabel label="EV/EBITDA" glossaryKey="ev_ebitda" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.ev_ebitda)}
              </p>
            </div>
            <div>
              <MetricLabel label="PEG" glossaryKey="peg_ratio" />
              <p className={`text-lg font-bold ${
                metrics.peg_ratio && metrics.peg_ratio < 1 ? "text-green-600 dark:text-green-400" :
                metrics.peg_ratio && metrics.peg_ratio > 2 ? "text-red-600 dark:text-red-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {formatRatio(metrics.peg_ratio)}
              </p>
            </div>

            {/* Profitability */}
            <div>
              <MetricLabel label="ROE" glossaryKey="roe" />
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                {formatPercent(metrics.roe)}
              </p>
            </div>
            <div>
              <MetricLabel label="ROA" glossaryKey="roa" />
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                {formatPercent(metrics.roa)}
              </p>
            </div>
            <div>
              <MetricLabel label="Gross Margin" glossaryKey="gross_margin" />
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                {formatPercent(metrics.gross_margin)}
              </p>
            </div>
            <div>
              <MetricLabel label="Net Margin" glossaryKey="net_margin" />
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                {formatPercent(metrics.net_margin)}
              </p>
            </div>

            {/* Financial Health */}
            <div>
              <MetricLabel label="Debt/Equity" glossaryKey="debt_equity" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.debt_equity)}
              </p>
            </div>
            <div>
              <MetricLabel label="Current Ratio" glossaryKey="current_ratio" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.current_ratio)}
              </p>
            </div>

            {/* Dividend */}
            <div>
              <MetricLabel label="Dividend Yield" glossaryKey="dividend_yield" />
              <p className="text-lg font-bold text-orange-600 dark:text-orange-400">
                {formatPercent(metrics.dividend_yield)}
              </p>
            </div>

            {/* Graham Number */}
            <div>
              <MetricLabel label="EPS" glossaryKey="eps" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.eps)}
              </p>
            </div>
            <div>
              <MetricLabel label="BPS" glossaryKey="book_value_per_share" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {formatRatio(metrics.book_value_per_share)}
              </p>
            </div>
            <div>
              <MetricLabel label="Graham Number" glossaryKey="graham_number" />
              <p className="text-lg font-bold text-violet-600 dark:text-violet-400">
                {formatRatio(metrics.graham_number)}
              </p>
            </div>

            {/* Risk */}
            <div>
              <MetricLabel label="Beta" glossaryKey="beta" />
              <p className={`text-lg font-bold ${
                metrics.beta && metrics.beta > 1.5 ? "text-red-600 dark:text-red-400" :
                metrics.beta && metrics.beta < 0.8 ? "text-green-600 dark:text-green-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {formatRatio(metrics.beta)}
              </p>
            </div>

            {/* Technical Indicators */}
            <div>
              <MetricLabel label="RSI" glossaryKey="rsi" />
              <p className={`text-lg font-bold ${
                metrics.rsi && metrics.rsi < 30 ? "text-green-600 dark:text-green-400" :
                metrics.rsi && metrics.rsi > 70 ? "text-red-600 dark:text-red-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {metrics.rsi != null ? `${metrics.rsi.toFixed(1)}` : "-"}
                {metrics.rsi != null && (
                  <span className="ml-1 text-sm font-normal text-slate-500 dark:text-slate-400">
                    {metrics.rsi < 30 ? "(Oversold)" : metrics.rsi > 70 ? "(Overbought)" : ""}
                  </span>
                )}
              </p>
            </div>
            <div>
              <MetricLabel label="Vol Chg" glossaryKey="volume_change" />
              <p className={`text-lg font-bold ${
                metrics.volume_change && metrics.volume_change > 100 ? "text-red-600 dark:text-red-400" :
                metrics.volume_change && metrics.volume_change > 50 ? "text-orange-600 dark:text-orange-400" :
                metrics.volume_change && metrics.volume_change < -50 ? "text-blue-600 dark:text-blue-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {metrics.volume_change != null ? `${metrics.volume_change > 0 ? "+" : ""}${metrics.volume_change.toFixed(1)}%` : "-"}
              </p>
            </div>

            {/* MACD */}
            <div>
              <MetricLabel label="MACD" glossaryKey="macd" />
              <p className={`text-lg font-bold ${
                metrics.macd_histogram && metrics.macd_histogram > 0 ? "text-green-600 dark:text-green-400" :
                metrics.macd_histogram && metrics.macd_histogram < 0 ? "text-red-600 dark:text-red-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {metrics.macd != null ? metrics.macd.toFixed(2) : "-"}
              </p>
            </div>
            <div>
              <MetricLabel label="Signal" glossaryKey="macd_signal" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {metrics.macd_signal != null ? metrics.macd_signal.toFixed(2) : "-"}
              </p>
            </div>
            <div>
              <MetricLabel label="Histogram" glossaryKey="macd_histogram" />
              <p className={`text-lg font-bold ${
                metrics.macd_histogram && metrics.macd_histogram > 0 ? "text-green-600 dark:text-green-400" :
                metrics.macd_histogram && metrics.macd_histogram < 0 ? "text-red-600 dark:text-red-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {metrics.macd_histogram != null ? `${metrics.macd_histogram > 0 ? "+" : ""}${metrics.macd_histogram.toFixed(2)}` : "-"}
              </p>
            </div>

            {/* Bollinger Bands */}
            <div>
              <MetricLabel label="BB Upper" glossaryKey="bb_upper" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {metrics.bb_upper != null ? metrics.bb_upper.toLocaleString() : "-"}
              </p>
            </div>
            <div>
              <MetricLabel label="BB Middle" glossaryKey="bb_middle" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {metrics.bb_middle != null ? metrics.bb_middle.toLocaleString() : "-"}
              </p>
            </div>
            <div>
              <MetricLabel label="BB Lower" glossaryKey="bb_lower" />
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                {metrics.bb_lower != null ? metrics.bb_lower.toLocaleString() : "-"}
              </p>
            </div>
            <div>
              <MetricLabel label="BB %" glossaryKey="bb_percent" />
              <p className={`text-lg font-bold ${
                metrics.bb_percent && metrics.bb_percent > 100 ? "text-red-600 dark:text-red-400" :
                metrics.bb_percent && metrics.bb_percent < 0 ? "text-green-600 dark:text-green-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {metrics.bb_percent != null ? `${metrics.bb_percent.toFixed(1)}%` : "-"}
                {metrics.bb_percent != null && (
                  <span className="ml-1 text-sm font-normal text-slate-500 dark:text-slate-400">
                    {metrics.bb_percent > 100 ? "(Overbought)" : metrics.bb_percent < 0 ? "(Oversold)" : ""}
                  </span>
                )}
              </p>
            </div>

            {/* MFI */}
            <div>
              <MetricLabel label="MFI" glossaryKey="mfi" />
              <p className={`text-lg font-bold ${
                metrics.mfi && metrics.mfi >= 80 ? "text-red-600 dark:text-red-400" :
                metrics.mfi && metrics.mfi <= 20 ? "text-green-600 dark:text-green-400" :
                "text-slate-900 dark:text-white"
              }`}>
                {metrics.mfi != null ? metrics.mfi.toFixed(1) : "-"}
                {metrics.mfi != null && (
                  <span className="ml-1 text-sm font-normal text-slate-500 dark:text-slate-400">
                    {metrics.mfi >= 80 ? "(Overbought)" : metrics.mfi <= 20 ? "(Oversold)" : ""}
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
