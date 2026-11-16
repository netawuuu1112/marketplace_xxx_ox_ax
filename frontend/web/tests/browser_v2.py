"""Offline V2 UI behavior checks. Run against a local Vite server, never production.

API fixtures deliberately simulate source failures; they do not prove live connector access.
Requires Playwright Python and local Chrome: python tests/browser_v2.py
"""
import json
import os
import unittest
import re
from urllib.parse import urlparse,parse_qs

from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get("V2_UI_URL", "http://127.0.0.1:5175")
NOW = "2026-11-15T12:00:00Z"


def group(capacity="1TB", exact=True):
    pid = "nv3-1tb" if exact else "nv3-500gb"
    offer = {"id": "wb-" + pid, "product_id": pid, "variant_id": pid,
             "source": "wildberries", "native_id": "123", "title": "Kingston NV3 " + capacity,
             "seller": "SSD Store", "url": "https://www.wildberries.ru/catalog/123/detail.aspx",
             "image_url": None, "price": 479000, "conditional_prices": [{"amount": 450000, "condition": "WB Кошелёк"}],
             "currency": "RUB", "rating": 4.8, "in_stock": True, "condition": "new",
             "checked_at": NOW, "region": "Москва", "match_status": "exact" if exact else "similar",
             "delivery": {"price": None, "date_min": None, "date_max": None, "region": "Москва",
                          "checked_at": None, "confidence": "unknown", "conditions": None}}
    return {"product": {"id": pid, "title": "Kingston NV3 " + capacity, "brand": "Kingston", "model": "NV3", "category": "ssd", "image_url": None},
            "variant": {"id": pid, "product_id": pid, "attributes": {"capacity": capacity}, "mpn": "SNV3S/1000G", "gtin": None, "condition": "new"},
            "offers": [offer], "minimum_price": 479000 if exact else None, "minimum_total": None,
            "best_price_offer_id": offer["id"] if exact else None, "best_total_offer_id": None,
            "sources_count": 1, "match_status": "exact" if exact else "similar", "reasons": [] if exact else ["Другой объём"]}


class V2Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel="chrome", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 390, "height": 844}, locale="ru-RU")
        self.page = self.context.new_page()
        self.page.set_default_timeout(4500)
        self.authenticated = True
        self.profile_region = 'Москва'
        self.other_region_offer = False
        self.searches = []
        self.cancelled = []
        self.created_watches = []
        self.favorite_ids = []
        self.polls = 0
        self.keep_running = False
        self.console_errors = []
        self.page.on("pageerror", lambda error: self.console_errors.append(str(error)))
        self.context.route("**/api/**", self.api)

    def tearDown(self):
        self.context.close()

    def api(self, route):
        request = route.request
        path = urlparse(request.url).path
        response = {}
        status = 200
        if path == "/api/auth/me":
            status = 200 if self.authenticated else 401
            response = {"role": "user", "id": 10}
        elif path == "/api/auth/login":
            self.authenticated = True
        elif path == "/api/favorites":
            response = {"products": []}
        elif path == "/api/v2/profile":
            response = {"region": self.profile_region}
        elif path == "/api/v2/recent":
            response = {"queries": ["Sony WH-1000XM5"], "products": []}
        elif path == "/api/v2/favorites":
            if request.method == "POST":
                self.favorite_ids.append(request.post_data_json["product_id"])
            response = {"products": []}
        elif path == "/api/v2/watches":
            if request.method == "POST":
                self.created_watches.append(request.post_data_json)
                response = {**request.post_data_json, "id": 1, "active": True, "state": "active", "title": "Kingston NV3 1TB", "last_price": None, "last_checked_at": None, "last_error": None}
                status = 201
            else:
                response = {"watches": []}
        elif path == "/api/v2/notifications":
            response = {"notifications": []}
        elif path == "/api/v2/search" and request.method == "POST":
            self.searches.append(request.post_data_json)
            response = self.snapshot(False)
            status = 202
        elif path.startswith("/api/v2/search/"):
            if request.method == "DELETE":
                self.cancelled.append(path.rsplit("/", 1)[-1])
                response = self.snapshot(False)
            else:
                self.polls += 1
                response = self.snapshot(not self.keep_running)
        elif path.endswith("/history"):
            response = {"points": [], "summary": {"min": None, "max": None, "average": None}}
        elif path.startswith("/api/v2/products/"):
            response = group()
            if self.other_region_offer:
                response['offers'].append({**response['offers'][0],'id':'other-city','source':'yandex_market','price':100000,'region':'Омск'})
        route.fulfill(status=status, content_type="application/json", body=json.dumps(response))

    def snapshot(self, complete):
        return {"search_id": "search-1", "query": "Kingston NV3 1TB", "normalized_query": "Kingston NV3 1TB", "created_at": NOW,
                "status": "complete" if complete else "running", "complete": complete,
                "groups": [group()], "related": [group("500GB", False)],
                "sources": [{"source": "wildberries", "status": "ok", "detail": "", "offers_count": 1, "elapsed_ms": 80, "checked_at": NOW, "region": "Москва", "supports_delivery": False, "supports_monitoring": True},
                            {"source": "ozon", "status": "blocked" if complete else "pending", "detail": "Источник недоступен", "offers_count": 0, "elapsed_ms": 100, "checked_at": NOW, "region": "Москва", "supports_delivery": False, "supports_monitoring": False}]}

    def search(self):
        self.page.goto(BASE)
        self.page.get_by_role("textbox", name="Название товара, модель или ссылка").fill("Kingston NV3 1TB")
        self.page.get_by_role("button", name="Найти", exact=True).click()
        expect(self.page.get_by_role("button", name="Сравнить Kingston NV3 1TB")).to_be_visible()

    def test_web_login_then_four_tabs_without_fake_telegram_identity(self):
        self.authenticated = False
        self.page.goto(BASE)
        self.page.get_by_label("Пароль").fill("fixture-password")
        self.page.get_by_role("button", name="Войти", exact=True).click()
        expect(self.page.get_by_role("navigation", name="Главная навигация")).to_be_visible()
        for label in ["Поиск", "Избранное", "Мониторинг", "Профиль"]:
            expect(self.page.get_by_role("button", name=label, exact=True)).to_be_visible()
        self.assertEqual([], self.console_errors)

    def test_partial_results_render_before_blocked_source_finishes(self):
        self.search()
        expect(self.page.get_by_text("Поиск продолжается", exact=False)).to_be_visible()
        expect(self.page.get_by_text("Ozon · Недоступен", exact=False)).to_be_visible()
        expect(self.page.get_by_role("heading", name="Похожие товары")).to_be_visible()
        self.assertEqual("Kingston NV3 1TB", self.searches[0]["query"])
        self.assertNotIn("user_id", self.searches[0])
        self.page.locator('details.source-chip').filter(has_text='Ozon').locator('summary').click()
        link=self.page.get_by_role('link',name='Открыть Ozon',exact=True)
        expect(link).to_be_visible()
        self.assertEqual('Kingston NV3 1TB',parse_qs(urlparse(link.get_attribute('href')).query)['text'][0])

    def test_selected_variant_watch_and_unknown_delivery_not_free(self):
        self.search()
        self.page.get_by_role("button", name="Сравнить Kingston NV3 1TB").click()
        expect(self.page.locator('.price-summary').get_by_text("Итого не подтверждено", exact=False)).to_be_visible()
        expect(self.page.get_by_text("WB Кошелёк", exact=False)).to_be_visible()
        self.page.get_by_role("button", name="Следить за ценой", exact=True).click()
        self.page.get_by_label("Целевая цена, ₽").fill("4500")
        self.page.get_by_role("button", name="Создать наблюдение", exact=True).click()
        expect(self.page.get_by_text("Наблюдение создано", exact=False)).to_be_visible()
        self.assertEqual("nv3-1tb", self.created_watches[0]["product_id"])
        self.assertEqual(450000, self.created_watches[0]["threshold"])
        self.assertEqual("Москва", self.created_watches[0]["region"])

    def test_tab_change_cancels_pending_search(self):
        self.keep_running = True
        self.search()
        self.page.get_by_role("button", name="Избранное", exact=True).click()
        self.page.wait_for_timeout(250)
        self.assertIn("search-1", self.cancelled)

    def test_watch_can_use_single_actual_region_when_profile_has_none(self):
        self.profile_region=''
        self.search()
        self.page.get_by_role('button', name='Сравнить Kingston NV3 1TB').click()
        self.page.get_by_role('button', name='Следить за ценой',exact=True).click()
        expect(self.page.get_by_label('Регион доставки',exact=True)).to_have_value('Москва')

    def test_known_other_city_offer_does_not_lower_selected_city_summary(self):
        self.other_region_offer=True
        self.search()
        self.page.get_by_role('button',name='Сравнить Kingston NV3 1TB').click()
        expect(self.page.locator('.price-summary strong').first).to_have_text(re.compile(r'4\s*790'))
        expect(self.page.get_by_text('Цена для Омск',exact=True)).to_be_visible()


if __name__ == "__main__":
    unittest.main(verbosity=2)
