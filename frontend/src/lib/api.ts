/**
 * MarketPulse API Client
 */

const API_BASE_URL = import.meta.env.VITE_API_URL as string;
const TOKEN_KEY = "marketpulse_token";

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return response.json();
}

// ── Auth types ───────────────────────────────────────────────────────────────

export interface UserPreferences {
  monitored_stores: string[];
  interested_brands: string[];
  onboarding_completed: boolean;
  notification_channels: ("email" | "telegram")[];
  notification_threshold_percent: number;
  telegram_chat_id: string | null;
}

export interface TelegramConnectResponse {
  deep_link: string;
  expires_at: string;
}

export interface UserRead {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  preferences: UserPreferences | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: UserRead;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserPreferencesUpdate {
  monitored_stores?: string[];
  interested_brands?: string[];
  onboarding_completed?: boolean;
}

// ── Interfaces matching app/api/schemas.py ──────────────────────────────────

export interface ProductFeedItem {
  id: number;
  brand: string;
  title: string;
  currentPrice: number;
  previousPrice: number;
  changePercent: number;
  changeDirection: "up" | "down" | "none";
  storeInitial: string;
  storeName: string;
  storeColor: string;
  image_url: string | null;
}

export interface CatalogItem {
  id: number;
  sku: string;
  brand: string;
  name: string;
  volume: string;
  type: string;
  price: number;
  previousPrice: number;
  changePercent: number;
  changeDirection: "up" | "down" | "none";
  store: string;
  storeColor: string;
  in_stock: boolean;      // snake_case — matches FastAPI response
  lastUpdated: string;
}

export interface PriceHistoryRead {
  id: number;
  price: number;
  in_stock: boolean;
  parsed_at: string;
  change_type: string;
}

export interface ProductCardDetail {
  id: number;
  url: string;
  title: string;
  brand: string | null;
  volume: string | null;
  concentration: string | null;
  image_url: string | null;
  description: string | null;
  current_price: number;
  old_price: number | null;
  store_name: string;
  is_available: boolean;
  history: PriceHistoryRead[];
  competitors: ProductFeedItem[];
}

export interface DashboardStats {
  total_products: string;     // formatted "1,234"
  avg_price_change: string;   // formatted "+1.5%"
  stores_monitored: number;
  potential_savings: string;  // formatted "€123"
  alerts_triggered: number;
}

// ── Analytics types ─────────────────────────────────────────────────────────

export interface MoverItem {
  product_id: number;
  brand: string | null;
  title: string;
  image_url: string | null;
  store_name: string;
  current_price: number;
  start_price: number;
  change_abs: number;
  change_percent: number;
  direction: "up" | "down";
}

export interface SpreadItem {
  group_id: number;
  name: string;
  image_url: string | null;
  cheapest_product_id: number;
  cheapest_store: string;
  cheapest_price: number;
  most_expensive_store: string;
  most_expensive_price: number;
  spread_abs: number;
  spread_percent: number;
  store_count: number;
}

export interface RetailerStats {
  store: string;
  product_count: number;
  avg_price: number;
  drop_count: number;
  drop_rate: number;
  cheapest_wins: number;
  cheapest_win_rate: number;
}

export interface BrandStoreCell {
  brand: string;
  store: string;
  product_count: number;
  avg_price: number;
}

export interface VolatilityItem {
  product_id: number;
  brand: string | null;
  title: string;
  image_url: string | null;
  store_name: string;
  current_price: number;
  volatility_eur: number;
  range_eur: number;
  observation_count: number;
}

export interface MarketTrendPoint {
  date: string;            // ISO YYYY-MM-DD
  avg_price: number;
  observation_count: number;
}

export interface MoversDistributionBin {
  lower: number;
  upper: number;
  count: number;
  label: string;
}

export interface RetailerTrendPoint {
  date: string;
  avg_price: number;
}

export interface RetailerTrendSeries {
  store: string;
  points: RetailerTrendPoint[];
}

export interface FavoriteItem {
  id: number;            // favorite row id
  product_id: number;
  brand: string | null;
  title: string;
  volume: string | null;
  concentration: string | null;
  image_url: string | null;
  current_price: number;
  previous_price: number | null;
  price_when_added: number | null;
  change_percent: number;
  change_direction: "up" | "down" | "none";
  store_name: string;
  is_available: boolean;
  alert_enabled: boolean;
  created_at: string;
}

// ── Admin types ──────────────────────────────────────────────────────────────

export interface AdminSiteHealth {
  domain: string;
  site_name: string;
  last_scrape_at: string | null;
  product_count: number;
  health_score: number;
  success_count: number;
  failure_count: number;
  last_error: string | null;
}

export interface AdminHealthResponse {
  sites: AdminSiteHealth[];
  db_latency_ms: number;
  total_products: number;
  total_users: number;
}

export interface AdminScrapingRule {
  domain: string;
  site_name: string;
  container_css: string;
  title_css: string;
  price_css: string | null;
  image_css: string | null;
  brand_css: string | null;
  concentration_css: string | null;
  stock_css: string | null;
  next_page_css: string | null;
  health_score: number;
  success_count: number;
  failure_count: number;
  last_success: string | null;
  last_error: string | null;
}

export interface AdminDataQuality {
  total_products: number;
  products_without_image: number;
  products_without_history: number;
  products_ungrouped: number;
  total_price_events: number;
}

export interface AdminUserRead {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  favorites_count: number;
}

export interface AdminUserPatch {
  is_active?: boolean;
}

export interface AdminLogsResponse {
  lines: string[];
  total: number;
}

// ── Typed API methods ────────────────────────────────────────────────────────

export const api = {
  // Products (public)
  getFeed: (limit = 20) =>
    fetchApi<ProductFeedItem[]>(`/products/feed?limit=${limit}`),
  getCatalog: (params?: string) =>
    fetchApi<CatalogItem[]>(`/products/catalog${params ? `?${params}` : ""}`),
  getProduct: (id: number | string) =>
    fetchApi<ProductCardDetail>(`/products/${id}`),
  getStats: () =>
    fetchApi<DashboardStats>("/analytics/stats"),

  // Auth
  register: (body: UserCreate) =>
    fetchApi<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: LoginRequest) =>
    fetchApi<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () =>
    fetchApi<UserRead>("/auth/me"),
  deleteAccount: () =>
    fetchApi<void>("/auth/me", { method: "DELETE" }),
  updatePreferences: (body: UserPreferencesUpdate) =>
    fetchApi<UserPreferences>("/auth/preferences", { method: "PATCH", body: JSON.stringify(body) }),
  connectTelegram: () =>
    fetchApi<TelegramConnectResponse>("/auth/telegram/connect", { method: "POST" }),
  disconnectTelegram: () =>
    fetchApi<void>("/auth/telegram/disconnect", { method: "POST" }),

  // Analytics
  getMovers: (window: "24h" | "7d" | "30d" = "7d", limit = 20, direction: "both" | "up" | "down" = "both") =>
    fetchApi<MoverItem[]>(`/analytics/movers?window=${window}&limit=${limit}&direction=${direction}`),
  getSpreads: (limit = 20) =>
    fetchApi<SpreadItem[]>(`/analytics/spreads?limit=${limit}`),
  getRetailers: () =>
    fetchApi<RetailerStats[]>("/analytics/retailers"),
  getBrandStoreMatrix: (top_brands = 20, min_count = 1) =>
    fetchApi<BrandStoreCell[]>(`/analytics/brand-store-matrix?top_brands=${top_brands}&min_count=${min_count}`),
  getVolatility: (window: "24h" | "7d" | "30d" = "30d", limit = 20) =>
    fetchApi<VolatilityItem[]>(`/analytics/volatility?window=${window}&limit=${limit}`),
  getMarketTrend: (window: "7d" | "30d" | "90d" = "30d") =>
    fetchApi<MarketTrendPoint[]>(`/analytics/market-trend?window=${window}`),
  getMoversDistribution: (window: "24h" | "7d" | "30d" = "7d", bin_size = 5, bin_max = 30) =>
    fetchApi<MoversDistributionBin[]>(
      `/analytics/movers/distribution?window=${window}&bin_size=${bin_size}&bin_max=${bin_max}`
    ),
  getRetailersTrend: (window: "7d" | "30d" | "90d" = "30d") =>
    fetchApi<RetailerTrendSeries[]>(`/analytics/retailers/trend?window=${window}`),

  // Admin
  admin: {
    health: () =>
      fetchApi<AdminHealthResponse>("/admin/health"),
    rules: (domain: string) =>
      fetchApi<AdminScrapingRule>(`/admin/rules/${encodeURIComponent(domain)}`),
    regenerateRules: (domain: string) =>
      fetchApi<{ status: string; domain: string }>(`/admin/rules/${encodeURIComponent(domain)}/regenerate`, { method: "POST" }),
    triggerScrape: (domain: string) =>
      fetchApi<{ status: string; domain: string }>(`/admin/scrape/${encodeURIComponent(domain)}`, { method: "POST" }),
    dataQuality: () =>
      fetchApi<AdminDataQuality>("/admin/data-quality"),
    users: () =>
      fetchApi<AdminUserRead[]>("/admin/users"),
    updateUser: (userId: number, patch: AdminUserPatch) =>
      fetchApi<AdminUserRead>(`/admin/users/${userId}`, { method: "PATCH", body: JSON.stringify(patch) }),
    logs: (tail = 50) =>
      fetchApi<AdminLogsResponse>(`/admin/logs?tail=${tail}`),
  },

  // Favorites
  listFavorites: () =>
    fetchApi<FavoriteItem[]>("/favorites"),
  addFavorite: (product_id: number, alert_enabled = true) =>
    fetchApi<FavoriteItem>("/favorites", {
      method: "POST",
      body: JSON.stringify({ product_id, alert_enabled }),
    }),
  updateFavorite: (product_id: number, alert_enabled: boolean) =>
    fetchApi<FavoriteItem>(`/favorites/${product_id}`, {
      method: "PATCH",
      body: JSON.stringify({ alert_enabled }),
    }),
  removeFavorite: (product_id: number) =>
    fetch(`${API_BASE_URL}/favorites/${product_id}`, {
      method: "DELETE",
      headers: {
        ...(localStorage.getItem(TOKEN_KEY)
          ? { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` }
          : {}),
      },
    }).then((r) => {
      if (!r.ok && r.status !== 204) {
        throw new Error(`API Error: ${r.status} ${r.statusText}`);
      }
    }),
};
