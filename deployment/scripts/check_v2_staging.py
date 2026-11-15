"""Local Docker smoke check; no marketplace requests, bot polling or external keys."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    root = Path(__file__).resolve().parents[2]
    settings = dict(line.split('=', 1) for line in (root / '.env.v2-staging').read_text().splitlines() if '=' in line)
    base = 'http://127.0.0.1:8089'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='ru-RU')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base)
        page.get_by_label('Пароль', exact=True).fill(settings['V2_WEB_PASSWORD'])
        page.get_by_role('button', name='Войти', exact=True).click()
        nav = page.get_by_role('navigation', name='Главная навигация')
        expect(nav).to_be_visible()
        for tab, heading in [('Избранное', 'Избранное'), ('Мониторинг', 'Мониторинг цен'), ('Профиль', 'Профиль')]:
            nav.get_by_role('button', name=tab, exact=True).click()
            expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible()
        page.get_by_role('button', name='Управление сервисом', exact=False).click()
        expect(page.get_by_role('button', name='В профиль', exact=False)).to_be_visible()
        usage = context.request.get(base + '/api/v2/admin/usage')
        assert usage.ok and 'usage' in usage.json()
        nav.get_by_role('button', name='Поиск', exact=True).click()
        expect(page.get_by_role('button', name='Найти', exact=True)).to_be_visible()
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert any(cookie['httpOnly'] for cookie in context.cookies()), 'HttpOnly session required'
        health = context.request.get(base + '/health')
        assert health.ok and health.json().get('demo') is False
        assert not errors, errors
        (root / 'docs/qa').mkdir(exist_ok=True)
        page.screenshot(path=str(root / 'docs/qa/v2-staging-home-empty.png'), full_page=True)
        browser.close()
    print('Local staging verified: login, HttpOnly session, four tabs, protected admin usage, health, no page errors or horizontal overflow. No source search executed.')


if __name__ == '__main__':
    main()
