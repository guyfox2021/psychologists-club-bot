from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Infrastructure-level configuration loaded from environment variables.

    Business-tunable values (trial length, subscription price, reminder
    schedule, community chat id) live in the `settings` DB table instead,
    since admins can change them at runtime via the /settings command.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---------------------------------------------------------
    bot_token: str = Field(alias="BOT_TOKEN")
    super_admin_ids: str = Field(default="", alias="SUPER_ADMIN_IDS")
    community_chat_id: int | None = Field(default=None, alias="COMMUNITY_CHAT_ID")

    @field_validator("community_chat_id", mode="before")
    @classmethod
    def _blank_community_chat_id_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    timezone: str = Field(default="Europe/Kyiv", alias="TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # When false, approved Students/Psychologists get the same immediate, free,
    # permanent access as Supervisors -- the whole payment flow is skipped, not
    # just hidden. Toggle back to true (and redeploy) to resume requiring payment.
    payment_required: bool = Field(default=True, alias="PAYMENT_REQUIRED")

    # --- Update delivery ----------------------------------------------------
    use_telegram_webhook: bool = Field(default=True, alias="USE_TELEGRAM_WEBHOOK")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    webhook_telegram_path: str = Field(default="/webhook/telegram", alias="WEBHOOK_TELEGRAM_PATH")
    webhook_monobank_path: str = Field(
        default="/webhook/monobank", alias="WEBHOOK_MONOBANK_PATH"
    )
    webhook_secret_token: str = Field(default="", alias="WEBHOOK_SECRET_TOKEN")
    web_server_host: str = Field(default="0.0.0.0", alias="WEB_SERVER_HOST")
    web_server_port: int = Field(default=8080, alias="WEB_SERVER_PORT")

    # --- PostgreSQL -----------------------------------------------------------
    postgres_host: str = Field(default="db", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="psychologists_club", alias="POSTGRES_DB")
    postgres_user: str = Field(default="psychologists_club", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")

    # --- Redis -----------------------------------------------------------------
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    # --- Monobank Acquiring ---------------------------------------------------------
    monobank_token: str = Field(default="", alias="MONOBANK_TOKEN")
    monobank_api_url: str = Field(default="https://api.monobank.ua", alias="MONOBANK_API_URL")
    monobank_merchant_domain: str = Field(default="", alias="MONOBANK_MERCHANT_DOMAIN")

    @property
    def super_admin_id_list(self) -> list[int]:
        return [
            int(raw_id.strip())
            for raw_id in self.super_admin_ids.split(",")
            if raw_id.strip()
        ]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_telegram_path}"

    @property
    def monobank_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_monobank_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
