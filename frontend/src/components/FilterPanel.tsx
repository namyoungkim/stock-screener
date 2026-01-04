"use client";

import { useState, useRef, useEffect } from "react";
import { Search, Filter, X, Plus, Trash2 } from "lucide-react";
import { PresetStrategy, MetricFilter, OperatorType } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import { getPresetTooltip, metricsGlossary } from "@/lib/glossary";

// Available metrics for filtering (grouped by category)
const FILTER_METRICS = [
  // Valuation
  { value: "pe_ratio", label: "P/E Ratio", category: "Valuation" },
  { value: "pb_ratio", label: "P/B Ratio", category: "Valuation" },
  { value: "ps_ratio", label: "P/S Ratio", category: "Valuation" },
  { value: "ev_ebitda", label: "EV/EBITDA", category: "Valuation" },
  { value: "peg_ratio", label: "PEG Ratio", category: "Valuation" },
  // Profitability
  { value: "roe", label: "ROE", category: "Profitability" },
  { value: "roa", label: "ROA", category: "Profitability" },
  { value: "gross_margin", label: "Gross Margin", category: "Profitability" },
  { value: "net_margin", label: "Net Margin", category: "Profitability" },
  // Financial Health
  { value: "debt_equity", label: "Debt/Equity", category: "Financial Health" },
  { value: "current_ratio", label: "Current Ratio", category: "Financial Health" },
  // Dividend
  { value: "dividend_yield", label: "Dividend Yield", category: "Dividend" },
  // Technical
  { value: "rsi", label: "RSI", category: "Technical" },
  { value: "mfi", label: "MFI", category: "Technical" },
  { value: "bb_percent", label: "Bollinger %B", category: "Technical" },
  { value: "macd", label: "MACD", category: "Technical" },
  // Value
  { value: "graham_number", label: "Graham Number", category: "Value" },
  // Risk
  { value: "beta", label: "Beta", category: "Risk" },
  // Price
  { value: "fifty_two_week_high", label: "52W High", category: "Price" },
  { value: "fifty_two_week_low", label: "52W Low", category: "Price" },
  // Momentum / Trend
  { value: "price_to_52w_high_pct", label: "Price to 52W High %", category: "Momentum" },
  { value: "ma_trend", label: "MA Trend (50/200)", category: "Momentum" },
];

const OPERATORS: { value: OperatorType; label: string }[] = [
  { value: "<", label: "<" },
  { value: "<=", label: "<=" },
  { value: "=", label: "=" },
  { value: ">=", label: ">=" },
  { value: ">", label: ">" },
];

// Get unique categories
const METRIC_CATEGORIES = Array.from(
  new Set(FILTER_METRICS.map((m) => m.category))
);

interface FilterPanelProps {
  presets: PresetStrategy[];
  selectedPreset: string | null;
  selectedMarket: string | null;
  searchQuery: string;
  customFilters: MetricFilter[];
  onPresetChange: (preset: string | null) => void;
  onMarketChange: (market: string | null) => void;
  onSearchChange: (query: string) => void;
  onApplyFilters: (filters: MetricFilter[]) => void;
}

const markets = [
  { id: null, name: "All Markets" },
  { id: "US", name: "US" },
  { id: "KOSPI", name: "KOSPI" },
  { id: "KOSDAQ", name: "KOSDAQ" },
];

export function FilterPanel({
  presets,
  selectedPreset,
  selectedMarket,
  searchQuery,
  customFilters,
  onPresetChange,
  onMarketChange,
  onSearchChange,
  onApplyFilters,
}: FilterPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [localFilters, setLocalFilters] = useState<MetricFilter[]>([]);
  const [pendingMetric, setPendingMetric] = useState(FILTER_METRICS[0].value);
  const [pendingOperator, setPendingOperator] = useState<OperatorType>("<=");
  const [pendingValue, setPendingValue] = useState("");

  // Local state for search input to handle Korean IME properly
  const [localSearch, setLocalSearch] = useState(searchQuery);
  const isComposingRef = useRef(false);

  // Sync local search with parent when searchQuery changes externally
  useEffect(() => {
    if (!isComposingRef.current) {
      setLocalSearch(searchQuery);
    }
  }, [searchQuery]);

  // Sync local filters with applied filters when panel opens
  const handleToggleExpand = () => {
    if (!isExpanded) {
      setLocalFilters(customFilters);
    }
    setIsExpanded(!isExpanded);
  };

  const handleAddFilter = () => {
    if (!pendingValue || isNaN(parseFloat(pendingValue))) return;

    const newFilter: MetricFilter = {
      metric: pendingMetric,
      operator: pendingOperator,
      value: parseFloat(pendingValue),
    };

    setLocalFilters([...localFilters, newFilter]);
    setPendingValue("");
  };

  const handleRemoveFilter = (index: number) => {
    setLocalFilters(localFilters.filter((_, i) => i !== index));
  };

  const handleApply = () => {
    onApplyFilters(localFilters);
  };

  const handleClear = () => {
    setLocalFilters([]);
    onApplyFilters([]);
  };

  const getMetricLabel = (metricValue: string) => {
    return FILTER_METRICS.find((m) => m.value === metricValue)?.label || metricValue;
  };

  return (
    <div className="space-y-4 rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 dark:text-slate-400" />
        <input
          type="text"
          placeholder="Search by ticker or name..."
          value={localSearch}
          onChange={(e) => {
            const value = e.target.value;
            setLocalSearch(value);
            // Update parent immediately for non-IME input (English, etc.)
            if (!isComposingRef.current) {
              onSearchChange(value);
            }
          }}
          onCompositionStart={() => {
            isComposingRef.current = true;
          }}
          onCompositionEnd={(e) => {
            isComposingRef.current = false;
            // Update parent with final composed value (Korean, etc.)
            onSearchChange(e.currentTarget.value);
          }}
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 py-2 pl-10 pr-4 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Market Filter */}
      <div>
        <label className="mb-2 block text-sm font-semibold text-slate-800 dark:text-slate-200">
          Market
        </label>
        <div className="flex flex-wrap gap-2">
          {markets.map((market) => (
            <button
              key={market.id ?? "all"}
              onClick={() => onMarketChange(market.id)}
              className={cn(
                "rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
                selectedMarket === market.id
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"
              )}
            >
              {market.name}
            </button>
          ))}
        </div>
      </div>

      {/* Presets */}
      <div>
        <label className="mb-2 block text-sm font-semibold text-slate-800 dark:text-slate-200">
          Preset Strategies
        </label>
        <div className="flex flex-wrap gap-2">
          {selectedPreset && (
            <button
              onClick={() => onPresetChange(null)}
              className="flex items-center gap-1 rounded-full bg-red-100 dark:bg-red-900/50 px-3 py-1.5 text-sm font-medium text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/70"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
          {presets.map((preset) => {
            const tooltip = getPresetTooltip(preset.id) || preset.description;
            return (
              <Tooltip key={preset.id} content={tooltip || preset.name} position="bottom">
                <button
                  onClick={() => onPresetChange(preset.id)}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
                    selectedPreset === preset.id
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"
                  )}
                >
                  {preset.name}
                </button>
              </Tooltip>
            );
          })}
        </div>
      </div>

      {/* Advanced Filters Toggle */}
      <button
        onClick={handleToggleExpand}
        className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
      >
        <Filter className="h-4 w-4" />
        {isExpanded ? "Hide" : "Show"} Advanced Filters
        {customFilters.length > 0 && (
          <span className="px-1.5 py-0.5 text-xs font-medium bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded">
            {customFilters.length}
          </span>
        )}
      </button>

      {/* Advanced Filters */}
      {isExpanded && (
        <div className="space-y-4 rounded-lg bg-slate-50 dark:bg-slate-700 p-4 border border-slate-200 dark:border-slate-600">
          {/* Active Filters */}
          {localFilters.length > 0 && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Active Filters
              </label>
              <div className="space-y-2">
                {localFilters.map((filter, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 p-2 rounded-lg bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600"
                  >
                    <span className="flex-1 text-sm text-slate-700 dark:text-slate-300">
                      <span className="font-medium">{getMetricLabel(filter.metric)}</span>
                      {" "}
                      <span className="text-blue-600 dark:text-blue-400 font-mono">
                        {filter.operator} {filter.value}
                      </span>
                    </span>
                    <button
                      onClick={() => handleRemoveFilter(index)}
                      className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Add New Filter */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Add Filter
            </label>
            <div className="flex flex-wrap gap-2">
              {/* Metric Select */}
              <select
                value={pendingMetric}
                onChange={(e) => setPendingMetric(e.target.value)}
                className="flex-1 min-w-[140px] px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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

              {/* Operator Select */}
              <select
                value={pendingOperator}
                onChange={(e) => setPendingOperator(e.target.value as OperatorType)}
                className="w-20 px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {OPERATORS.map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>

              {/* Value Input */}
              <input
                type="number"
                step="any"
                value={pendingValue}
                onChange={(e) => setPendingValue(e.target.value)}
                placeholder="Value"
                className="w-24 px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />

              {/* Add Button */}
              <button
                onClick={handleAddFilter}
                disabled={!pendingValue}
                className="px-3 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>

            {/* Metric Description */}
            {metricsGlossary[pendingMetric] && (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {metricsGlossary[pendingMetric]}
              </p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex justify-between pt-2 border-t border-slate-200 dark:border-slate-600">
            <button
              onClick={handleClear}
              disabled={localFilters.length === 0 && customFilters.length === 0}
              className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-600 hover:bg-slate-200 dark:hover:bg-slate-500 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear All
            </button>
            <button
              onClick={handleApply}
              className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors"
            >
              Apply Filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
