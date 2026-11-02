from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("CIVIC_RECORDS_DATA_DIR", str(BACKEND_DIR / "data"))))
    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    llm_model: str = field(default_factory=lambda: _env("OLLAMA_LLM_MODEL", "qwen3:14b"))
    embedding_model: str = field(default_factory=lambda: _env("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
    frontend_dist: Path = field(
        default_factory=lambda: Path(_env("CIVIC_RECORDS_FRONTEND_DIST", str(PROJECT_DIR / "frontend" / "dist")))
    )
    # auto: use Ollama when it is reachable with the configured models, otherwise the
    # built-in CPU-only demo provider. "ollama" and "demo" force one or the other.
    ai_provider: str = field(default_factory=lambda: _env("CIVIC_RECORDS_AI", "auto").strip().lower())
    # Demo mode enables one-click sign-in as the seeded fictional accounts. Never enable in production.
    demo_mode: bool = field(default_factory=lambda: _flag("CIVIC_RECORDS_DEMO"))
    deployment_name: str = field(
        default_factory=lambda: _env("CIVIC_RECORDS_DEPLOYMENT", "Rivergate Fire Department (fictional demo)")
    )

    def validate(self) -> None:
        parsed = urlparse(self.ollama_base_url)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OLLAMA_BASE_URL must point to localhost; external AI services are disabled.")
        if self.ai_provider not in {"auto", "ollama", "demo"}:
            raise ValueError("CIVIC_RECORDS_AI must be one of: auto, ollama, demo.")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "civic-records.sqlite3"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"


settings = Settings()
settings.validate()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
