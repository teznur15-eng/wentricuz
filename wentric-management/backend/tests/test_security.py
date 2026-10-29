import hashlib
import hmac
import time

from app.config import settings
from app.security import digest, opaque_token, verify_telegram


def make_telegram_hash(payload: dict, bot_token: str) -> str:
    check_string = "\n".join(
        f"{key}={payload[key]}"
        for key in sorted(payload)
        if key != "hash" and payload[key] is not None
    )
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    return hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()


def test_valid_telegram_login_is_accepted(monkeypatch):
    token = "123456:test-bot-token-for-unit-tests"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    payload = {"id": 12345, "first_name": "Sardor", "auth_date": int(time.time())}
    payload["hash"] = make_telegram_hash(payload, token)

    ok, reason = verify_telegram(payload)

    assert ok is True
    assert reason == "ok"


def test_changed_telegram_data_is_rejected(monkeypatch):
    token = "123456:test-bot-token-for-unit-tests"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    payload = {"id": 12345, "first_name": "Sardor", "auth_date": int(time.time())}
    payload["hash"] = make_telegram_hash(payload, token)
    payload["first_name"] = "Boshqa shaxs"

    ok, reason = verify_telegram(payload)

    assert ok is False
    assert "imzosi" in reason.lower()


def test_expired_telegram_login_is_rejected(monkeypatch):
    token = "123456:test-bot-token-for-unit-tests"
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    payload = {"id": 12345, "first_name": "Sardor", "auth_date": int(time.time()) - 3600}
    payload["hash"] = make_telegram_hash(payload, token)

    ok, reason = verify_telegram(payload)

    assert ok is False
    assert "eskirgan" in reason.lower()


def test_digest_is_stable_and_opaque_token_is_long():
    assert digest("same-value") == digest("same-value")
    assert digest("same-value") != digest("another-value")
    token = opaque_token()
    assert len(token) >= 40
    assert digest(token) != token
