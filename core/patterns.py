from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd


PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"),
    "phone_e164": re.compile(r"^\+?[1-9]\d{7,14}$"),
    "date_iso": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "datetime_iso": re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"),
    "postal_code_fr": re.compile(r"^\d{5}$"),
    "uuid": re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
    "url": re.compile(r"^https?://", re.IGNORECASE),
    "boolean_like": re.compile(r"^(true|false|yes|no|0|1)$", re.IGNORECASE),
}


@dataclass
class PatternMatch:
    name: Optional[str]
    confidence: float


def detect_pattern(values: pd.Series, sample_size: int = 5_000) -> PatternMatch:
    """
    Detect a dominant regex pattern in a string-like series.
    """
    s = values.dropna().astype(str).str.strip()

    if s.empty:
        return PatternMatch(None, 0.0)

    if len(s) > sample_size:
        s = s.sample(sample_size, random_state=42)

    total = len(s)
    best_name: Optional[str] = None
    best_count = 0

    for name, regex in PATTERNS.items():
        count = int(s.map(lambda x: bool(regex.fullmatch(x))).sum())
        if count > best_count:
            best_count = count
            best_name = name

    confidence = best_count / total if total else 0.0

    if confidence < 0.80:
        return PatternMatch(None, round(confidence, 3))

    return PatternMatch(best_name, round(confidence, 3))