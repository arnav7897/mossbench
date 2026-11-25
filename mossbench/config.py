"""Environment configuration; credentials are never included in repr/output."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    moss_project_id: str | None = None
    moss_project_key: str | None = None
    moss_model: str = "moss/fastlane-1"
    moss_index_alias: str | None = None


def load_config():
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip("\"'")
            if key and key.replace("_", "").isalnum():
                os.environ.setdefault(key, value)
    return Config(
        moss_project_id=os.getenv("MOSS_PROJECT_ID"),
        moss_project_key=os.getenv("MOSS_PROJECT_KEY") or os.getenv("MOSS_API_KEY"),
        moss_model=os.getenv("MOSS_MODEL", "moss/fastlane-1"),
        moss_index_alias=os.getenv("MOSS_INDEX_ALIAS"),
    )
