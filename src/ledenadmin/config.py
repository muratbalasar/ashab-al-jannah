from enum import StrEnum
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(StrEnum):
    DEV = "dev"
    EASYAUTH = "easyauth"


class AIProviderName(StrEnum):
    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class GeminiReasoningEffort(StrEnum):
    """Hoeveel Gemini 'nadenkt'; `none` kan alleen bij Gemini 2.5-modellen."""

    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class Settings(BaseSettings):
    """Centrale configuratie; waarden komen uit omgevingsvariabelen of `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./ledenadmin.db"
    timezone: str = "Europe/Amsterdam"

    auth_mode: AuthMode = AuthMode.EASYAUTH
    dev_user_name: str = "ontwikkelaar"
    dev_user_roles: str = "beheerder,penningmeester,bestuurder"
    role_claim_type: str = "roles"
    # Komma-gescheiden 'issuer|subject' van platformbeheerders (superadmin).
    superadmin_subjects: str = ""
    # Inlogpagina van Easy Auth; voor Entra External ID meestal /.auth/login/aad.
    easyauth_login_url: str = "/.auth/login/aad"
    # Ontvangt een melding bij elke nieuwe organisatie (optioneel).
    superadmin_email: str | None = None
    # Publieke basis-URL voor links in e-mails, bijv. https://ledenadmin.example.nl
    public_base_url: str = "http://localhost:8000"

    # Aanmelden van organisaties
    kvk_api_key: str | None = None
    kvk_api_url: str = "https://api.kvk.nl/api/v2/zoeken"
    max_organizations_per_user: int = Field(default=3, ge=1)

    # E-mail via Brevo; zonder sleutel delen beheerders de uitnodigingslink zelf.
    brevo_api_key: str | None = None
    mail_sender_email: str = "noreply@example.nl"
    mail_sender_name: str = "Ashab al-Jannah"
    mail_daily_limit: int = Field(default=300, ge=1)

    # Versleutelt de Mollie-sleutels van stichtingen in de database (Fernet-sleutel).
    # Maak er een met: python -c "from cryptography.fernet import Fernet;
    #   print(Fernet.generate_key().decode())"
    secret_encryption_key: str | None = None
    mollie_api_url: str = "https://api.mollie.com/v2"

    allow_donations_for_inactive_members: bool = False
    seed_default_categories: bool = True
    # Back-up van de SQLite-database via Litestream (zie docker-entrypoint.sh en README).
    litestream_replica_url: str | None = None
    # Alleen voor productie zonder Litestream, bijv. met een eigen back-up van een vast volume.
    allow_sqlite_in_production: bool = False

    # Wisselen van AI-dienst = alleen AI_PROVIDER aanpassen: sleutels en modellen per dienst
    # mogen naast elkaar blijven staan. <DIENST>_MODEL gaat voor op AI_MODEL.
    ai_provider: AIProviderName = AIProviderName.LOCAL
    ai_model: str | None = None
    ai_timeout_seconds: float = Field(default=20.0, gt=0)
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_base_url: str = GEMINI_OPENAI_BASE_URL
    gemini_reasoning_effort: GeminiReasoningEffort | None = GeminiReasoningEffort.MINIMAL

    # Helpassistent (US16): alleen actief met een externe AI-provider (zie assistant_active).
    assistant_enabled: bool = False
    assistant_daily_limit_per_user: int = Field(default=20, ge=1, le=100)
    assistant_daily_limit_total: int = Field(default=300, ge=1, le=5000)
    assistant_max_question_chars: int = Field(default=500, ge=50, le=1000)
    assistant_max_output_tokens: int = Field(default=600, ge=100, le=1500)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def assistant_active(self) -> bool:
        """De assistent staat aan én er is een externe AI-provider; anders is hij onzichtbaar."""
        return self.assistant_enabled and self.ai_provider != AIProviderName.LOCAL

    @property
    def model(self) -> str | None:
        """Het model voor de gekozen AI_PROVIDER: <DIENST>_MODEL, anders AI_MODEL."""
        specific = {
            AIProviderName.OPENAI: self.openai_model,
            AIProviderName.ANTHROPIC: self.anthropic_model,
            AIProviderName.GEMINI: self.gemini_model,
        }.get(self.ai_provider)
        return specific or self.ai_model

    @property
    def superadmins(self) -> frozenset[str]:
        return frozenset(s.strip() for s in self.superadmin_subjects.split(",") if s.strip())

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @field_validator("gemini_reasoning_effort", mode="before")
    @classmethod
    def _empty_is_default_of_model(cls, value):
        """Leeg = niets meesturen; Gemini gebruikt dan de standaard van het model."""
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        ZoneInfo(self.timezone)
        if self.is_production and self.auth_mode == AuthMode.DEV:
            raise ValueError("AUTH_MODE=dev is niet toegestaan wanneer APP_ENV=production")
        if (
            self.is_production
            and self.database_url.startswith("sqlite")
            and not self.litestream_replica_url
            and not self.allow_sqlite_in_production
        ):
            raise ValueError(
                "SQLite in productie vereist een back-up: zet LITESTREAM_REPLICA_URL (Litestream, "
                "zie README) of, met een eigen back-up, ALLOW_SQLITE_IN_PRODUCTION=true"
            )
        if self.ai_provider != AIProviderName.LOCAL and not self.model:
            raise ValueError(
                f"AI_MODEL (of {self.ai_provider.upper()}_MODEL) is verplicht voor "
                f"AI_PROVIDER={self.ai_provider}"
            )
        if self.ai_provider == AIProviderName.OPENAI and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is verplicht bij AI_PROVIDER=openai")
        if self.ai_provider == AIProviderName.ANTHROPIC and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is verplicht bij AI_PROVIDER=anthropic")
        if self.ai_provider == AIProviderName.GEMINI and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is verplicht bij AI_PROVIDER=gemini")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
