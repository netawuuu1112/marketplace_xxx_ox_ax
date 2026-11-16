export const SOURCE_SEARCH: Record<string, { name: string; base: string; param: string }> = {
  ozon: { name: 'Ozon', base: 'https://www.ozon.ru/search/', param: 'text' },
  wildberries: { name: 'Wildberries', base: 'https://www.wildberries.ru/catalog/0/search.aspx', param: 'search' },
  yandex_market: { name: 'Яндекс Маркет', base: 'https://market.yandex.ru/search', param: 'text' },
  avito: { name: 'Авито', base: 'https://www.avito.ru/rossiya', param: 'q' },
  taobao: { name: 'Taobao', base: 'https://s.taobao.com/search', param: 'q' },
  megamarket: { name: 'Мегамаркет', base: 'https://megamarket.ru/catalog/?type=products', param: 'q' },
  lamoda: { name: 'Lamoda', base: 'https://www.lamoda.ru/catalogsearch/result/', param: 'q' },
  dns: { name: 'DNS', base: 'https://www.dns-shop.ru/search/', param: 'q' },
  citilink: { name: 'Ситилинк', base: 'https://www.citilink.ru/search/', param: 'text' },
  aliexpress: { name: 'AliExpress', base: 'https://aliexpress.ru/wholesale', param: 'SearchText' },
};

export function sourceSearchUrl(source: string, query: string): string | null {
  const spec=SOURCE_SEARCH[source];
  if (!spec) return null;
  const url=new URL(spec.base);
  url.searchParams.set(spec.param,query);
  return url.toString();
}
