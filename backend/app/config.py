"""Application settings via environment variables."""
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Book Library"
    database_url: str = "sqlite:///./data/library.db"
    storage_dir: Path = Path("./data/files")  # uploaded PDFs
    # LLM settings for summarization (OpenAI-compatible endpoint)
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "z-ai/glm-5.3-flash"
    # max chars per chunk fed to the LLM for map-reduce summarization
    chunk_chars: int = 12000

    class Config:
        env_file = ".env"
        env_prefix = "LIBRARY_"


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
Path("./data").mkdir(exist_ok=True)
