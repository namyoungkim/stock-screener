"use client";

import { useState } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { api, MetricFilter, OperatorType } from "@/lib/api";
import { metricsGlossary } from "@/lib/glossary";

// Available metrics for filtering (same as FilterPanel)
const FILTER_METRICS = [
  { value: "pe_ratio", label: "P/E Ratio", category: "Valuation" },
  { value: "pb_ratio", label: "P/B Ratio", category: "Valuation" },
  { value: "ps_ratio", label: "P/S Ratio", category: "Valuation" },
  { value: "ev_ebitda", label: "EV/EBITDA", category: "Valuation" },
  { value: "peg_ratio", label: "PEG Ratio", category: "Valuation" },
  { value: "roe", label: "ROE", category: "Profitability" },
  { value: "roa", label: "ROA", category: "Profitability" },
  { value: "gross_margin", label: "Gross Margin", category: "Profitability" },
  { value: "net_margin", label: "Net Margin", category: "Profitability" },
  { value: "debt_equity", label: "Debt/Equity", category: "Financial Health" },
  { value: "current_ratio", label: "Current Ratio", category: "Financial Health" },
  { value: "dividend_yield", label: "Dividend Yield", category: "Dividend" },
  { value: "rsi", label: "RSI", category: "Technical" },
  { value: "mfi", label: "MFI", category: "Technical" },
  { value: "bb_percent", label: "Bollinger %B", category: "Technical" },
  { value: "macd", label: "MACD", category: "Technical" },
  { value: "graham_number", label: "Graham Number", category: "Value" },
  { value: "beta", label: "Beta", category: "Risk" },
  { value: "fifty_two_week_high", label: "52W High", category: "Price" },
  { value: "fifty_two_week_low", label: "52W Low", category: "Price" },
];

const OPERATORS: { value: OperatorType; label: string }[] = [
  { value: "<", label: "<" },
  { value: "<=", label: "<=" },
  { value: "=", label: "=" },
  { value: ">=", label: ">=" },
  { value: ">", label: ">" },
];

const METRIC_CATEGORIES = Array.from(
  new Set(FILTER_METRICS.map((m) => m.category))
);

interface PresetFormProps {
  token: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function PresetForm({ token, onClose, onSuccess }: PresetFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [filters, setFilters] = useState<MetricFilter[]>([]);
  const [pendingMetric, setPendingMetric] = useState(FILTER_METRICS[0].value);
  const [pendingOperator, setPendingOperator] = useState<OperatorType>("<=");
  const [pendingValue, setPendingValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createUserPreset(token, {
        name,
        description: description || undefined,
        filters,
      }),
    onSuccess: () => {
      onSuccess();
    },
    onError: (err: Error) => {
      if (err.message.includes("already exists")) {
        setError("A preset with this name already exists");
      } else {
        setError("Failed to create preset");
      }
    },
  });

  const handleAddFilter = () => {
    if (!pendingValue || isNaN(parseFloat(pendingValue))) return;

    const newFilter: MetricFilter = {
      metric: pendingMetric,
      operator: pendingOperator,
      value: parseFloat(pendingValue),
    };

    setFilters([...filters, newFilter]);
    setPendingValue("");
  };

  const handleRemoveFilter = (index: number) => {
    setFilters(filters.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Please enter a preset name");
      return;
    }

    if (filters.length === 0) {
      setError("Please add at least one filter");
      return;
    }

    createMutation.mutate();
  };

  const getMetricLabel = (metricValue: string) => {
    return FILTER_METRICS.find((m) => m.value === metricValue)?.label || metricValue;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-slate-800 px-6 py-4 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">
            Create New Preset
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Preset Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., My Value Strategy"
              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Current Filters */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Filters *
            </label>
            {filters.length > 0 ? (
              <div className="space-y-2 mb-4">
                {filters.map((filter, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600"
                  >
                    <span className="flex-1 text-sm text-gray-700 dark:text-gray-300">
                      <span className="font-medium">{getMetricLabel(filter.metric)}</span>
                      {" "}
                      <span className="text-blue-600 dark:text-blue-400 font-mono">
                        {filter.operator} {filter.value}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveFilter(index)}
                      className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                No filters added yet. Add at least one filter below.
              </p>
            )}

            {/* Add Filter */}
            <div className="p-3 rounded-lg bg-gray-50 dark:bg-slate-700/50 border border-gray-200 dark:border-slate-600">
              <div className="flex flex-wrap gap-2 mb-2">
                <select
                  value={pendingMetric}
                  onChange={(e) => setPendingMetric(e.target.value)}
                  className="flex-1 min-w-[120px] px-2 py-1.5 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                >
                  {METRIC_CATEGORIES.map((category) => (
                    <optgroup key={category} label={category}>
                      {FILTER_METRICS.filter((m) => m.category === category).map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>

                <select
                  value={pendingOperator}
                  onChange={(e) => setPendingOperator(e.target.value as OperatorType)}
                  className="w-16 px-2 py-1.5 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                >
                  {OPERATORS.map((op) => (
                    <option key={op.value} value={op.value}>
                      {op.label}
                    </option>
                  ))}
                </select>

                <input
                  type="number"
                  step="any"
                  value={pendingValue}
                  onChange={(e) => setPendingValue(e.target.value)}
                  placeholder="Value"
                  className="w-20 px-2 py-1.5 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-white placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500"
                />

                <button
                  type="button"
                  onClick={handleAddFilter}
                  disabled={!pendingValue}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>

              {metricsGlossary[pendingMetric] && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {metricsGlossary[pendingMetric]}
                </p>
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          {/* Buttons */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? "Creating..." : "Create Preset"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
