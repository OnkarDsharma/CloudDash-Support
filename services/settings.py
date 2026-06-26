from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "clouddash-support-api"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"

    llm_provider: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

    vector_store_path: str = ".data/vector_store"
    knowledge_base_path: str = "knowledge_base/articles"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

