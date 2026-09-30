from __future__ import annotations

import datetime as dt
from typing import Any


def build_payload(
    contract: dict[str, Any] | None,
    report: dict[str, Any] | None,
    lang: str,
) -> dict[str, Any]:
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "lang": lang,
        "contract": contract,
        "report": report,
    }