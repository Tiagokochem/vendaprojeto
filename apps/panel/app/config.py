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

    demo_email: str = ""
    demo_password: str = ""
    # Só cria conta demo no boot se True (dev local). Produção: False.
    demo_seed: bool = False

    postgres_user: str = "venda"
    postgres_password: str = "venda_dev_pass"
    postgres_db: str = "vendaprojeto"
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    openai_api_key: str = ""
    # Compat: GROQ_API_KEY no .env (teste grátis). Se preenchida, usa Groq.
    groq_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    evolution_base_url: str = "http://127.0.0.1:8091"
    authentication_api_key: str = ""
    # URL que a Evolution usa para chamar o painel (rede Docker: http://panel:8088)
    evolution_webhook_base: str = ""
    # URL pública do Manager Evolution (browser)
    evolution_server_url: str = "http://127.0.0.1:8091"
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
    def llm_api_key(self) -> str:
        return (self.groq_api_key or self.openai_api_key or "").strip()

    @property
    def llm_base_url(self) -> str:
        if (self.groq_api_key or "").strip():
            return "https://api.groq.com/openai/v1"
        return (self.openai_base_url or "https://api.openai.com/v1").rstrip("/")

    @property
    def llm_model(self) -> str:
        model = (self.openai_model or "").strip()
        if (self.groq_api_key or "").strip():
            # Modelos OpenAI não rodam na Groq; default leve e rápido no free tier
            if not model or model.startswith("gpt-") or model.startswith("o1"):
                return "llama-3.1-8b-instant"
        return model or "gpt-4o-mini"

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
