import { useCallback, useEffect, useRef, useState } from "react";
import { comparePrices, createWatch, currentUser, deleteAiProvider, getAdminOverview, getAdminUsers, getAiProviders, getAiRoutes, getAuditEvents, getBudget, getReviews, listFavorites, listNotifications, listWatches, login, myRole, removeWatch, saveAiProvider, saveAiRoute, searchMarketplaces, searchProducts, setAdminUserRole, watchHistory, writeFavorite } from "./api";
import type { AdminOverview, AdminUser, AuditEvent, AiProvider, AiRoute, MarketplaceOffer, MarketplaceSearch, Notification, PricePoint, Watch } from "./api";
import type { BudgetInfo, CompareRow, Product, Review, SearchResult } from "./types";

const SUGGESTIONS = [
  "чёрная маска для сна с пространством для ресниц",
  "кроссовки белые",
  "маска для сна до 1200 рублей",
];

type Screen =
  | { name: "home" }
  | { name: "results"; query: string; result: SearchResult }
  | { name: "marketplaces"; result: MarketplaceSearch }
  | { name: "product"; product: Product }
  | { name: "reviews"; product: Product }
  | { name: "compare"; rows: CompareRow[]; query: string }
  | { name: "favorites" }
  | { name: "watches" }
  | { name: "notifications" }
  | { name: "admin_ai" }
  | { name: "admin_users" }
  | { name: "admin_overview" }
  | { name: "settings" };

function rub(n: number | null | undefined): string {
  if (!n || n <= 0) return "цена неизвестна";
  return n.toLocaleString("ru-RU") + " ₽";
}

function MarketBadge({ m }: { m: Product["marketplace"] }) {
  if (m === "ozon") return <span className="badge badge-ozon">🟢 Ozon</span>;
  if (m === "wb") return <span className="badge">🟣 Wildberries</span>;
  return <span className="badge badge-ym">🔵 Яндекс</span>;
}

function VerdictMark({ v }: { v: string }) {
  return <span>{v === "confirmed" ? "✅" : v === "rejected" ? "❌" : "⚠️"}</span>;
}

function Stars({ n }: { n: number }) {
  return <span className="stars">{"★".repeat(Math.round(n)) + "☆".repeat(5 - Math.round(n))}</span>;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [role, setRole] = useState("user");
  useEffect(() => { currentUser().then(setAuthenticated); }, []);
  useEffect(() => { if (authenticated) myRole().then(setRole).catch(() => {}); }, [authenticated]);
  const [screen, setScreen] = useState<Screen>({ name: "home" });
  const [favorites, setFavorites] = useState<Product[]>([]);
  useEffect(() => { if (authenticated) listFavorites().then(setFavorites).catch(() => {}); }, [authenticated]);

  const saveFav = (p: Product) => {
    const next = favorites.some((f) => f.ext_id === p.ext_id && f.marketplace === p.marketplace)
      ? favorites.filter((f) => !(f.ext_id === p.ext_id && f.marketplace === p.marketplace))
      : [...favorites, p];
    const remove = favorites.some((f) => f.ext_id === p.ext_id && f.marketplace === p.marketplace);
    writeFavorite(p, remove).then(() => setFavorites(next)).catch((error) => window.alert(String(error)));
  };

  const isFav = (p: Product) =>
    favorites.some((f) => f.ext_id === p.ext_id && f.marketplace === p.marketplace);

  const go = (s: Screen) => {
    setScreen(s);
    window.scrollTo(0, 0);
  };

  if (authenticated === null) return <div className="app"><main className="content">Проверяю вход…</main></div>;
  if (!authenticated) return <LoginScreen onLogin={() => setAuthenticated(true)} />;

  return (
    <div className="app">
      <Header screen={screen} onBack={() => go({ name: "home" })} />
      <main className="content">
        {screen.name === "home" && (
          <HomeScreen onOpen={(s) => go(s)} role={role} />
        )}
        {screen.name === "results" && (
          <ResultsScreen
            screen={screen}
            isFav={isFav}
            onFav={saveFav}
            onProduct={(p) => go({ name: "product", product: p })}
            onCompare={(q) => {
              comparePrices(q).then((rows) => go({ name: "compare", rows, query: q }));
            }}
            onReviews={(p) => go({ name: "reviews", product: p })}
          />
        )}
        {screen.name === "marketplaces" && <MarketplaceResults result={screen.result} isFav={isFav} onFav={saveFav} />}
        {screen.name === "product" && (
          <ProductScreen
            product={screen.product}
            favored={isFav(screen.product)}
            onFav={() => saveFav(screen.product)}
            onReviews={() => go({ name: "reviews", product: screen.product })}
            onCompare={(q) => {
              comparePrices(q).then((rows) => go({ name: "compare", rows, query: q }));
            }}
          />
        )}
        {screen.name === "reviews" && <ReviewsScreen product={screen.product} />}
        {screen.name === "compare" && (
          <CompareScreen rows={screen.rows} query={screen.query} onSearch={(q) => {
            comparePrices(q).then((rows) => go({ name: "compare", rows, query: q }));
          }} />
        )}
        {screen.name === "favorites" && (
          <FavoritesScreen items={favorites} onProduct={(p) => go({ name: "product", product: p })} />
        )}
        {screen.name === "watches" && <WatchesScreen />}
        {screen.name === "notifications" && <NotificationsScreen />}
        {screen.name === "admin_ai" && <AiAdminScreen />}
        {screen.name === "admin_users" && <UsersAdminScreen />}
        {screen.name === "admin_overview" && <AdminOverviewScreen />}
        {screen.name === "settings" && <SettingsScreen />}
      </main>
      <TabBar
        active={screen.name === "favorites" ? "favorites" : screen.name === "settings" ? "settings" : "home"}
        onTab={(t) => go(t === "favorites" ? { name: "favorites" } : t === "settings" ? { name: "settings" } : { name: "home" })}
      />
    </div>
  );
}

function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  return <div className="app"><header className="header"><h1>MarketFusion AI</h1></header>
    <main className="content"><h2>Вход в веб-панель</h2>
      <form className="search-box" onSubmit={(event) => {
        event.preventDefault();
        login(password).then(onLogin).catch((reason) => setError(String(reason)));
      }}>
        <input type="password" autoComplete="current-password" value={password}
          onChange={(event) => setPassword(event.target.value)} placeholder="Пароль администратора" />
        <button className="btn-primary" type="submit">Войти</button>
      </form>
      {error && <p className="error">{error}</p>}
    </main></div>;
}

// ─────────────────────────── Header ───────────────────────────────

function Header({ screen, onBack }: { screen: Screen; onBack: () => void }) {
  const titles: Record<string, string> = {
    home: "Умный Шоппер",
    results: "Результаты",
    marketplaces: "Маркетплейсы",
    product: "Товар",
    reviews: "Отзывы",
    compare: "Сравнение цен",
    favorites: "Избранное",
    watches: "Мониторинг",
    notifications: "Уведомления",
    admin_ai: "Настройки ИИ",
    admin_users: "Пользователи",
    admin_overview: "Сводка",
    settings: "Настройки",
  };
  const canBack = screen.name !== "home";
  return (
    <header className="header">
      {canBack && <button className="btn-ghost" onClick={onBack}>←</button>}
      <h1>{titles[screen.name]}</h1>
    </header>
  );
}

// ─────────────────────────── Home ─────────────────────────────────

function HomeScreen({ onOpen, role }: { onOpen: (s: Screen) => void; role: string }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<"idle" | "busy">("idle");
  const [error, setError] = useState("");
  const openedFromExtension = useRef(false);

  const run = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setState("busy");
    setError("");
    try {
      const result = await searchMarketplaces(q);
      onOpen({ name: "marketplaces", result });
    } catch (e) {
      setError(String(e));
    } finally {
      setState("idle");
    }
  }, [onOpen]);

  useEffect(() => {
    if (openedFromExtension.current) return;
    openedFromExtension.current = true;
    const fromExtension = new URLSearchParams(window.location.search).get("q");
    if (fromExtension) {
      setQuery(fromExtension);
      void run(fromExtension);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [run]);

  return (
    <div className="home">
      <div className="search-box">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run(query)}
          placeholder="Например: чёрная маска для сна…"
          autoFocus
        />
        <button className="btn-primary" onClick={() => run(query)} disabled={state === "busy"}>
          {state === "busy" ? "🔎 Ищу…" : "🔎 Найти"}
        </button>
      </div>
      <p className="hint">Поиск предложений по подключённым маркетплейсам. Статус каждого источника показан в результатах.</p>
      {error && <p className="error">{error}</p>}
      <div className="chips">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => { setQuery(s); run(s); }}>
            {s}
          </button>
        ))}
      </div>
      <div className="menu-cards">
        <MenuCard emoji="🤖" title="ИИ-поиск" desc="Поиск с анализом характеристик" onClick={() => {
          if (!query.trim()) { setError("Введите запрос для ИИ-поиска"); return; }
          setState("busy");
          searchProducts(query, ["ozon", "yandex"])
            .then((result) => onOpen({ name: "results", query, result }))
            .catch((error) => setError(String(error)))
            .finally(() => setState("idle"));
        }} />
        <MenuCard emoji="⚖️" title="Сравнить цены" desc="Ozon vs Яндекс Маркет" onClick={() => onOpen({ name: "compare", rows: [], query: "" })} />
        <MenuCard emoji="⭐" title="Избранное" desc="Сохранённые товары" onClick={() => onOpen({ name: "favorites" })} />
        <MenuCard emoji="📉" title="Мониторинг" desc="Проверки цен и история" onClick={() => onOpen({ name: "watches" })} />
        <MenuCard emoji="🔔" title="Уведомления" desc="Достигнутые пороги цен" onClick={() => onOpen({ name: "notifications" })} />
        {(role === "super_admin" || role === "admin") && <MenuCard emoji="📊" title="Сводка" desc="Пользователи и мониторинг" onClick={() => onOpen({ name: "admin_overview" })} />}
        {role === "super_admin" && <MenuCard emoji="🧠" title="Настройки ИИ" desc="Провайдеры и модели по задачам" onClick={() => onOpen({ name: "admin_ai" })} />}
        {role === "super_admin" && <MenuCard emoji="👥" title="Пользователи" desc="Роли и журнал действий" onClick={() => onOpen({ name: "admin_users" })} />}
        <MenuCard emoji="⚙️" title="Настройки" desc="Профиль и лимиты запросов" onClick={() => onOpen({ name: "settings" })} />
      </div>
    </div>
  );
}

function MenuCard({ emoji, title, desc, onClick }: { emoji: string; title: string; desc: string; onClick?: () => void }) {
  return (
    <button className="menu-card" onClick={onClick}>
      <span className="menu-emoji">{emoji}</span>
      <div>
        <b>{title}</b>
        <p>{desc}</p>
      </div>
    </button>
  );
}

function productFromOffer(offer: MarketplaceOffer): Product | null {
  const markets: Record<string, Product["marketplace"]> = {
    ozon: "ozon", yandex_market: "yandex", wildberries: "wb",
  };
  const marketplace = markets[offer.source];
  if (!marketplace || !offer.product_id || !offer.url || offer.price_rub == null || offer.price_rub <= 0) return null;
  return {
    marketplace, ext_id: offer.product_id,
    title: offer.title, price: Math.round(offer.price_rub), url: offer.url,
    rating: offer.rating, reviews_count: offer.rating_count ?? 0,
    brand: offer.brand, traits: [],
  };
}

function sourceStatus(source: string, status: string): string {
  const name = { ozon: "Ozon", yandex_market: "Яндекс Маркет", wildberries: "Wildberries" }[source] ?? source;
  if (status === "blocked") return `${name}: сейчас недоступен`;
  if (status === "timeout") return `${name}: не ответил вовремя`;
  return `${name}: поиск пока не выполнен`;
}

function MarketplaceResults({ result, isFav, onFav }: {
  result: MarketplaceSearch;
  isFav: (p: Product) => boolean;
  onFav: (p: Product) => void;
}) {
  return (
    <section className="results">
      <div className="results-head">
        <h2>«{result.query}»</h2>
        <p className="hint">
          Найдено {result.total_offers} предложений. Ответили {result.sources_ok.length} из {result.sources_queried.length} источников.
          {!result.complete && " Сравнение неполное."}
        </p>
      </div>
      {result.cheapest_comparable && (
        <p className="winner">Наиболее выгодное сопоставимое предложение: {result.cheapest_comparable.source}, {rub(result.cheapest_comparable.price_rub)}</p>
      )}
      {result.source_outcomes.filter((s) => s.status !== "ok").map((s) => (
        <p className="hint" key={s.source}>{sourceStatus(s.source, s.status)}</p>
      ))}
      {result.offers.map((offer, index) => {
        const product = productFromOffer(offer);
        return <article className="card" key={`${offer.source}:${offer.product_id}:${index}`}>
          <div className="card-head"><span className="badge">{offer.source}</span></div>
          <h3>{offer.title}</h3>
          <p className="price"><b>{rub(offer.price_rub)}</b></p>
          {offer.price_with_subscription_rub != null && (
            <p className="hint">По подписке: {rub(offer.price_with_subscription_rub)}</p>
          )}
          <p className="hint">
            {[offer.brand, offer.seller, offer.rating != null ? `⭐ ${offer.rating}` : "", offer.in_stock === null ? "Наличие неизвестно" : offer.in_stock ? "В наличии" : "Нет в наличии"].filter(Boolean).join(" · ")}
          </p>
          {offer.url && <a className="btn-outline" href={offer.url} target="_blank" rel="noreferrer">Открыть товар</a>}
          {product && <button className="btn-outline" onClick={() => onFav(product)}>
            {isFav(product) ? "⭐ Убрать из избранного" : "⭐ В избранное"}
          </button>}
        </article>;
      })}
      {result.offers.length === 0 && <p className="hint">Подтверждённых предложений по запросу нет.</p>}
    </section>
  );
}

// ─────────────────────────── Results ──────────────────────────────

function ResultsScreen({ screen, isFav, onFav, onProduct, onCompare, onReviews }: {
  screen: Extract<Screen, { name: "results" }>;
  isFav: (p: Product) => boolean;
  onFav: (p: Product) => void;
  onProduct: (p: Product) => void;
  onCompare: (q: string) => void;
  onReviews: (p: Product) => void;
}) {
  const { query, result } = screen;
  return (
    <div className="results">
      <div className="results-head">
        <h2>По запросу «{query}»</h2>
        {result.constraints.must_have.length > 0 && (
          <p className="hint">Требования: {result.constraints.must_have.join(" · ")}</p>
        )}
        <button className="btn-outline" onClick={() => onCompare(query)}>⚖️ Сравнить цены на обеих площадках</button>
      </div>
      {result.products.map((p) => (
        <ProductCard
          key={`${p.marketplace}:${p.ext_id}`}
          p={p}
          favored={isFav(p)}
          verdicts={result.verdicts[p.ext_id]}
          onFav={() => onFav(p)}
          onOpen={() => onProduct(p)}
          onReviews={() => onReviews(p)}
        />
      ))}
    </div>
  );
}

// ─────────────────────────── ProductCard ──────────────────────────

function ProductCard({ p, favored, verdicts, onFav, onOpen, onReviews }: {
  p: Product;
  favored: boolean;
  verdicts?: Array<{ requirement: string; verdict: string; mentions: number }>;
  onFav: () => void;
  onOpen: () => void;
  onReviews: () => void;
}) {
  const disc = p.old_price && p.old_price > p.price
    ? Math.round((1 - p.price / p.old_price) * 100)
    : null;
  return (
    <article className="card" onClick={onOpen}>
      <div className="card-head">
        <MarketBadge m={p.marketplace} />
        <span className="rating">⭐ {p.rating ?? "—"} · {p.reviews_count} отз.</span>
      </div>
      <h3>{p.title}</h3>
      <p className="price">
        <b>{rub(p.price)}</b>
        {p.old_price && <s> {rub(p.old_price)}</s>}
        {disc && <span className="discount"> −{disc}%</span>}
      </p>
      {p.traits.length > 0 && <p className="traits">🏷 {p.traits.join(" · ")}</p>}
      {verdicts && verdicts.length > 0 && (
        <p className="verdicts">
          {verdicts.map((v) => (
            <span key={v.requirement}><VerdictMark v={v.verdict} /> {v.requirement}</span>
          ))}
        </p>
      )}
      <div className="card-actions" onClick={(e) => e.stopPropagation()}>
        <button className="btn-outline" onClick={onReviews}>📝 Отзывы ({p.reviews_count})</button>
        <button className="btn-outline" onClick={onFav}>{favored ? "⭐ Убрать" : "⭐ В избранное"}</button>
      </div>
    </article>
  );
}

// ─────────────────────────── Product ──────────────────────────────

function ProductScreen({ product: p, favored, onFav, onReviews, onCompare }: {
  product: Product;
  favored: boolean;
  onFav: () => void;
  onReviews: () => void;
  onCompare: (q: string) => void;
}) {
  return (
    <div className="product">
      <MarketBadge m={p.marketplace} />
      <h2>{p.title}</h2>
      <p className="price big"><b>{rub(p.price)}</b>
        {p.old_price && <s> {rub(p.old_price)}</s>}
      </p>
      <p className="hint">⭐ {p.rating ?? "—"} · {p.reviews_count} отзывов{p.ean ? ` · EAN ${p.ean}` : ""}</p>
      {p.traits.length > 0 && <p className="traits">🏷 {p.traits.join(" · ")}</p>}
      <div className="action-stack">
        <button className="btn-primary" onClick={onReviews}>📝 Отзывы ({p.reviews_count})</button>
        <button className="btn-outline" onClick={() => onCompare(p.title)}>⚖️ Сравнить цены</button>
        <button className="btn-outline" onClick={onFav}>{favored ? "⭐ Убрать из избранного" : "⭐ В избранное"}</button>
        <a className="btn-outline" href={p.url} target="_blank" rel="noreferrer">🛒 Открыть на маркетплейсе</a>
      </div>
    </div>
  );
}

// ─────────────────────────── Reviews ──────────────────────────────

function ReviewsScreen({ product: p }: { product: Product }) {
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [open, setOpen] = useState<Review | null>(null);

  useEffect(() => {
    getReviews(p).then(setReviews);
  }, [p]);

  return (
    <div className="reviews">
      <h2>{p.title}</h2>
      {!reviews && <p className="hint">Читаю отзывы…</p>}
      {reviews?.length === 0 && <p className="hint">Отзывов пока нет.</p>}
      <div className="review-list">
        {reviews?.map((r) => (
          <button key={r.id} className="review-item" onClick={() => setOpen(r)}>
            <div className="review-meta">
              <Stars n={r.rating} /> <b>{r.rating}/5</b> · {r.author} · {r.date}
              {r.bought_here && <span className="bought">🛒 куплен здесь</span>}
            </div>
            <p>{r.text}</p>
          </button>
        ))}
      </div>
      {open && (
        <div className="sheet" onClick={() => setOpen(null)}>
          <div className="sheet-card" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-head">
              <Stars n={open.rating} /> <b>{open.rating}/5</b>
              <button className="btn-ghost" onClick={() => setOpen(null)}>✕</button>
            </div>
            <p className="hint">{open.author} · {open.date}{open.bought_here ? " · куплен на маркетплейсе" : ""}</p>
            <p>{open.text}</p>
            {open.pros && <p className="pros">👍 {open.pros}</p>}
            {open.cons && <p className="cons">👎 {open.cons}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────── Compare ──────────────────────────────

function CompareScreen({ rows, query, onSearch }: {
  rows: CompareRow[];
  query: string;
  onSearch: (q: string) => void;
}) {
  const [q, setQ] = useState(query);
  const [busy, setBusy] = useState(false);
  return (
    <div className="compare">
      <div className="search-box">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Что сравнить?" />
        <button className="btn-primary" disabled={busy} onClick={async () => { setBusy(true); await onSearch(q); setBusy(false); }}>
          {busy ? "…" : "⚖️"}
        </button>
      </div>
      {rows.length === 0 && <p className="hint">Введите название товара — сравним цены на Ozon и Яндекс Маркете.</p>}
      {rows.map((r, i) => (
        <article className="card" key={i}>
          <h3>{r.title}</h3>
          <div className="compare-row">
            <span>🟢 Ozon: <b>{rub(r.ozon)}</b></span>
            <span>🔵 Яндекс: <b>{rub(r.yandex)}</b></span>
          </div>
          {r.cheaper && r.diff_percent ? (
            <p className="winner">🏆 Выгоднее {r.cheaper === "ozon" ? "на Ozon" : "на Яндекс Маркете"} на {r.diff_percent}%</p>
          ) : (
            <p className="hint">Цены совпадают</p>
          )}
          <div className="card-actions">
            <a className="btn-outline" href={r.ozon_url} target="_blank" rel="noreferrer">🛒 Ozon</a>
            <a className="btn-outline" href={r.yandex_url} target="_blank" rel="noreferrer">🛒 Яндекс</a>
          </div>
        </article>
      ))}
    </div>
  );
}

// ─────────────────────────── Favorites ────────────────────────────

function FavoritesScreen({ items, onProduct }: { items: Product[]; onProduct: (p: Product) => void }) {
  if (items.length === 0) return <p className="hint">Избранное пусто. Добавляйте ⭐ на карточках товаров.</p>;
  return (
    <div className="results">
      {items.map((p) => (
        <article className="card" key={`${p.marketplace}:${p.ext_id}`} onClick={() => onProduct(p)}>
          <div className="card-head"><MarketBadge m={p.marketplace} /></div>
          <h3>{p.title}</h3>
          <p className="price"><b>{rub(p.price)}</b></p>
        </article>
      ))}
    </div>
  );
}

function WatchesScreen() {
  const [items, setItems] = useState<Watch[]>([]);
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState("");
  const [interval, setInterval] = useState(60);
  const [history, setHistory] = useState<PricePoint[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { listWatches().then(setItems).catch((e) => setError(String(e))); }, []);
  return <div className="settings">
    <h2>Отслеживание цен</h2>
    <form className="card" onSubmit={(event) => {
      event.preventDefault(); setError("");
      createWatch(query, threshold ? Number(threshold) : null, interval)
        .then((watch) => { setItems([watch, ...items]); setQuery(""); setThreshold(""); })
        .catch((e) => setError(String(e)));
    }}>
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название товара" required minLength={2} />
      <input value={threshold} onChange={(event) => setThreshold(event.target.value)} type="number" min="1" step="0.01" placeholder="Порог цены, ₽ (необязательно)" />
      <select value={interval} onChange={(event) => setInterval(Number(event.target.value))}>
        {[15, 30, 60, 180, 360, 720, 1440].map((minutes) => <option key={minutes} value={minutes}>Каждые {minutes} мин</option>)}
      </select>
      <button className="btn-primary" type="submit">Добавить</button>
    </form>
    {error && <p className="error">{error}</p>}
    {items.map((watch) => <article className="card" key={watch.id}>
      <h3>{watch.query}</h3>
      <p className="price">{rub(watch.last_price_rub)}</p>
      <p className="hint">Порог: {rub(watch.threshold_rub)} · Интервал: {watch.interval_minutes} мин</p>
      <p className="hint">Последняя проверка: {watch.last_checked_at ? new Date(watch.last_checked_at).toLocaleString("ru-RU") : "ещё не выполнялась"}</p>
      {watch.last_error && <p className="error">{watch.last_error}</p>}
      <div className="card-actions">
        <button className="btn-outline" onClick={() => {
          watchHistory(watch.id).then((rows) => { setSelected(watch.id); setHistory(rows); }).catch((e) => setError(String(e)));
        }}>История</button>
        <button className="btn-outline" onClick={() => {
          removeWatch(watch.id).then(() => setItems(items.filter((item) => item.id !== watch.id))).catch((e) => setError(String(e)));
        }}>Удалить</button>
      </div>
    </article>)}
    {selected !== null && <section className="card"><h3>История цены</h3>
      {history.length === 0 && <p className="hint">Замеров пока нет.</p>}
      {history.length > 0 && <PriceHistorySummary points={history} />}
      {history.map((point) => <p key={`${point.captured_at}:${point.source}`}>
        {new Date(point.captured_at).toLocaleString("ru-RU")} · {point.source} · {rub(point.price_rub)}
      </p>)}
    </section>}
  </div>;
}

function PriceHistorySummary({ points }: { points: PricePoint[] }) {
  const chronological = [...points].reverse();
  const prices = chronological.map((point) => point.price_rub);
  const lowest = Math.min(...prices);
  const highest = Math.max(...prices);
  const average = prices.reduce((sum, price) => sum + price, 0) / prices.length;
  const first = prices[0];
  const last = prices[prices.length - 1];
  const change = first > 0 ? ((last - first) / first) * 100 : 0;
  const coordinates = prices.map((price, index) => {
    const x = 8 + (prices.length === 1 ? 0 : index * 304 / (prices.length - 1));
    const y = 100 - (price - lowest) * 84 / (highest - lowest || 1);
    return `${x},${y}`;
  }).join(" ");
  return <div>
    <p className="hint">Минимум: {rub(lowest)} · Средняя: {rub(Math.round(average))} · Изменение: {change.toFixed(1)}%</p>
    {points.length > 1 && <svg viewBox="0 0 320 108" role="img" aria-label="График изменения цены" style={{ width: "100%", maxHeight: 170 }}>
      <line x1="8" y1="100" x2="312" y2="100" stroke="currentColor" opacity="0.3" />
      <polyline points={coordinates} fill="none" stroke="#2783de" strokeWidth="2.5" strokeLinejoin="round" />
    </svg>}
  </div>;
}

function NotificationsScreen() {
  const [items, setItems] = useState<Notification[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { listNotifications().then(setItems).catch((e) => setError(String(e))); }, []);
  return <div className="settings"><h2>Уведомления</h2>
    {error && <p className="error">{error}</p>}
    {items.length === 0 && <p className="hint">Пока нет уведомлений.</p>}
    {items.map((item) => <article className="card" key={item.id}>
      <h3>{item.title}</h3><p>{item.body}</p>
      <p className="hint">{new Date(item.created_at).toLocaleString("ru-RU")}</p>
    </article>)}
  </div>;
}

const AI_BASE_URLS: Record<string, string> = {
  aitunnel: "https://api.aitunnel.ru/v1",
  openai: "https://api.openai.com/v1",
  qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  deepseek: "https://api.deepseek.com",
  kimi: "",
};

const AI_TASKS = ["constraints", "review", "rank", "arbiter", "freeform", "vision"];

function AiAdminScreen() {
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [routes, setRoutes] = useState<AiRoute[]>([]);
  const [name, setName] = useState("aitunnel");
  const [customName, setCustomName] = useState("");
  const [baseUrl, setBaseUrl] = useState(AI_BASE_URLS.aitunnel);
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [providerEnabled, setProviderEnabled] = useState(true);
  const [kind, setKind] = useState("constraints");
  const [routeProvider, setRouteProvider] = useState("");
  const [routeModel, setRouteModel] = useState("");
  const [error, setError] = useState("");
  const reload = () => Promise.all([getAiProviders(), getAiRoutes()])
    .then(([nextProviders, nextRoutes]) => { setProviders(nextProviders); setRoutes(nextRoutes); })
    .catch((reason) => setError(String(reason)));
  useEffect(() => { void reload(); }, []);
  return <div className="settings">
    <h2>Провайдеры ИИ</h2>
    <p className="hint">API-ключ сохраняется зашифрованным на сервере и не показывается после сохранения.</p>
    <form className="card" onSubmit={(event) => {
      event.preventDefault(); setError("");
      saveAiProvider({ name: name === "custom" ? customName : name,
        base_url: baseUrl, model_id: modelId, enabled: providerEnabled, api_key: apiKey || undefined })
        .then(() => { setApiKey(""); void reload(); }).catch((reason) => setError(String(reason)));
    }}>
      <select value={name} onChange={(event) => {
        const next = event.target.value; setName(next); setBaseUrl(AI_BASE_URLS[next] || "");
      }}>
        {Object.keys(AI_BASE_URLS).map((provider) => <option key={provider} value={provider}>{provider}</option>)}
        <option value="custom">custom</option>
      </select>
      {name === "custom" && <input value={customName} onChange={(event) => setCustomName(event.target.value)} placeholder="Имя провайдера" required />}
      <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="HTTPS Base URL" required />
      <input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="Model ID" required />
      <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" autoComplete="off" placeholder="API Key (для нового провайдера)" />
      <label><input type="checkbox" checked={providerEnabled} onChange={(event) => setProviderEnabled(event.target.checked)} /> Включён</label>
      <button className="btn-primary" type="submit">Сохранить провайдера</button>
    </form>
    {error && <p className="error">{error}</p>}
    {providers.map((provider) => <article className="card" key={provider.name}>
      <h3>{provider.name}</h3>
      <p className="hint">{provider.base_url} · {provider.model_id} · {provider.enabled ? "включён" : "отключён"}</p>
      <div className="card-actions">
        <button className="btn-outline" onClick={() => {
          if (provider.name in AI_BASE_URLS) setName(provider.name);
          else { setName("custom"); setCustomName(provider.name); }
          setBaseUrl(provider.base_url); setModelId(provider.model_id); setApiKey("");
          setProviderEnabled(provider.enabled);
        }}>Изменить</button>
        <button className="btn-outline" onClick={() => {
          deleteAiProvider(provider.name).then(() => void reload()).catch((reason) => setError(String(reason)));
        }}>Удалить</button>
      </div>
    </article>)}
    <h2>Маршрутизация задач</h2>
    <form className="card" onSubmit={(event) => {
      event.preventDefault(); setError("");
      saveAiRoute({ kind, provider_name: routeProvider, model_id: routeModel })
        .then(() => void reload()).catch((reason) => setError(String(reason)));
    }}>
      <select value={kind} onChange={(event) => setKind(event.target.value)}>
        {AI_TASKS.map((task) => <option key={task} value={task}>{task}</option>)}
      </select>
      <select value={routeProvider} onChange={(event) => {
        setRouteProvider(event.target.value);
        setRouteModel(providers.find((provider) => provider.name === event.target.value)?.model_id || "");
      }} required>
        <option value="">Выберите провайдера</option>
        {providers.filter((provider) => provider.enabled).map((provider) => <option key={provider.name} value={provider.name}>{provider.name}</option>)}
      </select>
      <input value={routeModel} onChange={(event) => setRouteModel(event.target.value)} placeholder="Model ID для задачи" required />
      <button className="btn-primary" type="submit">Назначить</button>
    </form>
    {routes.map((route) => <p className="card" key={route.kind}>
      {route.kind}: {route.provider_name} / {route.model_id}
    </p>)}
  </div>;
}

// ─────────────────────────── Settings ─────────────────────────────

function AdminOverviewScreen() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { getAdminOverview().then(setOverview).catch((reason) => setError(String(reason))); }, []);
  return <div className="settings">
    <h2>Состояние системы</h2>
    {error && <p className="error">{error}</p>}
    {overview && <div className="card">
      <p>Пользователи: {overview.users}</p>
      <p>Активные наблюдения: {overview.active_watches}</p>
      <p>Уведомления: {overview.notifications}</p>
      <p>Наблюдения с ошибкой: {overview.failed_watches}</p>
    </div>}
  </div>;
}

function UsersAdminScreen() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<"user" | "admin">("admin");
  const [error, setError] = useState("");
  const reload = () => Promise.all([getAdminUsers(), getAuditEvents()])
    .then(([nextUsers, nextEvents]) => { setUsers(nextUsers); setEvents(nextEvents); })
    .catch((reason) => setError(String(reason)));
  useEffect(() => { void reload(); }, []);
  const updateRole = (id: number, nextRole: "user" | "admin") => {
    setError("");
    setAdminUserRole(id, nextRole).then(() => void reload())
      .catch((reason) => setError(String(reason)));
  };
  return <div className="settings">
    <h2>Роли пользователей</h2>
    <p className="hint">Укажите Telegram ID. Доступ к секретам и назначению ролей остаётся у Super Admin.</p>
    <form className="card" onSubmit={(event) => {
      event.preventDefault();
      const id = Number(userId);
      if (!Number.isSafeInteger(id) || id <= 0) { setError("Неверный Telegram ID"); return; }
      updateRole(id, role);
      setUserId("");
    }}>
      <input inputMode="numeric" value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Telegram ID" required />
      <select value={role} onChange={(event) => setRole(event.target.value as "user" | "admin")}>
        <option value="admin">Admin</option><option value="user">User</option>
      </select>
      <button className="btn-primary" type="submit">Сохранить роль</button>
    </form>
    {error && <p className="error">{error}</p>}
    {users.map((user) => <article className="card" key={user.id}>
      <b>{user.id}</b> · {user.role}
      <p className="hint">Создан: {new Date(user.created_at).toLocaleString("ru-RU")}</p>
      <div className="card-actions">
        {user.role !== "admin" && <button className="btn-outline" onClick={() => updateRole(user.id, "admin")}>Сделать Admin</button>}
        {user.role !== "user" && <button className="btn-outline" onClick={() => updateRole(user.id, "user")}>Сделать User</button>}
      </div>
    </article>)}
    <h2>Журнал действий</h2>
    {events.map((event, index) => <p className="card" key={`${event.created_at}-${index}`}>
      {new Date(event.created_at).toLocaleString("ru-RU")} · {event.actor_id} · {event.action} · {event.subject}
    </p>)}
  </div>;
}

function SettingsScreen() {
  const [budget, setBudget] = useState<BudgetInfo | null>(null);
  useEffect(() => { getBudget().then(setBudget); }, []);
  return (
    <div className="settings">
      <h2>Лимиты и модели</h2>
      <div className="card">
        <p className="hint">Осталось запросов сегодня</p>
        <p className="budget-big">{budget ? `${budget.remaining} из ${budget.limit}` : "…"}</p>
        <p className="hint">
          Бесплатные модели OpenRouter: 50 запросов/день, после разового
          пополнения от $10 — 1000/день. Профиль: {budget?.profile ?? "quality"}.
        </p>
      </div>
      <h2>О приложении</h2>
      <p className="hint">
        ИИ-ассистент покупок для Ozon и Яндекс Маркета. Ответы основаны только
        на реальных данных маркетплейсов — бот не выдумывает товары и цены.
      </p>
    </div>
  );
}

// ─────────────────────────── TabBar ───────────────────────────────

function TabBar({ active, onTab }: { active: string; onTab: (t: string) => void }) {
  const tabs = [
    { key: "home", emoji: "🏠", label: "Главная" },
    { key: "favorites", emoji: "⭐", label: "Избранное" },
    { key: "settings", emoji: "⚙️", label: "Настройки" },
  ];
  return (
    <nav className="tabbar">
      {tabs.map((t) => (
        <button key={t.key} className={active === t.key ? "tab active" : "tab"} onClick={() => onTab(t.key)}>
          <span>{t.emoji}</span>
          {t.label}
        </button>
      ))}
    </nav>
  );
}
