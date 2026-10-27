/**
 * MarketPulse API client: types mirror app/api/schemas.py.
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
    let detail = "";
    try {
      const body = await response.clone().json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // body wasn't JSON — fall back to statusText
    }
    throw new Error(
      `API Error: ${response.status} ${detail || response.statusText}`
    );
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
  plan: "free" | "pro" | string;
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
  notification_channels?: ("email" | "telegram")[];
  notification_threshold_percent?: number;
}

// ── Catalogue (redesign) ─────────────────────────────────────────────────────

/** Daily lowest price per shop; every list has one value per day. */
export interface PriceSeries {
  days: string[];
  shops: Record<string, (number | null)[]>;
  cheapest: (string | null)[];
}

export interface CardOffer {
  product_id: number;
  store: string;
  store_name: string;
  title: string;
  price: number;
  old_price: number | null;
  promo_price: number | null;
  promo_code: string | null;
  url: string;
  in_stock: boolean;
  checked_at: string | null;
  change_30d: number | null;
}

/** One perfume in one size, with every shop that sells it. */
export interface CatalogCard {
  key: string;
  product_id: number;
  brand: string;
  name: string;
  concentration: string | null;
  volume: string | null;
  image_url: string | null;
  min_price: number;
  max_price: number;
  cheapest_store: string;
  shops: number;
  change_30d: number | null;
  has_promo: boolean;
  offers: CardOffer[];
}

export interface CardsPage {
  total: number;
  listings: number;
  items: CatalogCard[];
}

export interface ListingRow {
  product_id: number;
  brand: string;
  name: string;
  title: string;
  volume: string | null;
  concentration: string | null;
  image_url: string | null;
  price: number;
  old_price: number | null;
  promo_price: number | null;
  promo_code: string | null;
  change_30d: number | null;
  store: string;
  store_name: string;
  in_stock: boolean;
  url: string;
  checked_at: string | null;
}

export interface ListingsPage {
  total: number;
  items: ListingRow[];
}

export interface FacetValue {
  value: string;
  label: string;
  count: number;
}

export interface CatalogFacets {
  stores: FacetValue[];
  concentrations: FacetValue[];
  volumes: FacetValue[];
  brands: FacetValue[];
  price_min: number;
  price_max: number;
  as_of: string | null;
}

export type CardSort = "popular" | "shops" | "drop" | "low" | "high" | "gap" | "brand" | "new";
export type ListingSort = "popular" | "brand" | "name" | "price" | "change" | "shop";

export interface CatalogQuery {
  search?: string;
  brands?: string[];
  stores?: string[];
  volumes?: string[];
  types?: string[];
  price_min?: number | null;
  price_max?: number | null;
  in_stock?: boolean;
  promo?: boolean;
  multi_shop?: boolean;
  dropped?: boolean;
}

export interface MoveItem {
  product_id: number;
  store: string;
  store_name: string;
  brand: string;
  name: string;
  concentration: string | null;
  volume: string | null;
  image_url: string | null;
  old_price: number;
  new_price: number;
  change_percent: number;
  since: string | null;
}

// ── Market analytics (Pro) ───────────────────────────────────────────────────

export interface ShopSnapshot {
  store: string;
  store_name: string;
  products: number;
  current: number;
  changes_7d: number;
  changes_30d: number;
  cheapest_share: number;
  cheapest_count: number;
  promo_listings: number;
}

export interface MarketSnapshot {
  as_of: string | null;
  total_products: number;
  current_products: number;
  comparable: number;
  changes_7d: number;
  changes_30d: number;
  history_rows: number;
  history_since: string | null;
  spread_median: number;
  spread_mean: number;
  shops: ShopSnapshot[];
}

export interface ActivityPoint {
  date: string;
  store: string;
  up: number;
  down: number;
}

export interface PriceIndex {
  days: string[];
  shops: Record<string, (number | null)[]>;
  basket: Record<string, number>;
  estimated_from: string | null;
  estimated_to: string | null;
}

export interface BrandShopMatrix {
  brands: string[];
  stores: string[];
  cells: { brand: string; store: string; premium: number; bottles: number }[];
}

export interface DistributionBin {
  lower: number;
  upper: number;
  count: number;
}

export interface PriceBandRow {
  store: string;
  band: number;
  label: string;
  count: number;
}

export interface GapRow {
  card: CatalogCard;
  gap_percent: number;
  gap_eur: number;
  dearest_store: string;
}

export interface LandingData {
  market: MarketSnapshot;
  hero: CatalogCard | null;
  shelf: CatalogCard[];
  gaps: CatalogCard[];
  drops: MoveItem[];
}

// ── Product page ─────────────────────────────────────────────────────────────

export interface PriceHistoryRead {
  id: number;
  price: number;
  in_stock: boolean;
  parsed_at: string;
  change_type: string;
  store_name?: string;
}

export interface StoreOfferVariant {
  product_id: number;
  price: number;
  url: string;
  image_url: string | null;
  concentration?: string | null;
}

export interface StoreOffer {
  product_id: number;
  url: string;
  storeName: string;
  storeInitial: string;
  storeColor: string;
  price: number;
  previousPrice: number;
  changePercent: number;
  changeDirection: "up" | "down" | "none";
  image_url: string | null;
  concentration?: string | null;
  variants: StoreOfferVariant[];
  promoPrice?: number | null;
  promoCode?: string | null;
}

export interface SizeOption {
  product_id: number;
  volume: string;
  min_price: number;
  shops: number;
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
  promo_price?: number | null;
  promo_code?: string | null;
  history: PriceHistoryRead[];
  offers: StoreOffer[];
  display_name: string | null;
  sizes: SizeOption[];
  series: PriceSeries | null;
}

// ── Chat types ───────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
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
  alert_threshold_percent: number | null;
  created_at: string;
  display_name: string | null;
  offers: FavoriteOffer[];
  series: PriceSeries | null;
  change_30d: number | null;
}

export interface FavoriteOffer {
  product_id: number;
  store: string;
  store_name: string;
  price: number;
  old_price: number | null;
  url: string | null;
  is_available: boolean;
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
  plan: "free" | "pro" | string;
  created_at: string;
  favorites_count: number;
}

export interface AdminUserPatch {
  is_active?: boolean;
  plan?: "free" | "pro";
}

export interface AdminLogsResponse {
  lines: string[];
  total: number;
}

// ── Typed API methods ────────────────────────────────────────────────────────

function qs(params: object): string {
  const out = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => out.append(k, String(x)));
    else out.append(k, String(v));
  }
  const s = out.toString();
  return s ? `?${s}` : "";
}

export const api = {
  // Catalogue
  getCards: (q: CatalogQuery & { sort?: CardSort; skip?: number; limit?: number }) =>
    fetchApi<CardsPage>(`/products/cards${qs(q)}`),
  getListings: (q: CatalogQuery & { sort?: ListingSort; direction?: "asc" | "desc"; skip?: number; limit?: number }) =>
    fetchApi<ListingsPage>(`/products/listings${qs(q)}`),
  getFilters: () => fetchApi<CatalogFacets>("/products/filters"),
  getDrops: (q: { days?: number; stores?: string[]; brands?: string[]; limit?: number }) =>
    fetchApi<MoveItem[]>(`/products/drops${qs(q)}`),
  getProduct: (id: number | string) => fetchApi<ProductCardDetail>(`/products/${id}`),
  getLanding: () => fetchApi<LandingData>("/public/landing"),

  // Auth
  register: (body: UserCreate) =>
    fetchApi<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: LoginRequest) =>
    fetchApi<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => fetchApi<UserRead>("/auth/me"),
  deleteAccount: () => fetchApi<void>("/auth/me", { method: "DELETE" }),
  updatePreferences: (body: UserPreferencesUpdate) =>
    fetchApi<UserPreferences>("/auth/preferences", { method: "PATCH", body: JSON.stringify(body) }),
  changePassword: (current_password: string, new_password: string) =>
    fetchApi<void>("/auth/password", {
      method: "PATCH",
      body: JSON.stringify({ current_password, new_password }),
    }),
  updateProfile: (full_name: string) =>
    fetchApi<UserRead>("/auth/profile", { method: "PATCH", body: JSON.stringify({ full_name }) }),
  connectTelegram: () =>
    fetchApi<TelegramConnectResponse>("/auth/telegram/connect", { method: "POST" }),
  disconnectTelegram: () => fetchApi<void>("/auth/telegram/disconnect", { method: "POST" }),

  // Market analytics (Pro)
  analytics: {
    overview: () => fetchApi<MarketSnapshot>("/analytics/overview"),
    activity: (days = 30) => fetchApi<ActivityPoint[]>(`/analytics/activity?days=${days}`),
    priceIndex: (days = 30) => fetchApi<PriceIndex>(`/analytics/price-index?days=${days}`),
    moves: (days = 7, direction: "down" | "up" = "down", limit = 10) =>
      fetchApi<MoveItem[]>(`/analytics/moves?days=${days}&direction=${direction}&limit=${limit}`),
    gaps: (limit = 20, min_shops = 2) => fetchApi<GapRow[]>(`/analytics/gaps?limit=${limit}&min_shops=${min_shops}`),
    brandShop: (top = 12) => fetchApi<BrandShopMatrix>(`/analytics/brand-shop?top=${top}`),
    distribution: (days = 30) => fetchApi<DistributionBin[]>(`/analytics/distribution?days=${days}`),
    priceBands: () => fetchApi<PriceBandRow[]>("/analytics/price-bands"),
  },

  // Admin
  admin: {
    health: () => fetchApi<AdminHealthResponse>("/admin/health"),
    rules: (domain: string) => fetchApi<AdminScrapingRule>(`/admin/rules/${encodeURIComponent(domain)}`),
    regenerateRules: (domain: string) =>
      fetchApi<{ status: string; domain: string }>(`/admin/rules/${encodeURIComponent(domain)}/regenerate`, {
        method: "POST",
      }),
    triggerScrape: (domain: string, maxItems?: number | null) => {
      const q = maxItems != null ? `?max_items=${maxItems}` : "";
      return fetchApi<{ status: string; domain: string; job_id: string; max_items: number | null }>(
        `/admin/scrape/${encodeURIComponent(domain)}${q}`,
        { method: "POST" },
      );
    },
    deleteUser: (userId: number) => fetchApi<void>(`/admin/users/${userId}`, { method: "DELETE" }),
    batchDeactivate: (userIds: number[]) =>
      fetchApi<{ updated: number; skipped_self: number }>(`/admin/users/batch/deactivate`, {
        method: "POST",
        body: JSON.stringify({ user_ids: userIds }),
      }),
    dataQuality: () => fetchApi<AdminDataQuality>("/admin/data-quality"),
    users: () => fetchApi<AdminUserRead[]>("/admin/users"),
    updateUser: (userId: number, patch: AdminUserPatch) =>
      fetchApi<AdminUserRead>(`/admin/users/${userId}`, { method: "PATCH", body: JSON.stringify(patch) }),
    logs: (tail = 50) => fetchApi<AdminLogsResponse>(`/admin/logs?tail=${tail}`),
    workerStatus: () =>
      fetchApi<{ online: boolean; last_seen_ago_s: number | null; queue_depth: number }>("/admin/worker/status"),
  },

  // Chat
  sendChat: (message: string, history: ChatMessage[], page_context?: string) =>
    fetchApi<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, history, page_context }),
    }),

  // Favorites
  listFavorites: () => fetchApi<FavoriteItem[]>("/favorites"),
  addFavorite: (product_id: number, alert_enabled = true) =>
    fetchApi<FavoriteItem>("/favorites", {
      method: "POST",
      body: JSON.stringify({ product_id, alert_enabled }),
    }),
  updateFavorite: (product_id: number, patch: { alert_enabled?: boolean; alert_threshold_percent?: number }) =>
    fetchApi<FavoriteItem>(`/favorites/${product_id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  removeFavorite: (product_id: number) => fetchApi<void>(`/favorites/${product_id}`, { method: "DELETE" }),
};
