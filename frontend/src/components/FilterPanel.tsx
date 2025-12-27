"use client";

import { useState } from "react";
import { Search, Filter, X } from "lucide-react";
import { PresetStrategy, MetricFilter } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/Tooltip";
import { getPresetTooltip } from "@/lib/glossary";

interface FilterPanelProps {
  presets: PresetStrategy[];
  selectedPreset: string | null;
  selectedMarket: string | null;
  searchQuery: string;
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
  onPresetChange,
  onMarketChange,
  onSearchChange,
}: FilterPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="space-y-4 rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-sm">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 dark:text-slate-400" />
        <input
          type="text"
          placeholder="Search by ticker or name..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
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
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
      >
        <Filter className="h-4 w-4" />
        {isExpanded ? "Hide" : "Show"} Advanced Filters
      </button>

      {/* Advanced Filters */}
      {isExpanded && (
        <div className="rounded-lg bg-slate-50 dark:bg-slate-700 p-4 border border-slate-200 dark:border-slate-600">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Advanced custom filters coming soon...
          </p>
        </div>
      )}
    </div>
  );
}
