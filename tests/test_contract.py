from __future__ import annotations

import pandas as pd
import yaml

from core.contract import (
    dump_yaml,
    generate_contract,
    load_yaml,
    validate_contract_structure,
)
from core.profiler import profile_dataframe


def test_generate_contract_from_profile():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "email": ["a@b.com", "c@d.fr", "e@f.be"],
            "score": [1, 2, 3],
        }
    )

    profile = profile_dataframe(df, filename="users.csv")
    contract = generate_contract(profile, "users")

    assert contract["name"] == "users"
    assert contract["primary_key"] == ["id"]

    columns = {col["name"]: col for col in contract["columns"]}

    assert columns["id"]["type"] == "integer"
    assert columns["id"]["required"] is True
    assert columns["id"]["unique"] is True

    assert columns["email"]["constraints"]["pattern"] == "email"
    assert columns["score"]["constraints"]["minimum"] == 1
    assert columns["score"]["constraints"]["maximum"] == 3


def test_contract_yaml_roundtrip():
    df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    profile = profile_dataframe(df)
    contract = generate_contract(profile)

    text = dump_yaml(contract)
    loaded = load_yaml(text)

    assert loaded == contract


def test_validate_contract_structure_detects_missing_column():
    contract = {
        "columns": [
            {"name": "id", "type": "integer"},
        ],
        "primary_key": ["missing"],
    }

    errors = validate_contract_structure(contract)
    assert any("missing" in e for e in errors)


def test_validate_contract_structure_detects_bad_type():
    contract = {
        "columns": [
            {"name": "id", "type": "unknown"},
        ],
        "primary_key": [],
    }

    errors = validate_contract_structure(contract)
    assert errors