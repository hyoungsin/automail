from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


def history_path() -> Path:
    return config.root_dir() / "output" / "send_history.jsonl"


def append_history(record: dict) -> None:
    p = history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {**record, "ts": datetime.now(timezone.utc).isoformat()}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
