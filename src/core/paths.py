from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    env = (os.getenv("ANONYMIZER_DATA_DIR") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = repo_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def manual_tokens_path() -> Path:
    return data_dir() / "manual_tokens.json"


def manual_types_path() -> Path:
    return data_dir() / "manual_types.json"