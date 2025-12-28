"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Bell, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { api, AlertItem } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { metricsGlossary } from "@/lib/glossary";
import { SkeletonTable } from "@/components/ui/Skeleton";

// Available metrics for alerts
const ALERT_METRICS = [
  { value: "pe_ratio", label: "P/E Ratio" },
  { value: "pb_ratio", label: "P/B Ratio" },
  { value: "ps_ratio", label: "P/S Ratio" },
  { value: "roe", label: "ROE (%)" },
  { value: "roa", label: "ROA (%)" },
  { value: "debt_equity", label: "Debt/Equity" },
  { value: "dividend_yield", label: "Dividend Yield (%)" },
  { value: "rsi", label: "RSI" },
  { value: "mfi", label: "MFI" },
  { value: "bb_percent", label: "Bollinger %B" },
  { value: "graham_number", label: "Graham Number" },
  { value: "fifty_two_week_high", label: "52W High" },
  { value: "fifty_two_week_low", label: "52W Low" },
];

function formatMetric(metric: string): string {
  const found = ALERT_METRICS.find((m) => m.value === metric);
  return found ? found.label : metric;
}

function formatCondition(alert: AlertItem): string {
  return `${formatMetric(alert.metric)} ${alert.operator} ${alert.value}`;
}

export default function AlertsPage() {
  const { session, user, isLoading: authLoading } = useAuth();
  const token = session?.access_token;
  const queryClient = useQueryClient();

  const {
    data: alertsData,
    isLoading,
  } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.getAlerts(token!, { limit: 100 }),
    enabled: !!token,
  });

  const toggleMutation = useMutation({
    mutationFn: (alertId: string) => api.toggleAlert(token!, alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (alertId: string) => api.deleteAlert(token!, alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  // Not logged in
  if (!authLoading && !user) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <Bell className="mx-auto h-16 w-16 text-gray-300 dark:text-gray-600 mb-4" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Sign in to manage alerts
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Set up price and metric alerts for your favorite stocks
        </p>
      </div>
    );
  }

  // Loading
  if (authLoading || isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-8">
          <div className="h-9 w-32 bg-gray-200 dark:bg-slate-700 rounded animate-pulse" />
          <div className="h-5 w-24 bg-gray-200 dark:bg-slate-700 rounded animate-pulse mt-2" />
        </div>
        <SkeletonTable rows={5} columns={6} />
      </div>
    );
  }

  const items = alertsData?.items ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">My Alerts</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          {items.length} {items.length === 1 ? "alert" : "alerts"} configured
        </p>
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-12 text-center">
          <Bell className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            No alerts configured
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Go to a stock detail page and set up alerts for specific metrics
          </p>
          <Link
            href="/"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Browse Stocks
          </Link>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
            <thead className="bg-slate-800 dark:bg-slate-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Stock
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Condition
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase text-white">
                  Status
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase text-white">
                  Triggered
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-white">
                  Created
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase text-white">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-slate-700">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-slate-700">
                  <td className="px-4 py-4">
                    <Link
                      href={`/stocks/${item.ticker}?market=${item.market}`}
                      className="font-bold text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline"
                    >
                      {item.ticker}
                    </Link>
                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                      {item.name}
                    </p>
                  </td>
                  <td className="px-4 py-4">
                    <span className="font-mono text-sm text-gray-900 dark:text-white">
                      {formatCondition(item)}
                    </span>
                    {metricsGlossary[item.metric] && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-[300px] truncate">
                        {metricsGlossary[item.metric]}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4 text-center">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                        item.is_active
                          ? "bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300"
                          : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
                      }`}
                    >
                      {item.is_active ? "Active" : "Paused"}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-center">
                    <span className="text-gray-600 dark:text-gray-300">
                      {item.triggered_count}
                    </span>
                    {item.triggered_at && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Last: {new Date(item.triggered_at).toLocaleDateString()}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-gray-500 dark:text-gray-400">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => toggleMutation.mutate(item.id)}
                        disabled={toggleMutation.isPending}
                        className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-600 transition-colors"
                        title={item.is_active ? "Pause alert" : "Activate alert"}
                      >
                        {item.is_active ? (
                          <ToggleRight className="h-5 w-5 text-green-600 dark:text-green-400" />
                        ) : (
                          <ToggleLeft className="h-5 w-5 text-gray-400 dark:text-gray-500" />
                        )}
                      </button>
                      <button
                        onClick={() => {
                          if (confirm("Delete this alert?")) {
                            deleteMutation.mutate(item.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
                        title="Delete alert"
                      >
                        <Trash2 className="h-5 w-5 text-red-500 dark:text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Info section */}
      <div className="mt-8 rounded-lg border border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 p-6">
        <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
          How to create alerts
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Visit a stock&apos;s detail page and click the &quot;Add Alert&quot; button to set up notifications
          for specific metric conditions. Alerts will notify you when the condition is met.
        </p>
      </div>
    </div>
  );
}
