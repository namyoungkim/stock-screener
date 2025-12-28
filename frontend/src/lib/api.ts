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
  fifty_day_average?: number;
  two_hundred_day_average?: number;
  peg_ratio?: number;
  rsi?: number;
  volume_change?: number;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  bb_percent?: number;
  mfi?: number;
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
  fifty_day_average?: number;
  two_hundred_day_average?: number;
  peg_ratio?: number;
  rsi?: number;
  volume_change?: number;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  bb_percent?: number;
  mfi?: number;
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

// Watchlist types
export interface WatchlistItem {
  id: string;
  user_id: string;
  company_id: string;
  added_at: string;
  notes?: string;
  target_price?: number;
  ticker?: string;
  name?: string;
  market?: string;
  latest_price?: number;
}

export interface WatchlistResponse {
  total: number;
  items: WatchlistItem[];
}

// Alert types
export type OperatorType = "<" | "<=" | "=" | ">=" | ">";

export interface AlertItem {
  id: string;
  user_id: string;
  company_id: string;
  metric: string;
  operator: OperatorType;
  value: number;
  is_active: boolean;
  triggered_at?: string;
  triggered_count: number;
  created_at: string;
  updated_at: string;
  ticker?: string;
  name?: string;
  market?: string;
  latest_price?: number;
}

export interface AlertResponse {
  total: number;
  items: AlertItem[];
}

export interface AlertCreateData {
  company_id: string;
  metric: string;
  operator: OperatorType;
  value: number;
}

export interface AlertUpdateData {
  metric?: string;
  operator?: OperatorType;
  value?: number;
  is_active?: boolean;
}

// User Preset types
export interface UserPreset {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  filters: MetricFilter[];
  created_at: string;
  updated_at: string;
}

export interface UserPresetResponse {
  total: number;
  items: UserPreset[];
}

export interface UserPresetCreateData {
  name: string;
  description?: string;
  filters: MetricFilter[];
}

export interface UserPresetUpdateData {
  name?: string;
  description?: string;
  filters?: MetricFilter[];
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit & { token?: string }
): Promise<T> {
  const { token, ...fetchOptions } = options || {};

  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions?.headers,
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

  // Watchlist (requires auth)
  getWatchlist: (token: string, params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return fetchApi<WatchlistResponse>(
      `/api/watchlist${query ? `?${query}` : ""}`,
      { token }
    );
  },

  addToWatchlist: (
    token: string,
    data: { company_id: string; notes?: string; target_price?: number }
  ) =>
    fetchApi<{ success: boolean; item: WatchlistItem }>("/api/watchlist", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  removeFromWatchlist: (token: string, companyId: string) =>
    fetchApi<{ success: boolean; message: string }>(
      `/api/watchlist/${companyId}`,
      { method: "DELETE", token }
    ),

  updateWatchlistItem: (
    token: string,
    companyId: string,
    data: { notes?: string; target_price?: number }
  ) =>
    fetchApi<{ success: boolean; item: WatchlistItem }>(
      `/api/watchlist/${companyId}`,
      { method: "PATCH", body: JSON.stringify(data), token }
    ),

  checkInWatchlist: (token: string, companyId: string) =>
    fetchApi<{ in_watchlist: boolean }>(
      `/api/watchlist/check/${companyId}`,
      { token }
    ),

  // Alerts (requires auth)
  getAlerts: (token: string, params?: { limit?: number; offset?: number; active_only?: boolean }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    if (params?.active_only) searchParams.set("active_only", String(params.active_only));
    const query = searchParams.toString();
    return fetchApi<AlertResponse>(
      `/api/alerts${query ? `?${query}` : ""}`,
      { token }
    );
  },

  createAlert: (token: string, data: AlertCreateData) =>
    fetchApi<{ success: boolean; item: AlertItem }>("/api/alerts", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  getAlert: (token: string, alertId: string) =>
    fetchApi<AlertItem>(`/api/alerts/${alertId}`, { token }),

  updateAlert: (token: string, alertId: string, data: AlertUpdateData) =>
    fetchApi<{ success: boolean; item: AlertItem }>(
      `/api/alerts/${alertId}`,
      { method: "PATCH", body: JSON.stringify(data), token }
    ),

  deleteAlert: (token: string, alertId: string) =>
    fetchApi<{ success: boolean; message: string }>(
      `/api/alerts/${alertId}`,
      { method: "DELETE", token }
    ),

  toggleAlert: (token: string, alertId: string) =>
    fetchApi<{ success: boolean; item: AlertItem }>(
      `/api/alerts/${alertId}/toggle`,
      { method: "POST", token }
    ),

  getAlertsForCompany: (token: string, companyId: string) =>
    fetchApi<AlertItem[]>(`/api/alerts/company/${companyId}`, { token }),

  // User Presets (requires auth)
  getUserPresets: (token: string, params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    const query = searchParams.toString();
    return fetchApi<UserPresetResponse>(
      `/api/user-presets${query ? `?${query}` : ""}`,
      { token }
    );
  },

  createUserPreset: (token: string, data: UserPresetCreateData) =>
    fetchApi<{ success: boolean; item: UserPreset }>("/api/user-presets", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  getUserPreset: (token: string, presetId: string) =>
    fetchApi<UserPreset>(`/api/user-presets/${presetId}`, { token }),

  updateUserPreset: (token: string, presetId: string, data: UserPresetUpdateData) =>
    fetchApi<{ success: boolean; item: UserPreset }>(
      `/api/user-presets/${presetId}`,
      { method: "PATCH", body: JSON.stringify(data), token }
    ),

  deleteUserPreset: (token: string, presetId: string) =>
    fetchApi<{ success: boolean; message: string }>(
      `/api/user-presets/${presetId}`,
      { method: "DELETE", token }
    ),
};
