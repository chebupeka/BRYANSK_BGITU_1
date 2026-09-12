from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )

    text_processor: Literal["stub", "unavailable", "openai", "llm"] = "stub"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = Field(default="", max_length=200)
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = Field(default=20, gt=0, le=300)
    llm_max_tokens: int = Field(default=4096, ge=128, le=65536)
    # Only retries an invalid model result, never a network or HTTP error.
    llm_max_retries: int = Field(default=1, ge=0, le=1)
    llm_response_format: Literal["json_object", "none"] = "json_object"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    cache_max_entries: int = Field(default=128, ge=0, le=10000)
    cache_ttl_seconds: int = Field(default=300, ge=0, le=86400)
    max_concurrent_processes: int = Field(default=4, ge=1, le=128)

    @field_validator("llm_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
            )
            parsed.port  # Accessing .port also rejects invalid port syntax.
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("LLM_BASE_URL must be an HTTP(S) URL without credentials or query")
        return value

    @field_validator("llm_model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return value.strip()

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        origins = []
        for value in values:
            value = value.strip().rstrip("/")
            parsed = urlsplit(value)
            parsed.port  # Reject misspelled or out-of-range ports at startup.
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS_ORIGINS must contain explicit HTTP(S) origins")
            if value not in origins:
                origins.append(value)
        return origins
