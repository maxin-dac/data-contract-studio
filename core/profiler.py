from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from .patterns import detect_pattern


NULL_TOKENS = {
    "",
    "na",
    "n/a",
    "null",
    "none",
    "nan",
    "nil",
    "-",
    "--",
}


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    nullable: bool
    null_rate: float
    distinct: int
    unique_candidate: bool
    primary_key_candidate: bool
    pattern: Optional[str] = None
    pattern_confidence: float = 0.0
    min: Any = None
    max: Any = None
    mean: Optional[float] = None
    median: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    p95: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[list[Any]] = None
    flags: list[str] = field(default_factory=list)


@dataclass
class DatasetProfile:
    filename: Optional[str]
    rows: int
    columns: int
    generated_at: str
    columns_profiles: dict[str, ColumnProfile]
    warnings: list[str] = field(default_factory=list)


def _jsonable(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)
        if math.isnan(value):
            return None
        return value

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]

    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}

    return value


def _normalize_nulls(series: pd.Series, unify_nulls: bool) -> pd.Series:
    s = series.copy()

    if unify_nulls and (
        pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)
    ):
        lowered = s.astype("string").str.strip().str.lower()
        mask = s.isna() | lowered.isin(NULL_TOKENS)
        s = s.mask(mask)

    return s


def _looks_integer(numbers: pd.Series) -> bool:
    numbers = numbers.dropna()
    if numbers.empty:
        return False
    return bool(np.allclose(numbers, np.round(numbers), atol=1e-9))


def _infer_dtype(series: pd.Series, pattern: Optional[str]) -> str:
    if series.empty:
        return "string"

    if pattern == "date_iso":
        return "date"

    if pattern == "datetime_iso":
        return "datetime"

    try:
        inferred = pd.api.types.infer_dtype(series, skipna=True)
    except TypeError:
        inferred = "string"

    if inferred in {"integer", "int64", "Int64"}:
        return "integer"

    if inferred in {"floating", "float64", "float"}:
        return "float"

    if inferred == "boolean":
        return "boolean"

    if inferred in {"datetime", "datetime64", "datetimetz"}:
        return "datetime"

    if inferred == "date":
        return "date"

    if inferred == "categorical":
        return "categorical"

    if inferred == "string":
        numeric = pd.to_numeric(series, errors="coerce")
        ratio = numeric.notna().mean()
        if ratio > 0.95:
            if _looks_integer(numeric):
                return "integer"
            return "float"

    return "string"


def profile_dataframe(
    df: pd.DataFrame,
    filename: Optional[str] = None,
    cat_threshold: int = 50,
    unify_nulls: bool = True,
) -> DatasetProfile:
    rows = len(df)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    profiles: dict[str, ColumnProfile] = {}
    warnings: list[str] = []

    for col in df.columns:
        raw = df[col]
        series = _normalize_nulls(raw, unify_nulls=unify_nulls)
        non_null = series.dropna()

        null_rate = 0.0 if rows == 0 else 1.0 - (len(non_null) / rows)
        distinct = int(non_null.nunique(dropna=True))

        pattern_match = detect_pattern(non_null)
        dtype = _infer_dtype(non_null, pattern_match.name)

        nullable = null_rate > 0
        unique_candidate = rows > 0 and null_rate == 0 and distinct == rows

        primary_key_candidate = (
            unique_candidate
            and dtype in {"integer", "string", "date", "datetime"}
            and pattern_match.name in {None, "uuid", "date_iso", "datetime_iso"}
        )

        flags: list[str] = []

        if null_rate > 0.5:
            flags.append("high_null_rate")

        if distinct == 0:
            flags.append("empty")

        if unique_candidate:
            flags.append("unique_candidate")

        if primary_key_candidate:
            flags.append("primary_key_candidate")

        if pattern_match.name:
            flags.append("pattern_detected")

        cp = ColumnProfile(
            name=str(col),
            dtype=dtype,
            nullable=nullable,
            null_rate=round(float(null_rate), 6),
            distinct=distinct,
            unique_candidate=unique_candidate,
            primary_key_candidate=primary_key_candidate,
            pattern=pattern_match.name,
            pattern_confidence=pattern_match.confidence,
            flags=flags,
        )

        if dtype in {"integer", "float"}:
            numeric = pd.to_numeric(non_null, errors="coerce").dropna()
            if not numeric.empty:
                cp.min = _jsonable(numeric.min())
                cp.max = _jsonable(numeric.max())
                cp.mean = _jsonable(float(numeric.mean()))
                cp.median = _jsonable(float(numeric.median()))
                cp.p25 = _jsonable(float(numeric.quantile(0.25)))
                cp.p75 = _jsonable(float(numeric.quantile(0.75)))
                cp.p95 = _jsonable(float(numeric.quantile(0.95)))

        elif dtype in {"date", "datetime"}:
            parsed = pd.to_datetime(non_null, errors="coerce").dropna()
            if not parsed.empty:
                cp.min = _jsonable(parsed.min())
                cp.max = _jsonable(parsed.max())

        else:
            strings = non_null.astype(str)
            if not strings.empty:
                lengths = strings.str.len()
                cp.min_length = int(lengths.min())
                cp.max_length = int(lengths.max())

        if (
            dtype in {"string", "categorical"}
            and 0 < distinct <= cat_threshold
            and pattern_match.name not in {"email", "uuid", "url", "phone_e164"}
        ):
            values = non_null.astype(str).unique().tolist()
            try:
                values.sort()
            except Exception:
                values = sorted(values, key=str)
            cp.allowed_values = values[:100]
            cp.flags.append("low_cardinality")

        profiles[str(col)] = cp

    if rows > 0 and not any(p.primary_key_candidate for p in profiles.values()):
        warnings.append("no_unique_column")

    if any(p.distinct == 0 for p in profiles.values()):
        warnings.append("empty_columns")

    return DatasetProfile(
        filename=filename,
        rows=rows,
        columns=len(df.columns),
        generated_at=generated_at,
        columns_profiles=profiles,
        warnings=warnings,
    )


def profile_to_dataframe(profile: DatasetProfile) -> pd.DataFrame:
    rows = []

    for p in profile.columns_profiles.values():
        rows.append(
            {
                "column": p.name,
                "dtype": p.dtype,
                "nullable": p.nullable,
                "null_rate": p.null_rate,
                "distinct": p.distinct,
                "unique_candidate": p.unique_candidate,
                "primary_key_candidate": p.primary_key_candidate,
                "pattern": p.pattern or "-",
                "min": p.min,
                "max": p.max,
                "allowed_values": (
                    ", ".join(map(str, p.allowed_values)) if p.allowed_values else "-"
                ),
                "flags": ", ".join(p.flags) if p.flags else "-",
            }
        )

    return pd.DataFrame(rows)