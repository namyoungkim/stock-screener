"use client";

import { useState, useEffect, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { api, PresetStrategy, ScreenRequest, MetricFilter } from "@/lib/api";
import { StockTable } from "@/components/StockTable";
import { FilterPanel } from "@/components/FilterPanel";
import { Pagination } from "@/components/ui/Pagination";
import { useUrlParams } from "@/hooks/useUrlParams";
import { Filter } from "lucide-react";

const ITEMS_PER_PAGE = 50;

function HomeContent() {
  const searchParams = useSearchParams();
  const { params, setPreset, setMarket, setSearch, setPage } = useUrlParams();
  const [customFilters, setCustomFilters] = useState<MetricFilter[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  // Use URL params for state
  const selectedPreset = params.preset;
  const selectedMarket = params.market;
  const searchQuery = params.search;
  const currentPage = params.page;

  // Handle custom preset from sessionStorage
  useEffect(() => {
    const customPreset = searchParams.get("customPreset");

    if (customPreset === "true") {
      // User preset - load filters from sessionStorage
      const storedFilters = sessionStorage.getItem("customFilters");
      if (storedFilters) {
        try {
          const filters = JSON.parse(storedFilters) as MetricFilter[];
          setCustomFilters(filters);
          sessionStorage.removeItem("customFilters"); // Clean up after use
        } catch {
          console.error("Failed to parse custom filters from sessionStorage");
        }
      }
    }
  }, [searchParams]);

  // Fetch presets
  const { data: presets = [] } = useQuery<PresetStrategy[]>({
    queryKey: ["presets"],
    queryFn: api.getPresets,
  });

  const offset = (currentPage - 1) * ITEMS_PER_PAGE;

  // Build screen request
  const screenRequest: ScreenRequest = {
    preset: selectedPreset ?? undefined,
    market: selectedMarket as ScreenRequest["market"],
    filters: customFilters.length > 0 ? customFilters : undefined,
    search: searchQuery || undefined,
    limit: ITEMS_PER_PAGE,
    offset,
  };

  // Fetch stocks - use screen API if preset or custom filters selected
  const {
    data: stocksData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["stocks", selectedPreset, selectedMarket, searchQuery, currentPage, customFilters],
    queryFn: async () => {
      if (selectedPreset || customFilters.length > 0) {
        return api.screen(screenRequest);
      }
      return api.getStocks({
        market: selectedMarket ?? undefined,
        search: searchQuery || undefined,
        limit: ITEMS_PER_PAGE,
        offset,
      });
    },
  });

  // Reset page when filters change (using URL params)
  const handlePresetChange = (preset: string | null) => {
    setPreset(preset);
    if (preset) {
      setCustomFilters([]); // Clear custom filters when selecting preset
    }
  };

  const handleMarketChange = (market: string | null) => {
    setMarket(market);
  };

  const handleSearchChange = (search: string) => {
    setSearch(search);
  };

  const handleApplyFilters = (filters: MetricFilter[]) => {
    setCustomFilters(filters);
    setPreset(null); // Clear preset when applying custom filters
    setSearch(""); // Clear search when applying custom filters
  };

  const handlePageChange = (page: number) => {
    setPage(page);
  };

  const totalPages = Math.ceil((stocksData?.total ?? 0) / ITEMS_PER_PAGE);

  return (
    <div className="mx-auto max-w-screen-2xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Stock Screener</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Find undervalued stocks using proven value investing strategies
        </p>
      </div>

      {/* Mobile filter toggle button */}
      <div className="lg:hidden mb-4">
        <button
          type="button"
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg shadow-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
          aria-label={showFilters ? "Hide filters" : "Show filters"}
          aria-expanded={showFilters}
        >
          <Filter className="h-4 w-4" />
          {showFilters ? "Hide Filters" : "Show Filters"}
          {(selectedPreset || selectedMarket || searchQuery || customFilters.length > 0) && (
            <span className="ml-1 px-1.5 py-0.5 text-xs bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 rounded-full">
              Active
            </span>
          )}
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Filters */}
        <div className={`lg:col-span-1 ${showFilters ? "block" : "hidden lg:block"}`}>
          <FilterPanel
            presets={presets}
            selectedPreset={selectedPreset}
            selectedMarket={selectedMarket}
            searchQuery={searchQuery}
            customFilters={customFilters}
            onPresetChange={handlePresetChange}
            onMarketChange={handleMarketChange}
            onSearchChange={handleSearchChange}
            onApplyFilters={handleApplyFilters}
          />
        </div>

        {/* Results */}
        <div className="lg:col-span-4">
          <div className="rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm">
            <div className="border-b border-gray-200 dark:border-slate-700 px-4 py-3 bg-slate-50 dark:bg-slate-700">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-slate-900 dark:text-white">
                  {selectedPreset
                    ? `${presets.find((p) => p.id === selectedPreset)?.name} Results`
                    : customFilters.length > 0
                    ? "Filtered Results"
                    : "All Stocks"}
                </h2>
                <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                  {stocksData?.total ?? 0} stocks found
                </span>
              </div>
            </div>

            {error ? (
              <div className="p-8 text-center text-red-600 dark:text-red-400 font-medium">
                Error loading stocks. Make sure the API server is running.
              </div>
            ) : (
              <StockTable
                stocks={stocksData?.stocks ?? []}
                isLoading={isLoading}
              />
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="border-t border-gray-200 dark:border-slate-700 px-4 py-3 bg-slate-50 dark:bg-slate-700">
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-screen-2xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
        </div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  );
}
