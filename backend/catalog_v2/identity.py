"""Deterministic candidate identity; similarity never overrides a variant conflict."""
import hashlib
import re
import unicodedata
from difflib import SequenceMatcher, get_close_matches

from pydantic import BaseModel, Field
from compare_connector.identity import normalize_gtin
from .models import ProductVariant

ALIASES = {'кингстон':'kingston', 'нв3':'nv3', 'нв2':'nv2', 'самсунг':'samsung', 'галакси':'galaxy',
    'айфон':'iphone', 'эппл':'apple', 'сони':'sony', 'терабайт':'1tb', 'терабайта':'1tb',
    'тб':'tb', 'гб':'gb', 'про':'pro', 'макс':'max', 'ультра':'ultra', 'с25':'s25', 'с24':'s24'}
BRANDS = ('kingston','samsung','apple','sony','xiaomi','lenovo','asus','acer','huawei','honor','realme','crucial','adata','netac','apacer')


def normalize_query(query: str) -> str:
    text = unicodedata.normalize('NFKC', query).casefold().replace('ё','е')
    text = re.sub(r'[\u200b-\u200f]', '', text)
    for source, target in ALIASES.items():
        text = re.sub(r'(?<!\w)' + re.escape(source) + r'(?!\w)', target, text)
    text = ' '.join((get_close_matches(word, BRANDS, n=1, cutoff=.83) or [word])[0]
        if word.isascii() and word.isalpha() and len(word)>=5 else word for word in text.split())
    text = re.sub(r'(\d)\s+(tb|gb)\b', r'\1\2', text)
    return re.sub(r'\s+', ' ', text).strip()


def identify(title: str, *, brand: str = '', model: str = '', mpn: str = '', gtin: str = '', attributes: dict | None = None, condition: str = 'unknown') -> ProductVariant:
    text = normalize_query(title)
    brand = normalize_query(brand) or next((b for b in BRANDS if re.search(r'\b'+b+r'\b',text)), '')
    if not brand and 'iphone' in text: brand = 'apple'
    patterns = [r'\bnv[2-9]\b', r'\b(?:galaxy\s+)?s\d{2}(?:\s+(?:ultra|plus|fe))?\b',
        r'\biphone\s+\d{1,2}(?:\s+pro)?(?:\s+max|\s+plus|\s+mini)?\b', r'\bwh[ -]?1000xm\d\b',
        r'\bredmi\s+note\s+\d+(?:\s+pro)?(?:\s+plus)?\b', r'\brtx\s*\d{4}(?:\s*ti)?\b']
    if not model:
        model = next((m.group(0) for p in patterns if (m := re.search(p,text))), '')
    model = normalize_query(model).removeprefix('galaxy ')
    attrs = {str(k): normalize_query(str(v)) for k,v in (attributes or {}).items()}
    sizes = sorted({int(m.group(1)) * (1000 if m.group(2)=='tb' else 1) for m in re.finditer(r'(?<!\w)(\d+)\s*(tb|gb)\b',text)})
    if not sizes and re.search(r'iphone|galaxy|redmi|s\d{2}', model):
        rest=text.replace(model,'')
        capacities=re.findall(r'\b(64|128|256|512|1024)\b',rest)
        if len(set(capacities))==1: sizes=[int(capacities[0])]
    if sizes:
        attrs.setdefault('storage_gb', str(max(sizes)))
        if len(sizes)>1: attrs.setdefault('ram_gb',str(min(sizes)))
    colors = {'натуральный титан':'natural titanium','natural titanium':'natural titanium', 'черный':'black','black':'black','белый':'white','white':'white','синий':'blue','blue':'blue'}
    for raw, color in colors.items():
        if raw in text: attrs.setdefault('color',color); break
    for pattern,key in [(r'(\d+)\s*(?:шт|pcs)\b','quantity'),(r'\bразмер\s+(\d+)\b','size')]:
        if m := re.search(pattern,text): attrs.setdefault(key,m.group(1))
    if re.search(r'\b(?:чехол|кабель|адаптер|case|enclosure|корпус)\b',text): attrs['accessory']='yes'
    if re.search(r'\b(?:бу|б/у|used|восстановлен\w*|refurbished)\b',text): condition='used'
    category = 'storage' if re.search(r'\bssd\b|\bnv\d\b',text) else 'phone' if re.search(r'iphone|galaxy|redmi|s\d{2}',model) else 'audio' if '1000xm' in model else 'other'
    return ProductVariant(title=title, brand=brand, model=model, category=category, mpn=re.sub(r'[^a-z0-9]','',mpn.casefold()), gtin=normalize_gtin(gtin), attributes=attrs, condition=condition)


class MatchDecision(BaseModel):
    status: str
    reasons: list[str] = Field(default_factory=list)


def match_variant(a: ProductVariant, b: ProductVariant) -> MatchDecision:
    conflicts=[]
    for key in ('brand','model','mpn','gtin'):
        av,bv=getattr(a,key),getattr(b,key)
        if av and bv and av != bv: conflicts.append(key)
    if a.condition != 'unknown' and b.condition != 'unknown' and a.condition != b.condition: conflicts.append('condition')
    for key in a.attributes.keys() & b.attributes.keys():
        if a.attributes[key] != b.attributes[key]: conflicts.append(key)
    if a.attributes.get('accessory') != b.attributes.get('accessory') and ('accessory' in a.attributes or 'accessory' in b.attributes): conflicts.append('accessory')
    if conflicts: return MatchDecision(status='rejected',reasons=['Несовместимые свойства: '+', '.join(conflicts)])
    if a.gtin and a.gtin == b.gtin or a.mpn and a.mpn == b.mpn:
        return MatchDecision(status='exact',reasons=['Совпадает идентификатор производителя'])
    missing = set(a.attributes) - set(b.attributes) | (set(b.attributes) - set(a.attributes))
    if missing: return MatchDecision(status='probable',reasons=['Не подтверждены: '+', '.join(sorted(missing))])
    required = {'storage_gb'} if a.category in ('storage','phone') else set()
    if a.brand and a.brand == b.brand and a.model and a.model == b.model and required.issubset(a.attributes) and required.issubset(b.attributes):
        return MatchDecision(status='exact',reasons=['Совпадают бренд, модель и значимые характеристики'])
    score=SequenceMatcher(None,normalize_query(a.title),normalize_query(b.title)).ratio()
    return MatchDecision(status='probable' if score>=.75 else 'similar',reasons=['Текстового сходства недостаточно для подтверждения идентичности'])


def identity_key(variant: ProductVariant, fallback: str = '') -> str:
    # Incomplete identities stay separate even when titles happen to match.
    complete=variant.brand and variant.model and (variant.category not in ('storage','phone') or 'storage_gb' in variant.attributes)
    proof=variant.gtin or variant.mpn or (variant.brand+'|'+variant.model if complete else '')
    attrs='|'.join(f'{k}={v}' for k,v in sorted(variant.attributes.items()))
    value=f'{proof}|{attrs}|{variant.condition}' if proof else fallback
    return hashlib.sha256(value.encode()).hexdigest()[:32]
