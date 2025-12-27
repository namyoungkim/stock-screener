"use client";

import { useState } from "react";
import { Bell, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, OperatorType } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { metricsGlossary } from "@/lib/glossary";

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

const OPERATORS: { value: OperatorType; label: string }[] = [
  { value: "<", label: "< (less than)" },
  { value: "<=", label: "<= (less or equal)" },
  { value: "=", label: "= (equal)" },
  { value: ">=", label: ">= (greater or equal)" },
  { value: ">", label: "> (greater than)" },
];

interface AlertFormProps {
  companyId: string;
  ticker: string;
  companyName: string;
}

export function AlertForm({ companyId, ticker, companyName }: AlertFormProps) {
  const { session, user } = useAuth();
  const queryClient = useQueryClient();
  const token = session?.access_token;

  const [isOpen, setIsOpen] = useState(false);
  const [metric, setMetric] = useState(ALERT_METRICS[0].value);
  const [operator, setOperator] = useState<OperatorType>("<=");
  const [value, setValue] = useState("");
  const [showTooltip, setShowTooltip] = useState(false);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createAlert(token!, {
        company_id: companyId,
        metric,
        operator,
        value: parseFloat(value),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setIsOpen(false);
      setValue("");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value || isNaN(parseFloat(value))) return;
    createMutation.mutate();
  };

  const handleOpenClick = () => {
    if (!user) {
      setShowTooltip(true);
      setTimeout(() => setShowTooltip(false), 2000);
      return;
    }
    setIsOpen(true);
  };

  return (
    <>
      {/* Button */}
      <div className="relative inline-block">
        <button
          onClick={handleOpenClick}
          className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-600 transition-colors"
        >
          <Bell className="h-4 w-4" />
          Add Alert
        </button>

        {showTooltip && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap z-50">
            Sign in to create alerts
          </div>
        )}
      </div>

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                Create Alert for {ticker}
              </h2>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              {companyName}
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Metric */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Metric
                </label>
                <select
                  value={metric}
                  onChange={(e) => setMetric(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {ALERT_METRICS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
                {metricsGlossary[metric] && (
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {metricsGlossary[metric]}
                  </p>
                )}
              </div>

              {/* Operator */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Condition
                </label>
                <select
                  value={operator}
                  onChange={(e) => setOperator(e.target.value as OperatorType)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {OPERATORS.map((op) => (
                    <option key={op.value} value={op.value}>
                      {op.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Value */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Value
                </label>
                <input
                  type="number"
                  step="any"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Enter threshold value"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              {/* Preview */}
              <div className="p-3 rounded-lg bg-gray-50 dark:bg-slate-700/50">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  Alert when{" "}
                  <span className="font-medium text-gray-900 dark:text-white">
                    {ALERT_METRICS.find((m) => m.value === metric)?.label}
                  </span>{" "}
                  is{" "}
                  <span className="font-mono font-medium text-blue-600 dark:text-blue-400">
                    {operator} {value || "?"}
                  </span>
                </p>
              </div>

              {/* Buttons */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!value || createMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createMutation.isPending ? "Creating..." : "Create Alert"}
                </button>
              </div>

              {createMutation.isError && (
                <p className="text-sm text-red-600 dark:text-red-400">
                  Failed to create alert. Please try again.
                </p>
              )}
            </form>
          </div>
        </div>
      )}
    </>
  );
}
