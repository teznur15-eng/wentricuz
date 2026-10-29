from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = 'Wentric Management'
    environment: str = 'development'
    web_origin: str = 'http://localhost:3000'
    database_url: str = 'postgresql+asyncpg://wentric:change_me_db_password@127.0.0.1:5432/wentric'
    telegram_bot_token: str = ''
    telegram_bot_username: str = ''
    super_admin_telegram_ids: str = ''
    bot_api_secret: str = ''
    jwt_secret: str = ''
    session_idle_minutes: int = 30
    storage_dir: str = 'backend/storage'
    max_upload_mb: int = 20
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @property
    def super_admin_ids(self) -> set[int]:
        return {int(x.strip()) for x in self.super_admin_telegram_ids.split(',') if x.strip().isdigit()}

    @property
    def jwt_is_configured(self) -> bool:
        return len(self.jwt_secret) >= 32 and 'replace_with' not in self.jwt_secret

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
