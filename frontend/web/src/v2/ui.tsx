import { useEffect, useRef, type ReactNode } from "react";
import type { Offer, ProductGroup } from "./types";

export type IconName = "search" | "heart" | "bell" | "user" | "arrow" | "close" | "sliders" | "pin" | "external" | "chart" | "check" | "sun" | "moon";
export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    search: <><circle cx="10.7" cy="10.7" r="6.7"/><path d="m16 16 4.5 4.5"/></>,
    heart: <path d="M20.3 5.5a5 5 0 0 0-7.1 0L12 6.7l-1.2-1.2a5 5 0 0 0-7.1 7.1L12 21l8.3-8.4a5 5 0 0 0 0-7.1Z"/>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>,
    arrow: <path d="M19 12H5m6-6-6 6 6 6"/>, close: <path d="m6 6 12 12M6 18 18 6"/>,
    sliders: <><path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="17" r="2"/></>,
    pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/></>,
    external: <><path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/></>,
    chart: <><path d="M4 3v17h17M7 15l4-5 4 2 5-7"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
    moon: <path d="M21 13A9 9 0 0 1 11 3 9 9 0 1 0 21 13Z"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
export const sourceName = (source: string) => ({ wildberries: "Wildberries", wb: "Wildberries", yandex: "Яндекс Маркет", yandex_market: "Яндекс Маркет", ozon: "Ozon", dns: "DNS", citilink: "Ситилинк", megamarket: "Мегамаркет", avito: "Авито", lamoda: "Lamoda", aliexpress: "AliExpress", taobao: "Taobao", mvideo: "М.Видео" }[source] || source);
export const money = (amount: number | null | undefined, currency = "RUB") => amount == null ? "Цена неизвестна" : new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: amount % 100 ? 2 : 0 }).format(amount / 100);
export const date = (value?: string | null, time = false) => !value ? "Ещё не проверено" : new Date(value).toLocaleString("ru-RU", { day: "numeric", month: "short", ...(time ? { hour: "2-digit", minute: "2-digit" } : {}) });
export function confirmedTotal(offer: Offer, region: string): number | null {
  return offer.price != null && (!offer.region || offer.region === region) && offer.delivery.price != null && offer.delivery.confidence === "confirmed" && offer.delivery.region === region ? offer.price + offer.delivery.price : null;
}
export function safeUrl(value?: string | null): string | undefined {
  if (!value) return undefined;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : undefined; } catch { return undefined; }
}
export function ProductImage({ group }: { group: ProductGroup }) {
  const image = safeUrl(group.product.image_url || group.offers.find(offer => offer.image_url)?.image_url);
  return <div className="product-image">{image ? <img src={image} alt={group.product.title} loading="lazy" onError={event => { event.currentTarget.style.display = "none"; }} /> : <div className="image-placeholder"><span>{group.product.brand?.slice(0, 1) || "M"}</span><small>Фото не предоставлено</small></div>}</div>;
}
export function Skeleton({ count = 3 }: { count?: number }) {
  return <div className="product-grid" role="status" aria-label="Загрузка данных">{Array.from({ length: count }, (_, index) => <div className="skeleton-card" key={index}><div/><span/><span/></div>)}</div>;
}
export function Empty({ icon = "search", title, children }: { icon?: IconName; title: string; children: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Icon name={icon} size={30}/></div><h2>{title}</h2><p>{children}</p></div>;
}
export function Dialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = before; previous?.focus(); };
  }, []);
  return <dialog ref={ref} className="v2-dialog" aria-labelledby="dialog-title" onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => { if (event.target === ref.current) onClose(); }}><header><h2 id="dialog-title">{title}</h2><button className="icon-button" aria-label="Закрыть" onClick={onClose}><Icon name="close"/></button></header>{children}</dialog>;
}
