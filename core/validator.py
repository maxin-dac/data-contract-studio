from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from .patterns import PATTERNS


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
class RuleResult:
    rule_id: str
    column: Optional[str]
    rule_type: str
    status: str  # pass | fail | warning
    message: str
    violations_count: int = 0
    sample_violations: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    generated_at: str
    total_rules: int
    passed: int
    failed: int
    warnings: int
    score: float
    results: list[RuleResult]


def _null_mask(series: pd.Series, unify_nulls: bool = True) -> pd.Series:
    mask = series.isna()

    if unify_nulls and (
        pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
    ):
        lowered = series.astype("string").str.strip().str.lower()
        mask = mask | lowered.isin(NULL_TOKENS)

    return mask


def _samples(values: pd.Series, limit: int = 5) -> list[str]:
    return [str(v) for v in values.head(limit).tolist()]


def _type_valid_mask(series: pd.Series, expected: str) -> tuple[pd.Series, list[str]]:
    null_mask = _null_mask(series)
    valid = pd.Series(True, index=series.index)
    values = series[~null_mask]

    if values.empty or expected in {"string", "categorical"}:
        return valid, []

    if expected in {"integer", "float"}:
        numeric = pd.to_numeric(values, errors="coerce")
        bad = numeric.isna()

        if expected == "integer":
            bad = bad | ~(np.abs(numeric - np.round(numeric)) < 1e-9)

        valid.loc[~null_mask] = ~bad.to_numpy()
        return valid, _samples(values[bad])

    if expected in {"date", "datetime"}:
        parsed = pd.to_datetime(values, errors="coerce")
        bad = parsed.isna()
        valid.loc[~null_mask] = ~bad.to_numpy()
        return valid, _samples(values[bad])

    if expected == "boolean":
        normalized = values.astype(str).str.strip().str.lower()
        bad = ~normalized.isin({"true", "false", "yes", "no", "0", "1"})
        valid.loc[~null_mask] = ~bad.to_numpy()
        return valid, _samples(values[bad])

    return valid, []


def _add_result(
    results: list[RuleResult],
    rule_id: str,
    column: Optional[str],
    rule_type: str,
    status: str,
    message: str,
    violations_count: int = 0,
    sample_violations: Optional[list[str]] = None,
) -> None:
    results.append(
        RuleResult(
            rule_id=rule_id,
            column=column,
            rule_type=rule_type,
            status=status,
            message=message,
            violations_count=violations_count,
            sample_violations=sample_violations or [],
        )
    )


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> ValidationReport:
    results: list[RuleResult] = []

    columns_spec = {
        col["name"]: col
        for col in contract.get("columns", [])
        if isinstance(col, dict) and col.get("name")
    }

    primary_key = set(contract.get("primary_key", []) or [])
    null_thresholds = contract.get("null_thresholds", {}) or {}

    # Column existence
    for col_name in columns_spec:
        if col_name not in df.columns:
            _add_result(
                results,
                rule_id=f"column_exists:{col_name}",
                column=col_name,
                rule_type="column_exists",
                status="fail",
                message=f"Column '{col_name}' is missing from dataset",
            )

    for col_name, col_spec in columns_spec.items():
        if col_name not in df.columns:
            continue

        series = df[col_name]
        null_mask = _null_mask(series)
        null_rate = float(null_mask.mean()) if len(series) else 0.0

        required = bool(col_spec.get("required", not col_spec.get("nullable", True)))
        threshold = float(null_thresholds.get(col_name, 0.0 if required else 1.0))

        # Nullability / required
        if required and null_mask.any():
            _add_result(
                results,
                rule_id=f"required:{col_name}",
                column=col_name,
                rule_type="required",
                status="fail",
                message=f"Column '{col_name}' is required but contains null values",
                violations_count=int(null_mask.sum()),
                sample_violations=_samples(series[null_mask]),
            )
        elif null_rate > threshold:
            _add_result(
                results,
                rule_id=f"null_threshold:{col_name}",
                column=col_name,
                rule_type="null_threshold",
                status="fail",
                message=(
                    f"Column '{col_name}' null rate {null_rate:.4f} "
                    f"exceeds threshold {threshold:.4f}"
                ),
                violations_count=int(null_mask.sum()),
            )
        else:
            _add_result(
                results,
                rule_id=f"nullability:{col_name}",
                column=col_name,
                rule_type="nullability",
                status="pass",
                message=f"Column '{col_name}' satisfies nullability rules",
            )

        # Type
        expected_type = col_spec.get("type", "string")
        type_valid, type_violations = _type_valid_mask(series, expected_type)
        type_bad = ~type_valid & ~null_mask
        type_count = int(type_bad.sum())

        if type_count:
            _add_result(
                results,
                rule_id=f"type:{col_name}",
                column=col_name,
                rule_type="type",
                status="fail",
                message=f"Column '{col_name}' contains values incompatible with type '{expected_type}'",
                violations_count=type_count,
                sample_violations=type_violations,
            )
        else:
            _add_result(
                results,
                rule_id=f"type:{col_name}",
                column=col_name,
                rule_type="type",
                status="pass",
                message=f"Column '{col_name}' matches expected type '{expected_type}'",
            )

        # Unique / primary key
        is_unique = bool(col_spec.get("unique", False)) or col_name in primary_key
        if is_unique:
            non_null = series[~null_mask]
            dup_mask = non_null.duplicated(keep=False)
            dup_count = int(dup_mask.sum())

            if dup_count:
                _add_result(
                    results,
                    rule_id=f"unique:{col_name}",
                    column=col_name,
                    rule_type="unique",
                    status="fail",
                    message=f"Column '{col_name}' must be unique but contains duplicated values",
                    violations_count=dup_count,
                    sample_violations=_samples(non_null[dup_mask]),
                )
            else:
                _add_result(
                    results,
                    rule_id=f"unique:{col_name}",
                    column=col_name,
                    rule_type="unique",
                    status="pass",
                    message=f"Column '{col_name}' is unique",
                )

        # Constraints
        constraints = col_spec.get("constraints", {}) or {}
        values = series[~null_mask]

        if "minimum" in constraints or "maximum" in constraints:
            numeric = pd.to_numeric(values, errors="coerce")
            parseable = numeric.notna()
            bad = pd.Series(False, index=values.index)

            if "minimum" in constraints:
                bad = bad | (parseable & (numeric < float(constraints["minimum"])))

            if "maximum" in constraints:
                bad = bad | (parseable & (numeric > float(constraints["maximum"])))

            count = int(bad.sum())
            if count:
                _add_result(
                    results,
                    rule_id=f"range:{col_name}",
                    column=col_name,
                    rule_type="range",
                    status="fail",
                    message=f"Column '{col_name}' violates min/max constraints",
                    violations_count=count,
                    sample_violations=_samples(values[bad]),
                )
            else:
                _add_result(
                    results,
                    rule_id=f"range:{col_name}",
                    column=col_name,
                    rule_type="range",
                    status="pass",
                    message=f"Column '{col_name}' satisfies range constraints",
                )

        if "min_length" in constraints or "max_length" in constraints:
            strings = values.astype(str)
            lengths = strings.str.len()
            bad = pd.Series(False, index=values.index)

            if "min_length" in constraints:
                bad = bad | (lengths < int(constraints["min_length"]))

            if "max_length" in constraints:
                bad = bad | (lengths > int(constraints["max_length"]))

            count = int(bad.sum())
            if count:
                _add_result(
                    results,
                    rule_id=f"length:{col_name}",
                    column=col_name,
                    rule_type="length",
                    status="fail",
                    message=f"Column '{col_name}' violates length constraints",
                    violations_count=count,
                    sample_violations=_samples(values[bad]),
                )
            else:
                _add_result(
                    results,
                    rule_id=f"length:{col_name}",
                    column=col_name,
                    rule_type="length",
                    status="pass",
                    message=f"Column '{col_name}' satisfies length constraints",
                )

        if "pattern" in constraints:
            pattern = constraints["pattern"]
            regex = PATTERNS.get(pattern)
            if regex is None:
                try:
                    regex = re.compile(pattern)
                except re.error:
                    _add_result(
                        results,
                        rule_id=f"pattern:{col_name}",
                        column=col_name,
                        rule_type="pattern",
                        status="warning",
                        message=f"Invalid regex pattern for column '{col_name}': {pattern}",
                    )
                    regex = None

            if regex is not None:
                strings = values.astype(str)
                bad = ~strings.map(lambda x: bool(regex.fullmatch(x)))
                count = int(bad.sum())

                if count:
                    _add_result(
                        results,
                        rule_id=f"pattern:{col_name}",
                        column=col_name,
                        rule_type="pattern",
                        status="fail",
                        message=f"Column '{col_name}' violates pattern '{pattern}'",
                        violations_count=count,
                        sample_violations=_samples(values[bad]),
                    )
                else:
                    _add_result(
                        results,
                        rule_id=f"pattern:{col_name}",
                        column=col_name,
                        rule_type="pattern",
                        status="pass",
                        message=f"Column '{col_name}' satisfies pattern '{pattern}'",
                    )

        if "allowed_values" in constraints:
            allowed = {str(v) for v in constraints["allowed_values"]}
            strings = values.astype(str)
            bad = ~strings.isin(allowed)
            count = int(bad.sum())

            if count:
                _add_result(
                    results,
                    rule_id=f"allowed_values:{col_name}",
                    column=col_name,
                    rule_type="allowed_values",
                    status="fail",
                    message=f"Column '{col_name}' contains values outside allowed set",
                    violations_count=count,
                    sample_violations=_samples(values[bad]),
                )
            else:
                _add_result(
                    results,
                    rule_id=f"allowed_values:{col_name}",
                    column=col_name,
                    rule_type="allowed_values",
                    status="pass",
                    message=f"Column '{col_name}' contains only allowed values",
                )

    # Referential constraints
    for idx, ref in enumerate(contract.get("referential_constraints", []) or []):
        if not isinstance(ref, dict):
            continue

        col_name = ref.get("column")
        reference = ref.get("reference", [])

        if not col_name or col_name not in df.columns:
            _add_result(
                results,
                rule_id=f"referential:{idx}",
                column=col_name,
                rule_type="referential",
                status="fail",
                message=f"Referential constraint {idx} targets missing column '{col_name}'",
            )
            continue

        series = df[col_name]
        null_mask = _null_mask(series)
        values = series[~null_mask].astype(str)
        allowed = {str(v) for v in reference}
        bad = ~values.isin(allowed)
        count = int(bad.sum())

        if count:
            _add_result(
                results,
                rule_id=f"referential:{idx}:{col_name}",
                column=col_name,
                rule_type="referential",
                status="fail",
                message=f"Column '{col_name}' contains values outside reference list",
                violations_count=count,
                sample_violations=_samples(series[~null_mask][bad]),
            )
        else:
            _add_result(
                results,
                rule_id=f"referential:{idx}:{col_name}",
                column=col_name,
                rule_type="referential",
                status="pass",
                message=f"Column '{col_name}' satisfies referential constraint",
            )

    # Business rules MVP
    for idx, rule in enumerate(contract.get("business_rules", []) or []):
        if not isinstance(rule, dict):
            continue

        rule_type = rule.get("type")

        if rule_type == "conditional_required":
            trigger_col = rule.get("trigger_column")
            trigger_val = rule.get("trigger_value")
            required_col = rule.get("required_column")

            if (
                trigger_col not in df.columns
                or required_col not in df.columns
            ):
                _add_result(
                    results,
                    rule_id=f"business:{idx}",
                    column=None,
                    rule_type="business_rule",
                    status="fail",
                    message=f"Business rule {idx} references missing columns",
                )
                continue

            trigger_mask = (
                df[trigger_col].astype(str).str.strip().str.lower()
                == str(trigger_val).strip().lower()
            )
            required_null = _null_mask(df[required_col])
            bad = trigger_mask & required_null
            count = int(bad.sum())

            if count:
                _add_result(
                    results,
                    rule_id=f"business:{idx}:{required_col}",
                    column=required_col,
                    rule_type="business_rule",
                    status="fail",
                    message=(
                        f"When '{trigger_col}' = '{trigger_val}', "
                        f"column '{required_col}' is required"
                    ),
                    violations_count=count,
                    sample_violations=_samples(df.loc[bad, required_col]),
                )
            else:
                _add_result(
                    results,
                    rule_id=f"business:{idx}:{required_col}",
                    column=required_col,
                    rule_type="business_rule",
                    status="pass",
                    message=f"Conditional required rule {idx} satisfied",
                )

        else:
            _add_result(
                results,
                rule_id=f"business:{idx}",
                column=None,
                rule_type="business_rule",
                status="warning",
                message=f"Unsupported business rule type: {rule_type}",
            )

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    warnings = sum(1 for r in results if r.status == "warning")
    denominator = passed + failed
    score = passed / denominator if denominator else 1.0

    return ValidationReport(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        total_rules=len(results),
        passed=passed,
        failed=failed,
        warnings=warnings,
        score=round(score, 4),
        results=results,
    )