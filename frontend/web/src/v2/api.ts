import { retrieveRawInitData } from "@telegram-apps/sdk";
import type { ProductGroup, SearchRequest, SearchSnapshot, Watch, WatchInput, Notification, PriceHistory } from "./types";

const origin = (import.meta.env.VITE_API_URL as string | undefined) || window.location.origin;

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** Identity is derived by the server from signed Telegram data or its HttpOnly session. */
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let initData = "";
  try { initData = retrieveRawInitData() || ""; } catch { /* Regular authenticated web session. */ }
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (initData) headers.set("X-Telegram-Init-Data", initData);
  const response = await fetch(`${origin}${path}`, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    let detail = "";
    try { const payload = await response.json(); detail = typeof payload.detail === "string" ? payload.detail : ""; } catch { /* Do not expose an HTML proxy error. */ }
    throw new ApiError(response.status, response.status === 401 ? "Сессия завершена. Войдите снова." : detail || `Не удалось выполнить запрос (${response.status}). Попробуйте ещё раз.`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const json = (method: string, body?: unknown): RequestInit => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
const productPath = (id: string) => `/api/v2/products/${encodeURIComponent(id)}`;

export const api = {
  me: () => request<{ role: string; id?: number }>("/api/auth/me"),
  login: (password: string) => request("/api/auth/login", json("POST", { password })),
  recent: () => request<{ queries: string[]; products: ProductGroup[] }>("/api/v2/recent"),
  profile: () => request<{ region: string }>("/api/v2/profile"),
  saveProfile: (region: string) => request<{ region: string }>("/api/v2/profile", json("PATCH", { region })),
  search: (input: SearchRequest, signal: AbortSignal) => request<SearchSnapshot>("/api/v2/search", { ...json("POST", input), signal }),
  snapshot: (id: string, signal: AbortSignal) => request<SearchSnapshot>(`/api/v2/search/${encodeURIComponent(id)}`, { signal }),
  cancel: (id: string) => request(`/api/v2/search/${encodeURIComponent(id)}`, json("DELETE")),
  product: (id: string, signal?: AbortSignal) => request<ProductGroup>(productPath(id), { signal }),
  history: (id: string, days: string, signal: AbortSignal) => request<PriceHistory>(`${productPath(id)}/history?days=${days}`, { signal }),
  favorites: () => request<{ products: ProductGroup[] }>("/api/v2/favorites"),
  favorite: (id: string, remove: boolean) => request(remove ? `/api/v2/favorites/${encodeURIComponent(id)}` : "/api/v2/favorites", json(remove ? "DELETE" : "POST", remove ? undefined : { product_id: id })),
  watches: () => request<{ watches: Watch[] }>("/api/v2/watches"),
  createWatch: (input: WatchInput) => request<Watch>("/api/v2/watches", json("POST", input)),
  editWatch: (id: number, input: Partial<WatchInput> & { active?: boolean }) => {
    const { product_id, offer_id, mode, ...editable } = input;
    return request<Watch>(`/api/v2/watches/${id}`, json("PATCH", editable));
  },
  deleteWatch: (id: number) => request(`/api/v2/watches/${id}`, json("DELETE")),
  notifications: () => request<{ notifications: Notification[] }>("/api/v2/notifications"),
};
