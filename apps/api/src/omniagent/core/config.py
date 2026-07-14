"""Configuration centralisee."""
from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def _coerce_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    app_name: str = "OmniAgent"
    env: str = "development"
    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def _coerce_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    version: str = "1.0.0"

    # DB
    database_url: str = "postgresql+asyncpg://omniagent:omniagent@localhost:5432/omniagent"
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Plateformes emploi (job boards)
    hunter_api_key: str = ""
    filtering_matching_agent_api_key: str = ""
    mission_controller_agent_api_key: str = ""
    adzuna_app_id: str = ""
    adzuna_api_key: str = ""
    ft_client_id: str = ""
    ft_client_secret: str = ""
    themuse_api_key: str = ""

    # SMTP (envoi email candidature)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = ""
    smtp_from_name: str = "OmniAgent"

    # Fiabilite connecteurs emploi (quotas/rate limits)
    employment_connector_cache_ttl_s: int = 300
    employment_connector_max_retries: int = 2
    employment_connector_backoff_base_s: float = 0.5

    # Garde-fous envoi candidature
    application_sender_confirmation_phrase: str = "JE CONFIRME L ENVOI"
    application_sender_require_cv: bool = True

    # Securite
    secret_key: str = "change-me-in-prod"
    # Liste des origines autorisees en CORS. Configurable via
    # `OMNIAGENT_CORS_ORIGINS` (liste separee par virgules, ex:
    # "http://localhost:13000,http://127.0.0.1:8090").
    # Defaut : frontend local principal uniquement.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Auth
    access_token_ttl_s: int = 3600
    refresh_token_ttl_s: int = 7 * 24 * 3600  # 7 jours
    # En dev, on peut accepter X-User/X-Role uniquement si active explicitement.
    allow_legacy_headers: bool = False

    # JWT
    jwt_secret: str = ""          # override possible via JWT_SECRET (defaut = secret_key)
    jwt_algorithm: str = "HS256"

    # Modules actifs (modularite : un module peut etre desactive sans casser l''app)
    # Vague B : focus Emploi uniquement. transverse reste actif (memory/knowledge/etc.).
    # Accepte soit une liste JSON (["emploi","transverse"]) soit une string CSV ("emploi,transverse").
    active_modules: list[str] = ["emploi", "transverse"]

    @field_validator("active_modules", mode="before")
    @classmethod
    def _coerce_active_modules(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _coerce_cors(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @model_validator(mode="after")
    def _validate_production_security(self):
        if self.env == "production":
            if self.secret_key == "change-me-in-prod":
                raise ValueError("SECRET_KEY invalide en production (valeur par defaut interdite)")
            local_hosts = ("localhost", "127.0.0.1")
            if any(any(host in origin for host in local_hosts) for origin in self.cors_origins):
                raise ValueError("CORS_ORIGINS invalide en production: localhost/127.0.0.1 interdits")
        return self

    # Limites LLM
    monthly_llm_quota_usd: float = 5.0

    # Event store (persistance des events metier)
    # "memory" : in-process uniquement, defaut (zero impact)
    # "sqlite" : persistance append-only via aiosqlite
    event_store_backend: str = "memory"
    event_store_path: str = "omniagent_events.db"

    # Dedupe window (secondes) pour l''EventBus : evite les doublons d''events consecutifs
    event_dedupe_window: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
