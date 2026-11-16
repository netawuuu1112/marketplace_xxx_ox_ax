export type Match = "exact" | "probable" | "similar" | "rejected";
export type Sort = "relevance" | "price" | "total" | "delivery" | "rating";
export interface Offer {
  id: string; product_id: string; variant_id: string; source: string; native_id: string;
  title: string; seller: string; url: string; image_url: string | null;
  price: number | null; conditional_prices: { amount: number; condition: string }[];
  currency: string; rating: number | null; in_stock: boolean | null; condition: string;
  checked_at: string; region: string; match_status: Match;
  delivery: { price: number | null; date_min: string | null; date_max: string | null;
    region: string; checked_at: string | null; confidence: "unknown" | "reported" | "confirmed";
    conditions: string | string[] | null };
}
export interface ProductGroup {
  product: { id: string; title: string; brand: string; model: string; category: string; image_url: string | null };
  variant: { id: string; product_id: string; attributes: Record<string, unknown>; mpn: string | null; gtin: string | null; condition: string };
  offers: Offer[]; minimum_price: number | null; minimum_total: number | null;
  best_price_offer_id: string | null; best_total_offer_id: string | null; sources_count: number;
  match_status: Match; reasons: string[];
}
export interface SourceStatus {
  source: string; status: "pending" | "ok" | "partial" | "blocked" | "timeout" | "auth_required" | "rate_limited" | "parser_drift" | "unavailable";
  detail: string; offers_count: number; elapsed_ms: number; checked_at: string | null;
  region: string; supports_delivery: boolean; supports_monitoring: boolean;
}
export interface SearchSnapshot {
  search_id: string; query: string; normalized_query: string;
  status: "queued" | "running" | "complete" | "cancelled" | "failed";
  groups: ProductGroup[]; related: ProductGroup[]; sources: SourceStatus[];
  complete: boolean; error?: string; created_at: string;
}
export interface Filters { min_price?: number; max_price?: number; min_rating?: number; in_stock?: boolean; exact_only?: boolean; condition?: string; delivery_days?: number }
export interface SearchRequest { query: string; region: string; sources?: string[]; filters: Filters; sort: Sort }
export interface Rules { drop_amount?: number; drop_percent?: number; historical_low?: boolean; low_30?: boolean; low_90?: boolean; back_in_stock?: boolean; cheaper_source?: boolean }
export interface WatchInput {
  product_id: string; offer_id?: string; mode: "offer" | "minimum"; region: string; sources?: string[];
  threshold?: number | null; interval_minutes: number; rules: Rules; cooldown_minutes: number;
}
export interface Watch extends WatchInput {
  id: number; title: string; active: boolean; last_price: number | null;
  last_checked_at: string | null; last_error: string | null; state: "active" | "paused" | "needs_selection";
}
export interface Notification { id: number; title: string; body: string; created_at: string; read: boolean }
export interface PriceHistory { points: { captured_at: string; price: number; source: string; offer_id: string }[]; summary: { min: number | null; max: number | null; average: number | null } }
