"""
Central application settings.

Every secret is read from the environment (see backend/.env.example). There are
deliberately no hardcoded credentials or fallback connection strings here: a
missing secret must fail loudly rather than silently connect somewhere unexpected.
"""

import os
import secrets
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(BASE_DIR), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---------------------------------------------------------
    APP_NAME: str = "Legal Metrology Compliance Auditing System"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: str = "development"

    # --- Persistence ---------------------------------------------------------
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "legal_metrology_db"

    # --- Security ------------------------------------------------------------
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    BOOTSTRAP_ADMIN_EMAIL: str = "admin@legalmetrology.gov.in"
    BOOTSTRAP_ADMIN_PASSWORD: str = ""

    # --- CORS ----------------------------------------------------------------
    # Kept as a plain string: pydantic-settings JSON-decodes complex types (list,
    # dict) straight from env/dotenv sources before any validator runs, so a
    # comma-separated value raises SettingsError. Parsed by `cors_origins`.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Evidence handling ---------------------------------------------------
    EVIDENCE_MAX_DIMENSION: int = 1600
    EVIDENCE_JPEG_QUALITY: int = 80
    MAX_IMAGES_PER_SCAN: int = 4

    #: Per-image ceiling. Uploads are read fully into memory for OCR, so without a
    #: bound one request can exhaust the process. 12 MB comfortably fits a modern
    #: phone photo; anything larger is downscaled before OCR anyway.
    MAX_IMAGE_BYTES: int = 12 * 1024 * 1024

    #: Ceiling on pasted listing text, for the same reason.
    MAX_LISTING_CHARS: int = 200_000

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _reject_wildcard(cls, v: str) -> str:
        # Starlette silently refuses to send credentials to a "*" origin, which
        # surfaces as confusing "logged out on refresh" bugs. Reject it outright.
        if "*" in v:
            raise ValueError(
                'CORS_ORIGINS must not contain "*" because the API sends credentials. '
                "List the exact frontend origins instead, comma-separated."
            )
        return v

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def mongo_enabled(self) -> bool:
        return bool(self.MONGODB_URI.strip())

    def resolved_jwt_secret(self) -> str:
        """
        Returns the signing key, generating an ephemeral one in development so a
        fresh clone runs without setup. In any non-development environment a real
        secret is mandatory - an ephemeral key would invalidate every token on restart.
        """
        if self.JWT_SECRET_KEY.strip():
            return self.JWT_SECRET_KEY.strip()
        if self.ENVIRONMENT.lower() not in ("development", "dev", "local", "test"):
            raise RuntimeError(
                "JWT_SECRET_KEY must be set outside development. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return _EPHEMERAL_DEV_SECRET


# Generated once per process. Development convenience only.
_EPHEMERAL_DEV_SECRET = secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
