from __future__ import annotations

from typing import Any

import yaml

from .profiler import DatasetProfile


CONTRACT_VERSION = "1.0"

ALLOWED_TYPES = {
    "string",
    "integer",
    "float",
    "boolean",
    "date",
    "datetime",
    "categorical",
}


def generate_contract(
    profile: DatasetProfile,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    pk_candidates = [
        name
        for name, p in profile.columns_profiles.items()
        if p.primary_key_candidate
    ]
    chosen_pk = pk_candidates[0] if pk_candidates else None

    columns: list[dict[str, Any]] = []
    null_thresholds: dict[str, float] = {}

    for name, p in profile.columns_profiles.items():
        required = not p.nullable

        col: dict[str, Any] = {
            "name": name,
            "type": p.dtype,
            "required": required,
            "nullable": p.nullable,
            "unique": p.unique_candidate,
        }

        if chosen_pk and name == chosen_pk:
            col["primary_key"] = True

        constraints: dict[str, Any] = {}

        if p.min is not None:
            constraints["minimum"] = p.min

        if p.max is not None:
            constraints["maximum"] = p.max

        if p.pattern:
            constraints["pattern"] = p.pattern

        if p.min_length is not None:
            constraints["min_length"] = p.min_length

        if p.max_length is not None:
            constraints["max_length"] = p.max_length

        if p.allowed_values:
            constraints["allowed_values"] = p.allowed_values

        if constraints:
            col["constraints"] = constraints

        columns.append(col)

        if required:
            null_thresholds[name] = 0.0
        else:
            null_thresholds[name] = round(min(1.0, p.null_rate + 0.01), 4)

    return {
        "version": CONTRACT_VERSION,
        "name": dataset_name or "dataset",
        "generated_at": profile.generated_at,
        "source": {
            "filename": profile.filename,
            "rows": profile.rows,
            "columns": profile.columns,
        },
        "primary_key": [chosen_pk] if chosen_pk else [],
        "columns": columns,
        "null_thresholds": null_thresholds,
        "business_rules": [],
        "referential_constraints": [],
        "warnings": profile.warnings,
    }


def dump_yaml(contract: dict[str, Any]) -> str:
    return yaml.safe_dump(contract, sort_keys=False, allow_unicode=True)


def load_yaml(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Contract YAML must be a mapping")
    return data


def validate_contract_structure(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(contract, dict):
        return ["Contract must be a mapping"]

    if "columns" not in contract:
        errors.append("Missing required key: columns")
        return errors

    if not isinstance(contract["columns"], list):
        errors.append("Key 'columns' must be a list")
        return errors

    names: list[str] = []

    for idx, col in enumerate(contract["columns"]):
        if not isinstance(col, dict):
            errors.append(f"columns[{idx}] must be a mapping")
            continue

        name = col.get("name")
        if not name:
            errors.append(f"columns[{idx}].name is required")
        elif name in names:
            errors.append(f"Duplicate column name: {name}")
        else:
            names.append(str(name))

        col_type = col.get("type")
        if col_type not in ALLOWED_TYPES:
            errors.append(
                f"columns[{idx}].type '{col_type}' is not supported. "
                f"Allowed: {sorted(ALLOWED_TYPES)}"
            )

    primary_key = contract.get("primary_key", [])
    if not isinstance(primary_key, list):
        errors.append("primary_key must be a list")
    else:
        for pk in primary_key:
            if pk not in names:
                errors.append(f"primary_key column not found in columns: {pk}")

    return errors