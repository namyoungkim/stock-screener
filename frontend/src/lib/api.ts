const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Company {
  id: string;
  ticker: string;
  name: string;
  market: "US" | "KOSPI" | "KOSDAQ";
  sector?: string;
  industry?: string;
  currency: string;
}

export interface CompanyWithMetrics extends Company {
  latest_price?: number;
  market_cap?: number;
  metrics_date?: string;
  pe_ratio?: number;
  pb_ratio?: number;
  ps_ratio?: number;
  ev_ebitda?: number;
  roe?: number;
  roa?: number;
  gross_margin?: number;
  net_margin?: number;
  debt_equity?: number;
  current_ratio?: number;
  dividend_yield?: number;
  eps?: number;
  book_value_per_share?: number;
  graham_number?: number;
  fifty_two_week_high?: number;
  fifty_two_week_low?: number;
  beta?: number;
}

export interface MetricFilter {
  metric: string;
  operator: "<" | "<=" | "=" | ">=" | ">";
  value: number;
}

export interface ScreenRequest {
  filters?: MetricFilter[];
  preset?: string;
  market?: "US" | "KOSPI" | "KOSDAQ";
  limit?: number;
  offset?: number;
}

export interface ScreenResponse {
  total: number;
  stocks: CompanyWithMetrics[];
}

export interface PresetStrategy {
  id: string;
  name: string;
  description: string;
  filters: MetricFilter[];
}

export interface Metrics {
  company_id: string;
  date: string;
  pe_ratio?: number;
  pb_ratio?: number;
  ps_ratio?: number;
  ev_ebitda?: number;
  roe?: number;
  roa?: number;
  gross_margin?: number;
  net_margin?: number;
  debt_equity?: number;
  current_ratio?: number;
  dividend_yield?: number;
  eps?: number;
  book_value_per_share?: number;
  graham_number?: number;
  fifty_two_week_high?: number;
  fifty_two_week_low?: number;
  beta?: number;
}

export interface Price {
  company_id: string;
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  market_cap?: number;
}

export interface StockDetailResponse {
  company: Company;
  metrics?: Metrics;
  price?: Price;
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API Error: ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Stocks
  getStocks: (params?: {
    market?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.market) searchParams.set("market", params.market);
    if (params?.search) searchParams.set("search", params.search);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));

    const query = searchParams.toString();
    return fetchApi<ScreenResponse>(`/api/stocks${query ? `?${query}` : ""}`);
  },

  getStock: (ticker: string, market?: string) => {
    const params = market ? `?market=${market}` : "";
    return fetchApi<StockDetailResponse>(`/api/stocks/${ticker}${params}`);
  },

  // Screening
  screen: (request: ScreenRequest) =>
    fetchApi<ScreenResponse>("/api/screen", {
      method: "POST",
      body: JSON.stringify(request),
    }),

  getPresets: () => fetchApi<PresetStrategy[]>("/api/screen/presets"),

  getPreset: (id: string) => fetchApi<PresetStrategy>(`/api/screen/presets/${id}`),
};
