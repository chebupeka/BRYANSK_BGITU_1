from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    text_processor: Literal["stub", "unavailable", "llm"] = "stub"
    # OpenAI-совместимый адрес модели. Значение по умолчанию — локальная Ollama.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = 120.0
