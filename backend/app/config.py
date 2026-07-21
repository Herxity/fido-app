from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIDO_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "production"
    provider_mode: Literal["live", "development", "test"] = "live"
    database_url: str = "postgresql+psycopg://fido@localhost/fido"
    cors_origins: list[str] = Field(default_factory=list)
    clerk_issuer: str = ""
    clerk_audience: str = ""
    clerk_jwks_url: str = ""
    clerk_authorized_parties: list[str] = Field(default_factory=list)
    clerk_allow_legacy_org_claims: bool = False
    clerk_webhook_secret: str = ""
    identity_hash_key: str = ""
    field_encryption_key: str = ""
    lookup_hash_key: str = ""
    webhook_tolerance_seconds: int = 300
    request_body_limit: int = 1_048_576

    @model_validator(mode="after")
    def reject_unsafe_provider_configuration(self) -> "Settings":
        if self.environment == "production" and self.provider_mode != "live":
            raise ValueError("fake providers are forbidden in production")
        if self.provider_mode != "live" and self.provider_mode != self.environment:
            raise ValueError("provider mode must match the explicit non-production environment")
        if self.environment == "production" and not self.clerk_authorized_parties:
            raise ValueError("production requires an explicit Clerk authorized-party allowlist")
        if self.environment == "production" and len(self.identity_hash_key) < 32:
            raise ValueError("production requires a 32-character identity hash key")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
