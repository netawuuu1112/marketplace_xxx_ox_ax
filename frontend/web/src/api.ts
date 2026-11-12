import { retrieveLaunchParams, retrieveRawInitData } from "@telegram-apps/sdk";
import { DEMO_PRODUCTS, DEMO_REVIEWS } from "./data";
import type { BudgetInfo, CompareRow, Product, Review, SearchResult } from "./types";

export type MarketplaceOffer = {
  source: string;
  product_id: string;
  title: string;
  brand: string;
  seller: string;
  price_rub: number | null;
  price_with_subscription_rub: number | null;
  rating: number | null;
  rating_count: number | null;
  in_stock: boolean | null;
  url: string;
};

export type MarketplaceSearch = {
  query: string;
  sources_queried: string[];
  sources_ok: string[];
  complete: boolean;
  total_offers: number;
  cheapest_comparable: MarketplaceOffer | null;
  offers: MarketplaceOffer[];
  source_outcomes: { source: string; status: string; detail: string }[];
  warnings: string[];
};

export function searchMarketplaces(q: string): Promise<MarketplaceSearch> {
  return getJson<MarketplaceSearch>("/api/marketplaces/search", { q, ...authParams() });
}

export async function currentUser(): Promise<boolean> {
  try {
    await getJson("/api/auth/me", {});
    return true;
  } catch {
    return false;
  }
}

export async function myRole(): Promise<string> {
  return (await getJson<{ role: string }>("/api/auth/me", {})).role;
}

export type AiProvider = { name: string; base_url: string; model_id: string; enabled: boolean };
export type AiRoute = { kind: string; provider_name: string; model_id: string };
export type AdminUser = { id: number; role: string; created_at: string };
export type AuditEvent = { actor_id: number; action: string; subject: string; created_at: string };
export type AdminOverview = { users: number; active_watches: number; notifications: number; failed_watches: number };

async function adminRequest<T>(path: string, method: string, body?: unknown): Promise<T> {
  const url = new URL(`${API}${path}`);
  const { initData, userId } = launchInfo();
  if (userId) url.searchParams.set("user_id", userId);
  const response = await fetch(url.toString(), {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}),
      ...(initData ? { "X-Telegram-Init-Data": initData } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export async function getAiProviders(): Promise<AiProvider[]> {
  return (await adminRequest<{ providers: AiProvider[] }>("/api/admin/ai/providers", "GET")).providers;
}

export async function getAiRoutes(): Promise<AiRoute[]> {
  return (await adminRequest<{ routes: AiRoute[] }>("/api/admin/ai/routes", "GET")).routes;
}

export async function saveAiProvider(provider: AiProvider & { api_key?: string }): Promise<void> {
  await adminRequest("/api/admin/ai/providers", "PUT", provider);
}

export async function deleteAiProvider(name: string): Promise<void> {
  await adminRequest(`/api/admin/ai/providers/${encodeURIComponent(name)}`, "DELETE");
}

export async function saveAiRoute(route: AiRoute): Promise<void> {
  await adminRequest("/api/admin/ai/routes", "PUT", route);
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  return (await adminRequest<{ users: AdminUser[] }>("/api/admin/users", "GET")).users;
}

export async function setAdminUserRole(id: number, role: "user" | "admin"): Promise<void> {
  await adminRequest(`/api/admin/users/${id}/role`, "PUT", { role });
}

export async function getAuditEvents(): Promise<AuditEvent[]> {
  return (await adminRequest<{ events: AuditEvent[] }>("/api/admin/audit", "GET")).events;
}

export async function getAdminOverview(): Promise<AdminOverview> {
  return await adminRequest<AdminOverview>("/api/admin/overview", "GET");
}

export async function login(password: string): Promise<void> {
  const response = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ password }),
  });
  if (!response.ok) throw new Error(response.status === 401 ? "Неверный пароль" : `Ошибка входа: ${response.status}`);
}

export async function listFavorites(): Promise<Product[]> {
  const result = await getJson<{ products: Product[] }>("/api/favorites", authParams());
  return result.products;
}

export async function writeFavorite(product: Product, remove: boolean): Promise<void> {
  const { initData } = launchInfo();
  const url = new URL(`${API}/api/favorites`);
  const { user_id } = authParams();
  if (user_id) url.searchParams.set("user_id", user_id);
  const response = await fetch(url.toString(), {
    method: remove ? "DELETE" : "POST",
    headers: { "Content-Type": "application/json", ...(initData ? { "X-Telegram-Init-Data": initData } : {}) },
    body: JSON.stringify(product),
  });
  if (!response.ok) throw new Error(`Избранное: ${response.status}`);
}

export type Watch = {
  id: number; query: string; threshold_rub: number | null;
  interval_minutes: number; active: boolean; last_price_rub: number | null;
  last_checked_at: string | null; last_error: string | null;
};

export type PricePoint = { captured_at: string; price_rub: number; source: string; product_url: string };
export type Notification = { id: number; title: string; body: string; created_at: string; read: boolean };

export async function listWatches(): Promise<Watch[]> {
  return (await getJson<{ watches: Watch[] }>("/api/watches", authParams())).watches;
}

export async function watchHistory(id: number): Promise<PricePoint[]> {
  return (await getJson<{ history: PricePoint[] }>(`/api/watches/${id}/history`, authParams())).history;
}

export async function listNotifications(): Promise<Notification[]> {
  return (await getJson<{ notifications: Notification[] }>("/api/notifications", authParams())).notifications;
}

export async function createWatch(query: string, threshold: number | null, interval: number): Promise<Watch> {
  const { initData } = launchInfo();
  const url = new URL(`${API}/api/watches`);
  const { user_id } = authParams();
  if (user_id) url.searchParams.set("user_id", user_id);
  const response = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(initData ? { "X-Telegram-Init-Data": initData } : {}) },
    body: JSON.stringify({ query, threshold_rub: threshold, interval_minutes: interval }),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as Watch;
}

export async function removeWatch(id: number): Promise<void> {
  const { initData } = launchInfo();
  const url = new URL(`${API}/api/watches/${id}`);
  const { user_id } = authParams();
  if (user_id) url.searchParams.set("user_id", user_id);
  const response = await fetch(url.toString(), {
    method: "DELETE", headers: initData ? { "X-Telegram-Init-Data": initData } : {},
  });
  if (!response.ok) throw new Error(`Удаление: ${response.status}`);
}

// Реальный бэкенд подключается переменной VITE_API_URL при сборке:
//   VITE_API_URL=https://api.example.com npm run build
// Без неё Mini App работает в демо-режиме на встроенном каталоге
// (тот же набор товаров, что и Python-демо бота).
const API = (import.meta.env.VITE_API_URL as string | undefined) || window.location.origin;

const STOP = new Set(["для", "с", "на", "и", "в", "из", "по", "от", "не", "за", "или", "а", "но", "до", "как", "что"]);

function words(q: string): string[] {
  return q.toLowerCase().split(" ").filter((w) => w.length > 2 && !STOP.has(w));
}

function score(p: Product, q: string): number {
  const ws = words(q);
  const hay = `${p.title} ${p.traits.join(" ")}`.toLowerCase();
  return ws.filter((w) => hay.includes(w)).length;
}

// Telegram initData: сервер валидирует подпись HMAC-SHA256 и берёт user_id.
// В демо-режиме браузера initData невалиден — сервер (SHOPPER_API_ALLOW_ANON=1)
// возьмёт user_id из query.
function launchInfo(): { initData: string; userId: string } {
  try {
    const lp = retrieveLaunchParams();
    const userId = String(lp.tgWebAppData?.user?.id ?? "");
    return { initData: retrieveRawInitData() ?? "", userId };
  } catch {
    return { initData: "", userId: "1" };
  }
}

// Вне Telegram (браузерное демо, npm run dev) SDK может вернуть объект без
// user — подставляем демо-значение user_id; сервер (SHOPPER_API_ALLOW_ANON=1)
// примет его из query. В реальном Telegram initData валиден и user.id всегда
// есть — там fallback не срабатывает.

async function getJson<T>(path: string, params: Record<string, string>): Promise<T> {
  const url = new URL(`${API}${path}`);
  for (const [k, v] of Object.entries(params)) {
    if (v) url.searchParams.set(k, v);
  }
  const headers: Record<string, string> = {};
  const { initData } = launchInfo();
  if (initData) headers["X-Telegram-Init-Data"] = initData;
  const resp = await fetch(url.toString(), { headers });
  if (!resp.ok) throw new Error(`API ${resp.status}`);
  return (await resp.json()) as T;
}

function authParams(): Record<string, string> {
  const { userId } = launchInfo();
  return { user_id: userId || "1" };
}

export async function searchProducts(
  query: string,
  markets: string[],
): Promise<SearchResult> {
  if (API) {
    return getJson<SearchResult>("/api/search", {
      q: query,
      markets: markets.join(","),
      ...authParams(),
    });
  }
  await delay(350); // имитация «думающего» ассистента
  const pool = DEMO_PRODUCTS.filter((p) => markets.includes(p.marketplace));
  const ranked = pool
    .map((p) => ({ p, s: score(p, query) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, 5)
    .map((x) => x.p);
  const fallback = ranked.length ? ranked : pool.slice(0, 5);
  return {
    products: fallback,
    constraints: { query, must_have: [] },
    verdicts: {},
  };
}

export async function getReviews(product: Product): Promise<Review[]> {
  if (API) {
    return getJson<{ reviews: Review[] }>("/api/reviews", {
      marketplace: product.marketplace,
      ext_id: product.ext_id,
      ...authParams(),
    }).then((r) => r.reviews);
  }
  await delay(250);
  return DEMO_REVIEWS[`${product.marketplace}:${product.ext_id}`] ?? [];
}

export async function comparePrices(query: string): Promise<CompareRow[]> {
  if (API) {
    return getJson<{ rows: CompareRow[] }>("/api/compare", {
      q: query,
      ...authParams(),
    }).then((r) => r.rows);
  }
  await delay(300);
  const ozon = DEMO_PRODUCTS.filter((p) => p.marketplace === "ozon" && score(p, query) > 0);
  const yandex = DEMO_PRODUCTS.filter((p) => p.marketplace === "yandex");
  const rows: CompareRow[] = [];
  for (const o of ozon.slice(0, 3)) {
    const ym = yandex.find((y) => y.ean && y.ean === o.ean);
    if (!ym) continue;
    const cheaper = o.price < ym.price ? "ozon" : "yandex";
    const diff = Math.round((Math.abs(o.price - ym.price) / Math.max(o.price, ym.price)) * 100);
    rows.push({
      title: o.title,
      ozon: o.price,
      yandex: ym.price,
      ozon_url: o.url,
      yandex_url: ym.url,
      cheaper,
      diff_percent: diff,
    });
  }
  return rows;
}

export async function getBudget(): Promise<BudgetInfo> {
  if (API) {
    return getJson<BudgetInfo>("/api/budget", { ...authParams() });
  }
  return { used: 0, limit: 50, remaining: 50, profile: "quality" };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
