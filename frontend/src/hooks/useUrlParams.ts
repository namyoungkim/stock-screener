"use client";

import { useCallback, useMemo } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";

interface ScreenerParams {
  preset: string | null;
  market: string | null;
  search: string;
  page: number;
}

interface UseUrlParamsReturn {
  params: ScreenerParams;
  setPreset: (preset: string | null) => void;
  setMarket: (market: string | null) => void;
  setSearch: (search: string) => void;
  setPage: (page: number) => void;
  updateParams: (updates: Partial<ScreenerParams>) => void;
}

export function useUrlParams(): UseUrlParamsReturn {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  // Parse current params from URL
  const params = useMemo<ScreenerParams>(() => ({
    preset: searchParams.get("preset"),
    market: searchParams.get("market"),
    search: searchParams.get("search") || "",
    page: parseInt(searchParams.get("page") || "1", 10),
  }), [searchParams]);

  // Build new URL with updated params
  const buildUrl = useCallback((updates: Partial<ScreenerParams>): string => {
    const newParams = new URLSearchParams(searchParams.toString());

    // Helper to set or delete param
    const setParam = (key: string, value: string | number | null | undefined) => {
      if (value === null || value === undefined || value === "" || value === 1 && key === "page") {
        newParams.delete(key);
      } else {
        newParams.set(key, String(value));
      }
    };

    // Apply updates
    if ("preset" in updates) {
      setParam("preset", updates.preset);
      // Clear customPreset when setting a system preset
      if (updates.preset) {
        newParams.delete("customPreset");
      }
    }
    if ("market" in updates) setParam("market", updates.market);
    if ("search" in updates) setParam("search", updates.search);
    if ("page" in updates) setParam("page", updates.page);

    const queryString = newParams.toString();
    return queryString ? `${pathname}?${queryString}` : pathname;
  }, [searchParams, pathname]);

  // Update multiple params at once
  const updateParams = useCallback((updates: Partial<ScreenerParams>) => {
    const url = buildUrl(updates);
    router.push(url, { scroll: false });
  }, [buildUrl, router]);

  // Individual setters that reset page to 1
  const setPreset = useCallback((preset: string | null) => {
    updateParams({ preset, page: 1 });
  }, [updateParams]);

  const setMarket = useCallback((market: string | null) => {
    updateParams({ market, page: 1 });
  }, [updateParams]);

  const setSearch = useCallback((search: string) => {
    updateParams({ search, page: 1 });
  }, [updateParams]);

  const setPage = useCallback((page: number) => {
    updateParams({ page });
  }, [updateParams]);

  return {
    params,
    setPreset,
    setMarket,
    setSearch,
    setPage,
    updateParams,
  };
}
