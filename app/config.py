"""
Centralized Config File
Uses pydantic-settings for validating env varaibles
"""

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):

    #LLM Configuration
    gemini_api_key: str
    primary_model: str = "gemini-3.7-flash"
    fallback_model: str = "gemini-3.6-flash"

    #LangSmith
    lanchain_tracing_v2: bool = True
    langchain_api_key: str
    langchain_project: str

    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit_per_minute: int = 20
    cache_ttl_seconds: int = 300
    max_retries: int = 3

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

@lru_cache
def get_settings() -> Settings:
    """Cached settings instance - loaded once, reused everywhere."""
    return Settings()