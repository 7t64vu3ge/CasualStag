from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*args, **kwargs) -> bool:
        return False


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    api_host: str
    api_port: int
    explanation_mode: str
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    groq_api_key: str | None
    groq_model: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("FINANCIAL_AGENT_DATA_DIR", ROOT_DIR / "AgentAssignment")),
        api_host=os.getenv("FINANCIAL_AGENT_HOST", "127.0.0.1"),
        api_port=int(os.getenv("FINANCIAL_AGENT_PORT", "8000")),
        explanation_mode=os.getenv("FINANCIAL_AGENT_EXPLANATION_MODE", "template"),
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        langfuse_host=os.getenv("LANGFUSE_HOST"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )
