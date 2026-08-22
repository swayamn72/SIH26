from pathlib import Path
from typing import Any

import yaml

_CONFIG_CACHE: dict[str, Any] = {}


def load_config(name: str = "thresholds") -> dict[str, Any]:
    if name in _CONFIG_CACHE:
        return _CONFIG_CACHE[name]

    path = Path(__file__).parents[2] / "config" / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)
    _CONFIG_CACHE[name] = cfg
    return cfg


def load_prompt(name: str) -> str:
    path = Path(__file__).parents[2] / "config" / "llm_prompts" / name
    return path.read_text(encoding="utf-8")


def reload_config(name: str = "thresholds") -> dict[str, Any]:
    _CONFIG_CACHE.pop(name, None)
    return load_config(name)
