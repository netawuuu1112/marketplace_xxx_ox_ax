import { lazy, Suspense, useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, ApiError } from './v2/api';
import Search, { ProductGrid } from './v2/Search';
import ProductDetail from './v2/ProductDetail';
import WatchEditor from './v2/WatchEditor';
import { Empty, Icon, money, date, Skeleton, type IconName } from './v2/ui';
import type { ProductGroup, Watch, Notification } from './v2/types';
import { on, retrieveLaunchParams } from '@telegram-apps/sdk';
const Admin = lazy(() => import('./LegacyWorkspace').then(m => ({ default: m.V2Admin })));
type Tab = 'search' | 'favorites' | 'watches' | 'profile';
type Theme = 'auto' | 'light' | 'dark';

export default function App() {
  const [auth,setAuth] = useState<boolean|null>(null);
  const [role,setRole] = useState('user');
  const [tab,setTab] = useState<Tab>('search');
  const [region,setRegion] = useState('');
  const [favorites,setFavorites] = useState<ProductGroup[]>([]);
  const [recent,setRecent] = useState<{queries:string[];products:ProductGroup[]}>({queries:[],products:[]});
  const [watches,setWatches] = useState<Watch[]>([]);
  const [notifications,setNotifications] = useState<Notification[]>([]);
  const [product,setProduct] = useState<ProductGroup|null>(null);
  const [editing,setEditing] = useState<Watch|null>(null);
  const [error,setError] = useState('');
  const [toast,setToast] = useState('');
  const [loading,setLoading] = useState(false);
  const [admin,setAdmin] = useState(false);
  const [theme,setTheme] = useState<Theme>(() => (localStorage.getItem('mf-theme') as Theme)||'auto');
  const onError=useCallback((reason:unknown) => {
    if(reason instanceof ApiError && reason.status===401) setAuth(false);
    setError(reason instanceof Error ? reason.message : String(reason));
  },[]);
  useEffect(() => { api.me().then(me=>{setRole(me.role);setAuth(true);}).catch(()=>setAuth(false)); },[]);
  const refresh=useCallback(() => {
    setLoading(true);
    Promise.allSettled([
      api.profile().then(p=>setRegion(p.region)), api.favorites().then(r=>setFavorites(r.products)),
      api.recent().then(setRecent), api.watches().then(r=>setWatches(r.watches)),
      api.notifications().then(r=>setNotifications(r.notifications)),
    ]).then(results=>{results.forEach(r=>{if(r.status==='rejected')onError(r.reason);});setLoading(false);});
  },[onError]);
  useEffect(()=>{if(auth)refresh();},[auth,refresh]);
  useEffect(()=>{
    if(!auth)return;
    const params=new URLSearchParams(location.search);
    const id=params.get('product');
    if(params.get('section')==='watching')setTab('watches');
    if(id)api.product(id).then(setProduct).catch(onError);
  },[auth,onError]);
  useEffect(()=>{
    const media=matchMedia('(prefers-color-scheme: dark)');
    let telegram:Record<string,string>={};
    try { telegram=retrieveLaunchParams().tgWebAppThemeParams as Record<string,string>; } catch { /* Web theme. */ }
    const update=()=>{
      const bg=telegram.bg_color||telegram.bgColor;
      const dark=bg&&/^#[0-9a-f]{6}$/i.test(bg)?parseInt(bg.slice(1,3),16)*.299+parseInt(bg.slice(3,5),16)*.587+parseInt(bg.slice(5,7),16)*.114<130:media.matches;
      document.documentElement.dataset.theme=theme==='auto'?(dark?'dark':'light'):theme;
      for(const [key,value] of [['--bg',bg],['--ink',telegram.text_color||telegram.textColor],['--muted',telegram.hint_color||telegram.hintColor]]) {
        if(theme==='auto'&&value)document.documentElement.style.setProperty(key,value);
        else document.documentElement.style.removeProperty(key);
      }
    };
    update();localStorage.setItem('mf-theme',theme);media.addEventListener('change',update);
    const off=on('theme_changed',event=>{telegram=event.theme_params as Record<string,string>;update();});
    return()=>{media.removeEventListener('change',update);off();};
  },[theme]);
  useEffect(()=>{if(toast){const timer=setTimeout(()=>setToast(''),4500);return()=>clearTimeout(timer);}},[toast]);
  const favorite=(group:ProductGroup)=>{
    const remove=favorites.some(g=>g.product.id===group.product.id);
    api.favorite(group.product.id,remove).then(()=>{setFavorites(current=>remove?current.filter(g=>g.product.id!==group.product.id):[group,...current]);}).catch(onError);
  };
  const saveRegion=(value:string)=>{setRegion(value);};
  const changeTab=(next:Tab)=>{setProduct(null);setAdmin(false);setError('');setTab(next);window.scrollTo(0,0);};
  if(auth===null)return <div className="v2-app"><main><Skeleton/></main></div>;
  if(!auth)return <Login onLogin={()=>api.me().then(me=>{setRole(me.role);setAuth(true);})}/>;
  return <div className="v2-app"><header className="app-header"><button className="brand" onClick={()=>changeTab('search')} aria-label="MarketFusion AI — поиск"><span className="brand-mark">M</span><span>MarketFusion<span className="brand-ai"> AI</span></span></button><span className="live-label"><i/> Реальные предложения</span><button className="icon-button notification-trigger" aria-label="Уведомления" onClick={()=>changeTab('watches')}><Icon name="bell"/>{notifications.some(n=>!n.read)&&<i/>}</button></header>
    <main className="app-main">{error&&<div className="error-banner" role="alert">{error}<button className="text-button" onClick={()=>setError('')}>Закрыть</button></div>}
      {admin&&(role==='admin'||role==='super_admin')?<Suspense fallback={<Skeleton/>}><button className="back-button" onClick={()=>setAdmin(false)}><Icon name="arrow"/>В профиль</button><Admin role={role}/></Suspense>:
        product?<ProductDetail key={product.product.id} initial={product} region={region} favored={favorites.some(g=>g.product.id===product.product.id)} onFavorite={favorite} onBack={()=>setProduct(null)} onSaved={()=>{setToast('Наблюдение создано');refresh();}} onError={onError}/>:
        tab==='search'?<Search region={region} setRegion={saveRegion} favorites={favorites} recent={recent} watches={watches} onFavorite={favorite} onOpen={setProduct} onError={onError} onRefresh={refresh}/>:
        tab==='favorites'?<section><div className="page-heading"><span className="eyebrow">СОХРАНЕНО ДЛЯ ВАС</span><h1>Избранное</h1><p className="muted">Ваши товары и предложения площадок.</p></div>{loading?<Skeleton/>:favorites.length?<ProductGrid groups={favorites} favorites={favorites} onFavorite={favorite} onOpen={setProduct}/>:<Empty icon="heart" title="Сохраните то, что нравится">Добавьте товар в избранное из результатов поиска.</Empty>}</section>:
        tab==='watches'?<section><div className="page-heading"><span className="eyebrow">ПОКУПАЙТЕ ВОВРЕМЯ</span><h1>Мониторинг цен</h1><p className="muted">Наблюдения привязаны к выбранному товару и варианту.</p></div>{loading?<Skeleton/>:watches.length===0?<Empty icon="bell" title="Начните следить за ценой">Откройте найденный товар и выберите «Следить за ценой».</Empty>:<div className="watch-list">{watches.map(watch=><article className="panel watch-card" key={watch.id}><div className="row between"><span className={`pill ${watch.state==='active'?'success':''}`}>{watch.state==='needs_selection'?'Нужно выбрать товар':watch.active?'Наблюдаем':'На паузе'}</span><span className="muted">{watch.region||'Регион не задан'}</span></div><h2>{watch.title}</h2><div className="row between"><strong className="product-price">{money(watch.last_price)}</strong><span>Цель: {money(watch.threshold)}</span></div><p className="muted">Проверено: {date(watch.last_checked_at,true)} · Каждые {watch.interval_minutes} мин.</p>{watch.last_error&&<p className="warning-banner">{watch.last_error}</p>}<div className="row wrap">{watch.product_id&&<button className="secondary" onClick={()=>api.product(watch.product_id).then(setProduct).catch(onError)}>Карточка и история</button>}{watch.state!=='needs_selection'&&<><button className="secondary" onClick={()=>setEditing(watch)}>Настроить</button><button className="text-button" onClick={()=>api.editWatch(watch.id,{active:!watch.active}).then(refresh).catch(onError)}>{watch.active?'Пауза':'Возобновить'}</button></>}<button className="text-button danger" onClick={()=>api.deleteWatch(watch.id).then(refresh).catch(onError)}>Удалить</button></div></article>)}</div>}<section className="notifications"><div className="section-heading"><h2>Уведомления</h2></div>{notifications.length?notifications.map(n=><article className="panel" key={n.id}><small>{date(n.created_at,true)}</small><h3>{n.title}</h3><p className="notification-body">{n.body}</p></article>):<p className="muted">Здесь появятся зафиксированные изменения цены.</p>}</section></section>:
        <section className="profile"><div className="page-heading"><span className="eyebrow">ВАШ MARKETFUSION</span><h1>Профиль</h1></div><form className="panel" onSubmit={event=>{event.preventDefault();api.saveProfile(region).then(()=>setToast('Регион сохранён')).catch(onError);}}><h2>Регион доставки</h2><p className="muted">Итоговая стоимость рассчитывается только при подтверждённой доставке в этот регион.</p><label>Город или регион<input value={region} onChange={e=>setRegion(e.target.value)} maxLength={100} placeholder="Например, Москва"/></label><button className="primary" type="submit">Сохранить регион</button></form><section className="panel"><h2>Оформление</h2><div className="segmented">{(['auto','light','dark'] as Theme[]).map(t=><button key={t} className={theme===t?'active':''} onClick={()=>setTheme(t)}>{t==='auto'?'Системная':t==='light'?'Светлая':'Тёмная'}</button>)}</div></section>{(role==='admin'||role==='super_admin')&&<button className="panel admin-link" onClick={()=>setAdmin(true)}>Управление сервисом <span>Провайдеры ИИ, пользователи и диагностика →</span></button>}<p className="muted profile-note">Цены и наличие меняются на площадках. Неполные данные помечаются явно.</p></section>}
    </main><nav className="bottom-nav" aria-label="Главная навигация">{([{key:'search',label:'Поиск',icon:'search'},{key:'favorites',label:'Избранное',icon:'heart'},{key:'watches',label:'Мониторинг',icon:'bell'},{key:'profile',label:'Профиль',icon:'user'}] as {key:Tab;label:string;icon:IconName}[]).map(item=><button key={item.key} className={tab===item.key?'active':''} aria-current={tab===item.key?'page':undefined} onClick={()=>changeTab(item.key)}><Icon name={item.icon}/><span>{item.label}</span></button>)}</nav>{toast&&<div className="toast" role="status">{toast}</div>}{editing&&<WatchEditor watch={editing} region={region} onClose={()=>setEditing(null)} onSaved={()=>{setEditing(null);setToast('Наблюдение сохранено');refresh();}} onError={onError}/>}</div>;
}

function Login({onLogin}:{onLogin:()=>Promise<void>}){
  const [password,setPassword]=useState(''); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const submit=async(event:FormEvent)=>{event.preventDefault();setBusy(true);setError('');try{await api.login(password);await onLogin();}catch{setError('Не удалось войти. Проверьте пароль.');}finally{setBusy(false);}};
  return <main className="login-page"><div className="login-card panel"><span className="brand-mark">M</span><span className="eyebrow">MARKETFUSION AI</span><h1>Покупки с уверенностью.</h1><p className="muted">Откройте приложение через Telegram или войдите в веб-панель администратора.</p><form onSubmit={submit}><label>Пароль<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<p role="alert" className="error-banner">{error}</p>}<button className="primary full" disabled={busy}>{busy?'Проверяем…':'Войти'}</button></form></div></main>;
}
