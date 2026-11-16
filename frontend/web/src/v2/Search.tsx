import { sourceSearchUrl } from "../marketplaceLinks";
﻿import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "./api";
import type { Filters, ProductGroup, SearchSnapshot, Sort, SourceStatus, Watch } from "./types";
import { Empty, Icon, money, ProductImage, Skeleton, sourceName } from "./ui";

export const SOURCES = ["wildberries", "yandex_market", "ozon", "megamarket", "avito", "dns", "citilink", "lamoda", "aliexpress", "taobao"];
const statuses: Record<SourceStatus["status"], string> = { pending: "Ищем", ok: "Готово", partial: "Неполные данные", blocked: "Недоступен", timeout: "Не ответил вовремя", auth_required: "Нужен вход на площадку", rate_limited: "Лимит запросов", parser_drift: "Изменился сайт", unavailable: "Недоступен" };
export function SourceProgress({ snapshot }: { snapshot: SearchSnapshot }) {
  const answered = snapshot.sources.filter(source => source.status !== "pending").length;
  return <section className="source-progress" aria-label="Статус источников" aria-live="polite"><div className="row between"><strong>{snapshot.status === "running" || snapshot.status === "queued" ? "Поиск продолжается" : snapshot.status === "cancelled" ? "Поиск остановлен" : "Поиск завершён"}</strong><span>{answered} / {snapshot.sources.length} площадок</span></div><div className="progress-track"><span style={{ width: `${snapshot.sources.length ? answered / snapshot.sources.length * 100 : 0}%` }}/></div><div className="source-chips">{snapshot.sources.map(source => <details key={source.source} className={`source-chip source-${source.status}`}><summary>{sourceName(source.source)} · {source.status === "ok" ? `${source.offers_count} предл.` : statuses[source.status]}</summary><p>{source.detail || statuses[source.status]}{source.checked_at && <><br/>Проверено {new Date(source.checked_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</>}<br/>{source.region || "Регион не указан"} · Доставка {source.supports_delivery ? "поддерживается" : "не предоставлена"} · Мониторинг {source.supports_monitoring ? "поддерживается" : "не поддерживается"}{source.status !== "pending" && source.status !== "ok" && <SourceLink source={source.source} query={snapshot.normalized_query}/>}</p></details>)}</div>{(!snapshot.complete || snapshot.sources.some(source => source.status !== "ok")) && snapshot.status === "complete" && <p className="muted">Сравнение неполное: часть площадок или обычных цен недоступна.</p>}</section>;
}
export function ProductCard({ group, favorite, onFavorite, onOpen, related = false }: { group: ProductGroup; favorite: boolean; onFavorite: (group: ProductGroup) => void; onOpen: (group: ProductGroup) => void; related?: boolean }) {
  const currency = group.offers[0]?.currency || "RUB";
  return <article className={`catalog-card ${related ? "related-card" : ""}`}><div className="card-media"><button className="image-button" aria-label={`Сравнить ${group.product.title}`} onClick={() => onOpen(group)}><ProductImage group={group}/></button><button className={`favorite-button ${favorite ? "is-favorite" : ""}`} aria-label={favorite ? `Убрать ${group.product.title} из избранного` : `Сохранить ${group.product.title}`} aria-pressed={favorite} onClick={() => onFavorite(group)}><Icon name="heart" size={20}/></button>{!related && <span className="match-badge"><Icon name="check" size={12}/>Точное совпадение</span>}</div><div className="card-body"><span className="eyebrow">{group.product.brand || group.product.category || "Товар"}</span><h3><button onClick={() => onOpen(group)}>{group.product.title}</button></h3><p className="variant-line">{Object.values(group.variant.attributes).map(String).join(" · ") || group.product.model}</p>{group.variant.mpn && <p className="variant-line">MPN: {group.variant.mpn.toUpperCase()}</p>}{related ? <p className="related-reason">{group.match_status === "probable" ? "Нужно уточнить вариант" : "Другой вариант"}{group.reasons.length > 0 && ` · ${group.reasons.join("; ")}`}</p> : <><strong className="product-price">{group.minimum_price == null ? "Цена не подтверждена" : money(group.minimum_price, currency)}</strong><p className="muted">{group.sources_count} {group.sources_count === 1 ? "площадка" : "площадки"} · {group.offers.length} предл.</p>{group.minimum_total != null && <small>С доставкой от {money(group.minimum_total, currency)}</small>}</>}<button className="compare-link" onClick={() => onOpen(group)}>{related ? "Посмотреть вариант" : "Сравнить предложения"}<span aria-hidden="true">↗</span></button></div></article>;
}
export function ProductGrid({ groups, favorites, onFavorite, onOpen, related = false }: { groups: ProductGroup[]; favorites: ProductGroup[]; onFavorite: (group: ProductGroup) => void; onOpen: (group: ProductGroup) => void; related?: boolean }) {
  return <div className="product-grid">{groups.map(group => <ProductCard key={group.variant.id} group={group} favorite={favorites.some(item => item.product.id === group.product.id)} onFavorite={onFavorite} onOpen={onOpen} related={related}/>)}</div>;
}
export default function Search({ region, setRegion, favorites, recent, watches, onFavorite, onOpen, onError, onRefresh }: {
  region: string; setRegion: (region: string) => void; favorites: ProductGroup[]; recent: { queries: string[]; products: ProductGroup[] };
  watches: Watch[]; onFavorite: (group: ProductGroup) => void; onOpen: (group: ProductGroup) => void;
  onError: (error: unknown) => void; onRefresh: () => void;
}) {
  const [query, setQuery] = useState("");
  const [snapshot, setSnapshot] = useState<SearchSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<Sort>("relevance");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<Filters>({});
  const [sources, setSources] = useState<string[]>([]);
  const job = useRef<{ controller: AbortController; id?: string; timer?: number; running: boolean } | null>(null);
  const initialQuery = useRef(false);
  const stop = () => {
    const current = job.current;
    job.current = null;
    if (!current) return;
    current.controller.abort();
    window.clearTimeout(current.timer);
    if (current.id && current.running) void api.cancel(current.id).catch(() => {});
  };
  useEffect(() => () => stop(), []);
  const run = async (value = query) => {
    if (!value.trim()) return;
    stop();
    setQuery(value); setError(""); setBusy(true); setSnapshot(null);
    const current = { controller: new AbortController(), running: true } as NonNullable<typeof job.current>;
    job.current = current;
    const accept = (data: SearchSnapshot) => {
      if (job.current !== current) return;
      current.id = data.search_id;
      current.running = data.status === "running" || data.status === "queued";
      setSnapshot(data); setBusy(current.running);
      if (data.error) setError(data.error);
      if (current.running) current.timer = window.setTimeout(poll, 1200);
      else onRefresh();
    };
    const fail = (reason: unknown) => {
      if (current.controller.signal.aborted || job.current !== current) return;
      // Stop only polling on transport failure; explicitly cancel the abandoned server job.
      stop(); setBusy(false); setError(String(reason instanceof Error ? reason.message : reason)); onError(reason);
    };
    const poll = async () => {
      try { accept(await api.snapshot(current.id!, current.controller.signal)); } catch (reason) { fail(reason); }
    };
    try {
      const data = await api.search({ query: value.trim(), region, ...(sources.length ? { sources } : {}), filters, sort }, current.controller.signal);
      // A source may finish POST after the user changed tabs. Cancel its server-side work too.
      if (job.current !== current) { if (["running", "queued"].includes(data.status)) void api.cancel(data.search_id).catch(() => {}); return; }
      accept(data);
    } catch (reason) { fail(reason); }
  };
  useEffect(() => {
    if (initialQuery.current) return;
    initialQuery.current = true;
    const fromLink = new URLSearchParams(window.location.search).get("q");
    if (fromLink) { void run(fromLink); const url = new URL(window.location.href); url.searchParams.delete("q"); window.history.replaceState({}, "", url.pathname + url.search + url.hash); }
  }, []);
  const updateNumber = (key: keyof Filters, value: string, minor = false) => setFilters(current => ({ ...current, [key]: value === "" ? undefined : Math.round(Number(value) * (minor ? 100 : 1)) }));
  const submit = (event: FormEvent) => { event.preventDefault(); void run(); };
  const reached = watches.filter(watch => watch.active && watch.last_price != null && watch.threshold != null && watch.last_price <= watch.threshold);
  return <div className="search-page"><section className={`search-intro ${snapshot ? "compact" : ""}`}><div className="intro-topline"><span className="eyebrow">ВАШ ПОМОЩНИК В ПОКУПКАХ</span><span className="region-label"><Icon name="pin" size={15}/>{region || "Выберите регион"}</span></div><h1>Найди дешевле.<br/><span>Купи вовремя.</span></h1><p>Сравнивай цены на маркетплейсах<br className="mobile-break"/> и следи за скидками.</p><form className="v2-search" onSubmit={submit}><Icon name="search"/><input aria-label="Название товара, модель или ссылка" placeholder="Название товара, модель или ссылка" value={query} onChange={event => setQuery(event.target.value)} maxLength={1000} required/><button className="primary" type="submit">Найти</button></form><div className="search-caption"><span>Точные варианты. Обычные цены. Честная доставка.</span><button className="text-button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}><Icon name="sliders" size={16}/>Фильтры</button></div></section>
    {filtersOpen && <form className="filter-panel panel" onSubmit={submit}><div className="filter-fields"><label>Цена от, ₽<input type="number" min="0" step="0.01" value={filters.min_price == null ? "" : filters.min_price / 100} onChange={event => updateNumber("min_price", event.target.value, true)}/></label><label>Цена до, ₽<input type="number" min="0" step="0.01" value={filters.max_price == null ? "" : filters.max_price / 100} onChange={event => updateNumber("max_price", event.target.value, true)}/></label><label>Рейтинг от<select value={filters.min_rating ?? ""} onChange={event => updateNumber("min_rating", event.target.value)}><option value="">Любой</option><option value="3">3+</option><option value="4">4+</option><option value="4.5">4,5+</option></select></label><label>Доставка, дней<input type="number" min="0" max="365" value={filters.delivery_days ?? ""} onChange={event => updateNumber("delivery_days", event.target.value)}/></label><label>Состояние<select value={filters.condition || ""} onChange={event => setFilters(current => ({ ...current, condition: event.target.value || undefined }))}><option value="">Любое</option><option value="new">Новое</option><option value="used">Б/у</option><option value="refurbished">Восстановленное</option></select></label><label>Регион доставки<input value={region} onChange={event => setRegion(event.target.value)} required maxLength={120}/></label></div><fieldset><legend>Площадки <span className="muted">· все, если не выбраны</span></legend><div className="source-selector">{SOURCES.map(source => <label key={source} className="check-chip"><input type="checkbox" checked={sources.includes(source)} onChange={() => setSources(current => current.includes(source) ? current.filter(item => item !== source) : [...current, source])}/>{sourceName(source)}</label>)}</div></fieldset><div className="row wrap"><label className="check-line"><input type="checkbox" checked={!!filters.in_stock} onChange={event => setFilters(current => ({ ...current, in_stock: event.target.checked || undefined }))}/>В наличии</label><label className="check-line"><input type="checkbox" checked={!!filters.exact_only} onChange={event => setFilters(current => ({ ...current, exact_only: event.target.checked || undefined }))}/>Только точные совпадения</label></div><button className="primary" type="submit" disabled={!query.trim()}>Применить и найти</button></form>}
    {error && <div className="error-banner" role="alert">{error}<button className="text-button" onClick={() => void run()}>Повторить</button></div>}
    {snapshot && <><SourceProgress snapshot={snapshot}/><div className="section-heading"><div><span className="eyebrow">РЕЗУЛЬТАТЫ ПОИСКА</span><h2>{snapshot.groups.length ? "Точные совпадения" : "Точных совпадений пока нет"}</h2></div><label className="sort-label"><span className="sr-only">Сортировка</span><select aria-label="Сортировка" value={sort} onChange={event => { setSort(event.target.value as Sort); }}><option value="relevance">По релевантности</option><option value="price">Дешевле</option><option value="total">Выгоднее с доставкой</option><option value="delivery">Быстрая доставка</option><option value="rating">По рейтингу</option></select></label></div><SortResults groups={snapshot.groups} sort={sort} region={region} favorites={favorites} onFavorite={onFavorite} onOpen={onOpen}/>{!snapshot.groups.length && !busy && <p className="muted">Уточните модель или посмотрите похожие варианты ниже. Их цены не участвуют в точном сравнении.</p>}{busy && <><div className="row between search-running"><p className="muted">Результаты появляются по мере ответа площадок</p><button className="text-button" onClick={() => { stop(); setBusy(false); setSnapshot(current => current ? { ...current, status: "cancelled" } : current); }}>Остановить</button></div>{!snapshot.groups.length && <Skeleton/>}</>}{snapshot.related.length > 0 && !filters.exact_only && <section className="related-section"><div className="section-heading"><div><span className="eyebrow">ОТДЕЛЬНО ОТ ТОЧНОГО СРАВНЕНИЯ</span><h2>Похожие товары</h2></div></div><ProductGrid groups={snapshot.related} favorites={favorites} onFavorite={onFavorite} onOpen={onOpen} related/></section>}</>}
    {busy && !snapshot && <Skeleton/>}
    {!snapshot && !busy && <>{recent.queries.length > 0 && <section className="recent-queries"><h2>Недавние запросы</h2><div className="row wrap">{recent.queries.map(value => <button className="query-chip" key={value} onClick={() => void run(value)}><Icon name="search" size={15}/>{value}</button>)}</div></section>}{reached.length > 0 && <section className="panel reached"><span className="eyebrow">ЦЕЛЕВАЯ ЦЕНА ДОСТИГНУТА</span>{reached.map(watch => <p key={watch.id}><strong>{watch.title}</strong> · {money(watch.last_price)}</p>)}</section>}{watches.some(watch => watch.active) && <section className="panel"><h2>Под наблюдением</h2>{watches.filter(watch => watch.active).slice(0, 3).map(watch => <div className="row between watch-preview" key={watch.id}><span>{watch.title}</span><strong>{money(watch.last_price)}</strong></div>)}</section>}{recent.products.length > 0 ? <section><div className="section-heading"><h2>Вы недавно находили</h2></div><ProductGrid groups={recent.products} favorites={favorites} onFavorite={onFavorite} onOpen={onOpen}/></section> : <Empty title="Всё начинается с точной модели">Введите название, артикул или ссылку. Мы соберём предложения и покажем, какие цены удалось подтвердить.</Empty>}<div className="trust-strip"><div><Icon name="check"/><span><strong>Один и тот же товар</strong><small>Разные объёмы и модели — отдельно</small></span></div><div><Icon name="chart"/><span><strong>Покупка в нужный момент</strong><small>История и уведомления о цене</small></span></div></div></>}
  </div>;
}

function SortResults({ groups, sort, region, ...rest }: { groups: ProductGroup[]; sort: Sort; region: string; favorites: ProductGroup[]; onFavorite: (group: ProductGroup) => void; onOpen: (group: ProductGroup) => void }) {
  const score = (group: ProductGroup) => {
    if (sort === "price") return group.minimum_price ?? Infinity;
    if (sort === "total") return group.minimum_total ?? Infinity;
    if (sort === "rating") return -Math.max(...group.offers.filter(offer => offer.match_status === "exact").map(offer => offer.rating ?? -1));
    if (sort === "delivery") return Math.min(...group.offers.filter(offer => offer.match_status === "exact" && offer.delivery.region === region && offer.delivery.date_max).map(offer => new Date(offer.delivery.date_max!).getTime()));
    return 0;
  };
  return <ProductGrid groups={sort === "relevance" ? groups : [...groups].sort((a, b) => score(a) - score(b))} {...rest}/>;
}



function SourceLink({source,query}:{source:string;query:string}) {
 const href=sourceSearchUrl(source,query);
 return href ? <a className="text-button" href={href} target="_blank" rel="noopener noreferrer">Открыть {sourceName(source)}</a> : null;
}
