from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "sqlite:///./data/clash_detection.db"
    storage_root: Path = Path("./data/storage")
    web_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_archive_entries: int = Field(default=5_000, gt=0)
    max_archive_uncompressed_bytes: int = Field(default=250 * 1024 * 1024, gt=0)

    inference_provider: str = "mock"
    inference_base_url: str = "http://localhost:8001/v1"
    inference_api_key: str = "local"
    inference_timeout_seconds: float = Field(default=180, gt=0)
    max_concurrent_inference: int = Field(default=1, gt=0)

    model_name: str = "Qwen/Qwen3-VL-2B-Instruct"
    served_model_name: str = "clash-detection-qwen3-vl-2b"
    adapter_name: str = "train_2026-06-27-00-01-40"
    prompt_version: str = "clash-analysis-v1"
    parser_version: str = "navisworks-v1"
    severity_rule_version: str = "severity-v1"

    @cached_property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.web_origins.split(",") if value.strip()]

    def prepare_directories(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            database_path = Path(self.database_url.removeprefix("sqlite:///"))
            if str(database_path) != ":memory:":
                database_path.parent.mkdir(parents=True, exist_ok=True)
