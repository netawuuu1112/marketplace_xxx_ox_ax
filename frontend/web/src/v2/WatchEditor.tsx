import { useState, type FormEvent } from "react";
import { api } from "./api";
import type { ProductGroup, Rules, Watch, WatchInput } from "./types";
import { Dialog, sourceName } from "./ui";

const booleanRules: { key: keyof Rules; label: string }[] = [
  { key: "historical_low", label: "Новый исторический минимум" }, { key: "low_30", label: "Минимум за 30 дней" },
  { key: "low_90", label: "Минимум за 90 дней" }, { key: "back_in_stock", label: "Снова в продаже" },
  { key: "cheaper_source", label: "Дешевле на другой площадке" },
];
export default function WatchEditor({ group, watch, region, onClose, onSaved, onError }: {
  group?: ProductGroup; watch?: Watch; region: string; onClose: () => void; onSaved: () => void; onError: (reason: unknown) => void;
}) {
  const [mode, setMode] = useState<"offer" | "minimum">(watch?.mode || "minimum");
  const exactOffers = group?.offers.filter(offer => offer.match_status === "exact") || [];
  const [offerId, setOfferId] = useState(watch?.offer_id || exactOffers[0]?.id || "");
  const [target, setTarget] = useState(watch?.threshold == null ? "" : String(watch.threshold / 100));
  const [interval, setInterval] = useState(watch?.interval_minutes || 60);
  const [cooldown, setCooldown] = useState(watch?.cooldown_minutes ?? 360);
  const [watchRegion, setWatchRegion] = useState(watch?.region || region);
  const [rules, setRules] = useState<Rules>(watch?.rules || { historical_low: true });
  const [sources, setSources] = useState<string[]>(watch?.sources || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const availableSources = [...new Set([...(group?.offers.map(offer => offer.source) || []), ...(watch?.sources || [])])];
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!watchRegion.trim()) { setError("Укажите регион доставки."); return; }
    if (mode === "offer" && !offerId) { setError("Выберите конкретное предложение."); return; }
    if (!target && !Object.values(rules).some(Boolean)) { setError("Выберите хотя бы одно условие уведомления."); return; }
    setBusy(true); setError("");
    const payload: WatchInput = {
      product_id: watch?.product_id || group!.product.id, mode,
      ...(mode === "offer" ? { offer_id: offerId } : {}), region: watchRegion.trim(), sources,
      threshold: target === "" ? null : Math.round(Number(target) * 100), interval_minutes: interval,
      rules, cooldown_minutes: cooldown,
    };
    try {
      if (watch) await api.editWatch(watch.id, payload); else await api.createWatch(payload);
      onSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); onError(reason); }
    finally { setBusy(false); }
  };
  return <Dialog title={watch ? "Настроить наблюдение" : "Следить за ценой"} onClose={onClose}><form className="watch-form" onSubmit={save}><div className="selected-product"><span className="eyebrow">ВЫБРАННЫЙ ТОВАР</span><strong>{group?.product.title || watch?.title}</strong>{group && <small>{Object.values(group.variant.attributes).map(String).join(" · ")}</small>}</div><label>Режим отслеживания<select value={mode} onChange={event => setMode(event.target.value as typeof mode)}><option value="minimum">Минимум по площадкам</option><option value="offer">Одна карточка</option></select></label>{mode === "offer" && <label>Предложение<select value={offerId} onChange={event => setOfferId(event.target.value)} required><option value="">Выберите предложение</option>{exactOffers.map(offer => <option value={offer.id} key={offer.id}>{sourceName(offer.source)} · {offer.seller || offer.title}</option>)}{watch?.offer_id && !exactOffers.some(offer => offer.id === watch.offer_id) && <option value={watch.offer_id}>Сохранённая карточка · {watch.offer_id}</option>}</select></label>}<label>Регион доставки<input value={watchRegion} onChange={event => setWatchRegion(event.target.value)} maxLength={120} required/></label><fieldset><legend>Условия уведомления</legend><div className="filter-fields"><label>Целевая цена, ₽<input type="number" min="0.01" step="0.01" inputMode="decimal" placeholder="Например, 5000" value={target} onChange={event => setTarget(event.target.value)}/></label><label>Снижение на сумму, ₽<input type="number" min="0.01" step="0.01" value={rules.drop_amount == null ? "" : rules.drop_amount / 100} onChange={event => setRules(current => ({ ...current, drop_amount: event.target.value ? Math.round(Number(event.target.value) * 100) : undefined }))}/></label><label>Снижение на процент, %<input type="number" min="0.01" max="100" step="0.01" value={rules.drop_percent ?? ""} onChange={event => setRules(current => ({ ...current, drop_percent: event.target.value ? Number(event.target.value) : undefined }))}/></label></div>{booleanRules.map(rule => <label className="check-line" key={rule.key}><input type="checkbox" checked={!!rules[rule.key]} onChange={event => setRules(current => ({ ...current, [rule.key]: event.target.checked }))}/>{rule.label}</label>)}</fieldset>{mode === "minimum" && availableSources.length > 0 && <fieldset><legend>Источники <span className="muted">· все, если не выбраны</span></legend><div className="source-selector">{availableSources.map(source => <label className="check-chip" key={source}><input type="checkbox" checked={sources.includes(source)} onChange={() => setSources(current => current.includes(source) ? current.filter(value => value !== source) : [...current, source])}/>{sourceName(source)}</label>)}</div></fieldset>}<div className="filter-fields"><label>Проверять каждые<select value={interval} onChange={event => setInterval(Number(event.target.value))}>{[15, 30, 60, 180, 360, 720, 1440].map(value => <option key={value} value={value}>{value < 60 ? `${value} минут` : `${value / 60} ч`}</option>)}</select></label><label>Пауза между уведомлениями, мин<input type="number" min="0" max="10080" value={cooldown} onChange={event => setCooldown(Number(event.target.value))}/></label></div><p className="muted">Проверяем выбранный вариант товара. Отсутствующая цена или временный сбой площадки не считаются снижением цены.</p>{error && <p className="error-banner" role="alert">{error}</p>}<button className="primary full" type="submit" disabled={busy}>{busy ? "Сохраняем…" : watch ? "Сохранить изменения" : "Создать наблюдение"}</button></form></Dialog>;
}
