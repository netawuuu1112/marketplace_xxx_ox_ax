"""Read-only production probe with signed Telegram initData, without printing it."""

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request(path: str, headers: dict[str, str]) -> dict:
    url = "https://marketfusionai.kosmo-connect.ru" + path
    with urlopen(Request(url, headers=headers), timeout=110) as response:
        return json.load(response)


def main() -> None:
    env_file = Path(__file__).resolve().parents[2] / ".env"
    settings = {
        key: value.strip()
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
        for key, _, value in [line.partition("=")]
    }
    token = settings["SHOPPER_BOT_TOKEN"]
    user_id = int(settings["TELEGRAM_ADMIN_IDS"].split(",", 1)[0])
    values = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    headers = {"X-Telegram-Init-Data": urlencode(values)}

    me = request("/api/auth/me", headers)
    favorites = request("/api/favorites", headers)
    print(json.dumps({"auth_role": me.get("role"), "favorites": len(favorites.get("products", []))}))

    sources = sys.argv[1] if len(sys.argv) > 1 else "yandex_market"
    query = sys.argv[2] if len(sys.argv) > 2 else "ssd"
    search = request("/api/marketplaces/search?" + urlencode({"q": query, "sources": sources}), headers)
    print(json.dumps({
        "query": query,
        "complete": search.get("complete"),
        "total_offers": search.get("total_offers"),
        "outcomes": [
            {
                "source": item["source"], "status": item["status"],
                "offers": item["offers_returned"], "code": item.get("error_code"),
                "detail": item.get("detail", "")[:220],
            }
            for item in search.get("source_outcomes", [])
        ],
        "ordinary_prices": sum(offer.get("price_rub") is not None for offer in search.get("offers", [])),
        "priced_offers": [{
            "source": offer.get("source"), "product_id": offer.get("product_id"),
            "price_rub": offer.get("price_rub"), "price_kind": offer.get("price_kind"),
        } for offer in search.get("offers", []) if offer.get("price_rub") is not None],
        "first_offer_url": search.get("offers", [{}])[0].get("url") if search.get("offers") else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
