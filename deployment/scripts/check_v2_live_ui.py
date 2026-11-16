"""Render actual local catalog/history/reviews after check_v2_live_flow.py.

No API interception, Telegram send, LLM generation or production connection.
The review reader may make a bounded external source read on a cache miss.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    root = Path(__file__).resolve().parents[2]
    settings = dict(line.split('=', 1) for line in (root / '.env.v2-staging').read_text().splitlines() if '=' in line)
    flow = json.loads((root / 'backups/v2/live-staging-flow.json').read_text(encoding='utf-8'))
    base = 'http://127.0.0.1:8089'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 920}, locale='ru-RU')
        assert context.request.post(base + '/api/auth/login', data={'password': settings['V2_WEB_PASSWORD']}, headers={'Origin': base}).ok
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/?product=' + flow['product_id'])
        expect(page.get_by_role('heading', name='Предложения площадок', exact=True)).to_be_visible()
        expect(page.get_by_role('img', name='История из ', exact=False)).to_be_attached()
        assert page.locator('.offer-card').count() >= 3
        page.screenshot(path=str(root / 'docs/qa/v2-staging-product-live.png'))
        page.locator('#price-history').evaluate("element => element.scrollIntoView({block: 'start'})")
        page.screenshot(path=str(root / 'docs/qa/v2-staging-history-live.png'))
        # The separately verified requested card, not the first other seller.
        article = page.locator('.offer-card').filter(has=page.locator('a[href*="103604860921"]')).first
        article.get_by_role('button', name='Читать отзывы').click()
        expect(page.locator('.review-list .review-item').first).to_be_attached(timeout=20000)
        expect(page.get_by_text('Отзывы относятся к общей карточке товара и могут описывать другие варианты.', exact=True)).to_be_attached()
        page.locator('.review-section').evaluate("element => element.scrollIntoView({block: 'start'})")
        page.screenshot(path=str(root / 'docs/qa/v2-staging-reviews-live.png'))
        assert not errors, errors
        browser.close()
    print('Actual staging UI verified: offers, measured history, source reviews and scope warning; no fixture responses or JS errors')


if __name__ == '__main__':
    main()
