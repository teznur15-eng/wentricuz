import hashlib, hmac, json, secrets
from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings

def create_token(sid: str, employee_id: int) -> str:
    if not settings.jwt_is_configured:
        raise RuntimeError('JWT_SECRET kamida 32 belgi bo‘lishi kerak')
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(employee_id), 'sid': sid, 'iat': now, 'exp': now + timedelta(days=7)}, settings.jwt_secret, algorithm='HS256')

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])

def verify_telegram(data: dict) -> tuple[bool, str]:
    token = settings.telegram_bot_token
    if not token:
        return (False, 'TELEGRAM_BOT_TOKEN .env ichida sozlanmagan')
    supplied = str(data.get('hash', ''))
    try:
        auth = int(data.get('auth_date', 0))
        tid = int(data.get('id', 0))
    except (TypeError, ValueError):
        return (False, 'Telegram ma’lumotlari noto‘g‘ri')
    now = int(datetime.now(timezone.utc).timestamp())
    if not supplied or tid <= 0 or auth <= 0 or (now - auth > 600) or (auth - now > 60):
        return (False, 'Telegram login eskirgan yoki noto‘g‘ri')
    values = []
    for key in sorted(data):
        if key == 'hash' or data[key] is None:
            continue
        val = data[key]
        if isinstance(val, (dict, list)):
            val = json.dumps(val, ensure_ascii=False, separators=(',', ':'))
        values.append(f'{key}={val}')
    key = hashlib.sha256(token.encode()).digest()
    expected = hmac.new(key, '\n'.join(values).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        return (False, 'Telegram imzosi haqiqiy emas')
    return (True, 'ok')

def opaque_token() -> str:
    return secrets.token_urlsafe(32)

def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt_secret(value: str) -> str:
    """Encrypt a reusable secret using a key derived from JWT_SECRET."""
    import base64
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest())
    return Fernet(key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    """Decrypt an application secret previously written by encrypt_secret."""
    import base64
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest())
    return Fernet(key).decrypt(value.encode("ascii")).decode("utf-8")
