from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DETROIT_RECORDS_DATA_DIR", os.getenv("CIVICLENS_DATA_DIR", BACKEND_DIR / "data")))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    llm_model: str = os.getenv("OLLAMA_LLM_MODEL", "qwen3:14b")
    embedding_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    frontend_dist: Path = Path(os.getenv("DETROIT_RECORDS_FRONTEND_DIST", os.getenv("CIVICLENS_FRONTEND_DIST", PROJECT_DIR / "frontend" / "dist")))

    def validate(self) -> None:
        parsed = urlparse(self.ollama_base_url)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("OLLAMA_BASE_URL must point to localhost; external AI services are disabled.")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "civiclens.sqlite3"

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
