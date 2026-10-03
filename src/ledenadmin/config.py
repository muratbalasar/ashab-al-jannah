from enum import StrEnum
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(StrEnum):
    DEV = "dev"
    EASYAUTH = "easyauth"


class AIProviderName(StrEnum):
    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


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
    allow_sqlite_in_production: bool = False

    ai_provider: AIProviderName = AIProviderName.LOCAL
    ai_model: str | None = None
    ai_timeout_seconds: float = Field(default=20.0, gt=0)
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    anthropic_api_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def superadmins(self) -> frozenset[str]:
        return frozenset(s.strip() for s in self.superadmin_subjects.split(",") if s.strip())

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        ZoneInfo(self.timezone)
        if self.is_production and self.auth_mode == AuthMode.DEV:
            raise ValueError("AUTH_MODE=dev is niet toegestaan wanneer APP_ENV=production")
        if (
            self.is_production
            and self.database_url.startswith("sqlite")
            and not self.allow_sqlite_in_production
        ):
            raise ValueError(
                "SQLite is in productie niet geschikt (geen persistente opslag in containers); "
                "stel DATABASE_URL in op Azure SQL of zet ALLOW_SQLITE_IN_PRODUCTION=true"
            )
        if self.ai_provider != AIProviderName.LOCAL and not self.ai_model:
            raise ValueError("AI_MODEL is verplicht voor een externe AI-provider")
        if self.ai_provider == AIProviderName.OPENAI and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is verplicht bij AI_PROVIDER=openai")
        if self.ai_provider == AIProviderName.ANTHROPIC and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is verplicht bij AI_PROVIDER=anthropic")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
