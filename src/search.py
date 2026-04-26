from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config


@dataclass
class SearchPreset:
    id: str
    name: str
    query: str
    enabled: bool
    max_messages: int


def load_presets(path: Path | None = None) -> list[SearchPreset]:
    root = config.root_dir()
    p = path or root / "config" / "search_presets.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    presets: list[SearchPreset] = []
    for row in data.get("presets", []):
        presets.append(
            SearchPreset(
                id=str(row["id"]),
                name=str(row.get("name", row["id"])),
                query=str(row["query"]),
                enabled=bool(row.get("enabled", True)),
                max_messages=int(row.get("max_messages", 25)),
            )
        )
    return presets


def enabled_presets(presets: list[SearchPreset]) -> list[SearchPreset]:
    return [p for p in presets if p.enabled]
