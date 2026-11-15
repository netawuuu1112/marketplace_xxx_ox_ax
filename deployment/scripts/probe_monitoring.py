"""Create a temporary Yandex Market watch and verify a real worker price sample."""

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE = "https://marketfusionai.kosmo-connect.ru"


def api(path, headers, payload=None, method=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(BASE + path, data=body, headers=headers, method=method)
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def main():
    env = {}
    for line in (Path(__file__).resolve().parents[2] / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key] = value.strip()
    values = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": int(env["TELEGRAM_ADMIN_IDS"].split(",", 1)[0])}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", env["SHOPPER_BOT_TOKEN"].encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    headers = {"X-Telegram-Init-Data": urlencode(values), "Content-Type": "application/json"}

    before = api("/api/watches", headers)["watches"]
    watch = api("/api/watches", headers, {
        "query": "ssd", "sources": ["yandex_market"], "interval_minutes": 15,
    })
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            watches = api("/api/watches", headers)["watches"]
            current = next(item for item in watches if item["id"] == watch["id"])
            if current["last_checked_at"]:
                history = api(f"/api/watches/{watch['id']}/history", headers)["history"]
                print(json.dumps({
                    "checked": True, "source": history[0]["source"] if history else None,
                    "price_recorded": bool(history and history[0]["price_rub"] > 0),
                    "error": current["last_error"],
                }, ensure_ascii=False))
                if not history or history[0]["price_rub"] <= 0:
                    raise RuntimeError("Worker did not record a comparable price")
                break
            time.sleep(10)
        else:
            raise TimeoutError("Worker did not check the watch within 120 seconds")
    finally:
        api(f"/api/watches/{watch['id']}", headers, method="DELETE")
        after = api("/api/watches", headers)["watches"]
        print(json.dumps({"original_watch_count": len(before), "restored_watch_count": len(after)}))
        if len(after) != len(before):
            raise RuntimeError("Temporary watch cleanup failed")


if __name__ == "__main__":
    main()
