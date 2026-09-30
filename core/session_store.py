from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import Any

import pandas as pd


SESSION_FILE = pathlib.Path(".streamlit/session_state.json")
MAX_DF_CHARS = 2_000_000

PERSIST_KEYS = (
    "lang",
    "nav_view",
    "filename",
    "contract_text",
    "contract",
    "validation_report",
    "warnings",
)


def _serialize(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)

    if isinstance(value, pd.DataFrame):
        csv_text = value.to_csv(index=False)
        if len(csv_text) <= MAX_DF_CHARS:
            return {"__dataframe__": csv_text}
        return None

    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]

    return value


def save_session(state: Any) -> None:
    data: dict[str, Any] = {}

    for key in PERSIST_KEYS:
        if key in state:
            data[key] = _serialize(state[key])

    df = state.get("df")
    if isinstance(df, pd.DataFrame):
        csv_text = df.to_csv(index=False)
        if len(csv_text) <= MAX_DF_CHARS:
            data["_df_csv"] = csv_text

    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def load_session() -> dict[str, Any] | None:
    if not SESSION_FILE.exists():
        return None

    try:
        raw = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

    df_csv = raw.pop("_df_csv", None)
    if df_csv:
        try:
            raw["df"] = pd.read_csv(pd.io.common.StringIO(df_csv))
        except Exception:
            raw["df"] = None

    return raw


def clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()