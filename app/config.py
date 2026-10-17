from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    FALKORDB_URL: str = "redis://localhost:6379"
    FALKORDB_HOST: str = "localhost"
    FALKORDB_PORT: int = 6379
    FALKORDB_PASSWORD: Optional[str] = None

    LLM_PROVIDER: str = "deterministic"  # "deterministic" | "groq" | "openai" | "gemini"
    LLM_API_KEY: Optional[str] = None

    PORT: int = 8000
    HOST: str = "0.0.0.0"

    COMPANY_GRAPH: str = "company_graph"
    DEFAULT_TEAM: str = "core_platform"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
