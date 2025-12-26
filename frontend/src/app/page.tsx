"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, PresetStrategy, ScreenRequest } from "@/lib/api";
import { StockTable } from "@/components/StockTable";
import { FilterPanel } from "@/components/FilterPanel";

export default function Home() {
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [selectedMarket, setSelectedMarket] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch presets
  const { data: presets = [] } = useQuery<PresetStrategy[]>({
    queryKey: ["presets"],
    queryFn: api.getPresets,
  });

  // Build screen request
  const screenRequest: ScreenRequest = {
    preset: selectedPreset ?? undefined,
    market: selectedMarket as ScreenRequest["market"],
    limit: 100,
  };

  // Fetch stocks - use screen API if preset selected, otherwise use stocks API
  const {
    data: stocksData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["stocks", selectedPreset, selectedMarket, searchQuery],
    queryFn: async () => {
      if (selectedPreset) {
        return api.screen(screenRequest);
      }
      return api.getStocks({
        market: selectedMarket ?? undefined,
        search: searchQuery || undefined,
        limit: 100,
      });
    },
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Stock Screener</h1>
        <p className="mt-2 text-slate-600">
          Find undervalued stocks using proven value investing strategies
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Filters */}
        <div className="lg:col-span-1">
          <FilterPanel
            presets={presets}
            selectedPreset={selectedPreset}
            selectedMarket={selectedMarket}
            searchQuery={searchQuery}
            onPresetChange={setSelectedPreset}
            onMarketChange={setSelectedMarket}
            onSearchChange={setSearchQuery}
            onApplyFilters={() => {}}
          />
        </div>

        {/* Results */}
        <div className="lg:col-span-3">
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-4 py-3 bg-slate-50">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-slate-900">
                  {selectedPreset
                    ? `${presets.find((p) => p.id === selectedPreset)?.name} Results`
                    : "All Stocks"}
                </h2>
                <span className="text-sm font-medium text-slate-600">
                  {stocksData?.total ?? 0} stocks found
                </span>
              </div>
            </div>

            {error ? (
              <div className="p-8 text-center text-red-600 font-medium">
                Error loading stocks. Make sure the API server is running.
              </div>
            ) : (
              <StockTable
                stocks={stocksData?.stocks ?? []}
                isLoading={isLoading}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
