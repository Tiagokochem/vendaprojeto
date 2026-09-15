from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env", "/app/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    panel_secret: str = "dev-secret-change-me"
    panel_port: int = 8088
    app_env: str = "development"

    demo_email: str = "demo@vendaprojeto.local"
    demo_password: str = "demo1234"

    postgres_user: str = "venda"
    postgres_password: str = "venda_dev_pass"
    postgres_db: str = "vendaprojeto"
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    evolution_base_url: str = "http://127.0.0.1:8081"
    authentication_api_key: str = ""
    webhook_hmac_secret: str = ""

    apify_token: str = ""
    apify_actor_id: str = "compass/crawler-google-places"

    # URL pública (VPS) para back_urls e webhooks do Mercado Pago
    public_base_url: str = "http://127.0.0.1:8088"

    # Mercado Pago (Checkout Pro + doação)
    mercadopago_access_token: str = ""
    mercadopago_public_key: str = ""
    # Link pronto do MP (alternativa à preferência de doação)
    mercadopago_donation_url: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
