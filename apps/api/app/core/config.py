from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareerPilot API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://careerpilot:careerpilot@localhost:5432/careerpilot"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    embedding_provider: str = "deterministic"
    embedding_model: str = "careerpilot-hash-1024-v1"
    reranker_provider: str = "deterministic"
    reranker_model: str = "careerpilot-overlap-reranker-v1"
    auth_secret: str = "development-only-change-me-32-bytes"
    access_token_ttl_minutes: int = Field(default=60, ge=1, le=10_080)
    allow_demo_auth: bool = True
    demo_user_id: str = "demo-user"
    rate_limit_per_minute: int = Field(default=120, ge=1, le=1_000_000)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1, le=1_000_000)
    trusted_proxy_headers: bool = False
    # AI base_url guard (SSRF). Local-first installs legitimately point at
    # Ollama/llama.cpp on 127.0.0.1, so private hosts are allowed by default.
    # Set to false for a shared/Internet-facing deployment to block loopback and
    # RFC1918 targets; metadata endpoints are always blocked either way.
    ai_allow_private_hosts: bool = True
    # WeChat article import honours mp.weixin.qq.com/robots.txt by default.
    # Only disable this when you are authorised to fetch the article yourself.
    wechat_respect_robots: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CAREERPILOT_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment == "production" and (
            len(self.auth_secret) < 32 or self.auth_secret == "development-only-change-me-32-bytes"
        ):
            raise ValueError("production requires a non-default auth secret of 32+ characters")
        if self.environment == "production" and self.allow_demo_auth:
            raise ValueError("production must disable demo authentication")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
