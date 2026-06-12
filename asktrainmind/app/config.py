from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME = "AskTrainMind"


@dataclass
class AIConfig:
    provider: str = "null"
    endpoint: str = ""
    model: str = ""
    deployment: str = ""
    api_key: str = ""
    vision_enabled: bool = False
    fetch_documents: bool = False  # Optional document enrichment, never required for results


def appdata_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", appdata_dir())) if os.name == "nt" else Path.home() / ".cache"
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return appdata_dir() / "config.json"


def load_ai_config() -> AIConfig:
    path = config_path()
    if not path.exists():
        return AIConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AIConfig()
    defaults = asdict(AIConfig())
    merged = {k: data.get(k, default) for k, default in defaults.items()}
    merged["vision_enabled"] = bool(merged.get("vision_enabled", False))
    return AIConfig(**merged)


def save_ai_config(config: AIConfig) -> None:
    config_path().write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    candidate = base / relative
    if candidate.exists():
        return candidate

    alt = base / "asktrainmind" / relative
    if alt.exists():
        return alt
    return candidate
