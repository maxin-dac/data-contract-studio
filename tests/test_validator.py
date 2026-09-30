from __future__ import annotations

import pandas as pd

from core.validator import validate_dataframe


def test_validator_pass_basic():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "score": [10, 20, 30],
        }
    )

    contract = {
        "columns": [
            {
                "name": "id",
                "type": "integer",
                "required": True,
                "unique": True,
            },
            {
                "name": "score",
                "type": "integer",
                "required": True,
                "constraints": {"minimum": 0, "maximum": 100},
            },
        ],
        "primary_key": ["id"],
        "null_thresholds": {"id": 0.0, "score": 0.0},
        "business_rules": [],
        "referential_constraints": [],
    }

    report = validate_dataframe(df, contract)

    assert report.failed == 0
    assert report.score == 1.0


def test_validator_detects_duplicate_primary_key():
    df = pd.DataFrame({"id": [1, 2, 2]})

    contract = {
        "columns": [
            {"name": "id", "type": "integer", "required": True, "unique": True},
        ],
        "primary_key": ["id"],
        "null_thresholds": {"id": 0.0},
    }

    report = validate_dataframe(df, contract)

    unique_results = [r for r in report.results if r.rule_type == "unique"]
    assert unique_results
    assert unique_results[0].status == "fail"
    assert unique_results[0].violations_count == 2


def test_validator_detects_range_violation():
    df = pd.DataFrame({"score": [1, 2, 150]})

    contract = {
        "columns": [
            {
                "name": "score",
                "type": "integer",
                "required": True,
                "constraints": {"maximum": 100},
            },
        ],
        "null_thresholds": {"score": 0.0},
    }

    report = validate_dataframe(df, contract)

    range_results = [r for r in report.results if r.rule_type == "range"]
    assert range_results
    assert range_results[0].status == "fail"
    assert range_results[0].violations_count == 1


def test_validator_conditional_required_rule():
    df = pd.DataFrame(
        {
            "country": ["FR", "DE", "FR"],
            "postal_code": ["75001", None, None],
        }
    )

    contract = {
        "columns": [
            {"name": "country", "type": "string", "required": True},
            {"name": "postal_code", "type": "string", "required": False},
        ],
        "null_thresholds": {"country": 0.0, "postal_code": 1.0},
        "business_rules": [
            {
                "type": "conditional_required",
                "trigger_column": "country",
                "trigger_value": "FR",
                "required_column": "postal_code",
            }
        ],
    }

    report = validate_dataframe(df, contract)

    business_results = [r for r in report.results if r.rule_type == "business_rule"]
    assert business_results
    assert business_results[0].status == "fail"
    assert business_results[0].violations_count == 1