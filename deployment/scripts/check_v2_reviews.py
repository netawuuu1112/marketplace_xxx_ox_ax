"""Bounded genuine review read through isolated local HTTP API; no LLM calls."""
import http.cookiejar
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request


def main():
    root = Path(__file__).resolve().parents[2]
    settings = dict(line.split('=', 1) for line in (root / '.env.v2-staging').read_text().splitlines() if '=' in line)
    base = 'http://127.0.0.1:8089'
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(Request(base + '/api/auth/login', data=json.dumps({'password': settings['V2_WEB_PASSWORD']}).encode(),
                             headers={'Content-Type': 'application/json', 'Origin': base}), timeout=15):
        pass
    report = []
    for market, native_id in [('yandex', '103604860921'), ('wb', '505976742')]:
        started = time.monotonic()
        row = {'source': market, 'native_id': native_id}
        try:
            with opener.open(base + '/api/reviews?marketplace=' + market + '&ext_id=' + native_id, timeout=25) as response:
                data = json.load(response)
            row.update(status=200, reviews=len(data['reviews']), scope=sorted({r.get('scope', 'unknown') for r in data['reviews']}))
        except HTTPError as exc:
            row.update(status=exc.code)
        row['elapsed_s'] = round(time.monotonic() - started, 2)
        report.append(row)
    target = root / 'backups/v2/live-reviews-16.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
