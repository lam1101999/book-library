import os
from pathlib import Path

from pydantic_settings import BaseSettings

# On Vercel serverless the filesystem is ephemeral: default storage to /tmp
_IS_SERVERLESS = os.environ.get("VERCEL") == "1"
_DEFAULT_DB = "sqlite:////tmp/library.db" if _IS_SERVERLESS else "sqlite:///./data/library.db"
_DEFAULT_FILES = "/tmp/files" if _IS_SERVERLESS else "./data/files"


class Settings(BaseSettings):
    app_name: str = "Book Library"
    database_url: str = _DEFAULT_DB
    storage_dir: Path = Path(_DEFAULT_FILES)  # uploaded PDFs
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
if not _IS_SERVERLESS:
    Path("./data").mkdir(exist_ok=True)
