from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_project_env(env_path: str | None = None) -> Path:
    path = Path(env_path) if env_path else _repo_root() / ".env"
    if path.exists():
        load_dotenv(path, override=False)
    return path


def runtime_env_status() -> dict[str, Any]:
    return {
        "openai_api_key": bool(os.getenv("OPENAI_API_KEY")),
        "lamini_api_key": bool(os.getenv("LAMINI_API_KEY")),
        "lmnr_project_api_key": bool(os.getenv("LMNR_PROJECT_API_KEY")),
    }


def ensure_real_call_requirements() -> dict[str, Any]:
    status = runtime_env_status()
    if not status["openai_api_key"]:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Real mode requires a model provider key in .env or shell env."
        )
    return status
