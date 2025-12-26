"use client";

import { useState } from "react";
import { Search, Filter, X } from "lucide-react";
import { PresetStrategy, MetricFilter } from "@/lib/api";
import { cn } from "@/lib/utils";

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
  { id: "US", name: "US (S&P 500)" },
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
    <div className="space-y-4 rounded-lg border bg-white p-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search by ticker or name..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full rounded-lg border py-2 pl-10 pr-4 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Market Filter */}
      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Market
        </label>
        <div className="flex flex-wrap gap-2">
          {markets.map((market) => (
            <button
              key={market.id ?? "all"}
              onClick={() => onMarketChange(market.id)}
              className={cn(
                "rounded-full px-3 py-1 text-sm font-medium transition-colors",
                selectedMarket === market.id
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              {market.name}
            </button>
          ))}
        </div>
      </div>

      {/* Presets */}
      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Preset Strategies
        </label>
        <div className="flex flex-wrap gap-2">
          {selectedPreset && (
            <button
              onClick={() => onPresetChange(null)}
              className="flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-200"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
          {presets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => onPresetChange(preset.id)}
              className={cn(
                "rounded-full px-3 py-1 text-sm font-medium transition-colors",
                selectedPreset === preset.id
                  ? "bg-green-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
              title={preset.description}
            >
              {preset.name}
            </button>
          ))}
        </div>
      </div>

      {/* Advanced Filters Toggle */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <Filter className="h-4 w-4" />
        {isExpanded ? "Hide" : "Show"} Advanced Filters
      </button>

      {/* Advanced Filters */}
      {isExpanded && (
        <div className="rounded-lg bg-gray-50 p-4">
          <p className="text-sm text-gray-500">
            Advanced custom filters coming soon...
          </p>
        </div>
      )}
    </div>
  );
}
