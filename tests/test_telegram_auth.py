import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from web import parse_init_data


def signed_init_data(token: str, auth_date: int) -> str:
    values = {"auth_date": str(auth_date), "user": json.dumps({"id": 42}, separators=(",", ":"))}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_signature_and_expiry():
    token = "123456:test-token"
    assert parse_init_data(signed_init_data(token, int(time.time())), token) == 42
    assert parse_init_data(signed_init_data(token, int(time.time()) - 90000), token) is None
    assert parse_init_data(signed_init_data(token, int(time.time())), "wrong-token") is None
