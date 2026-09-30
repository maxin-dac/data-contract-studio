from __future__ import annotations

import pandas as pd
import pytest

from core.profiler import profile_dataframe, profile_to_dataframe


def test_profile_numeric_and_unique():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "score": [10.5, 20.0, None],
        }
    )

    profile = profile_dataframe(df, filename="test.csv")

    assert profile.rows == 3
    assert profile.columns == 2
    assert profile.filename == "test.csv"

    id_profile = profile.columns_profiles["id"]
    score_profile = profile.columns_profiles["score"]

    assert id_profile.dtype == "integer"
    assert id_profile.nullable is False
    assert id_profile.unique_candidate is True
    assert id_profile.primary_key_candidate is True

    assert score_profile.dtype == "float"
    assert score_profile.nullable is True
    assert score_profile.null_rate == pytest.approx(1 / 3, abs=1e-6)


def test_profile_email_pattern():
    df = pd.DataFrame(
        {
            "email": ["alice@example.com", "bob@domain.fr"],
        }
    )

    profile = profile_dataframe(df)
    email_profile = profile.columns_profiles["email"]

    assert email_profile.pattern == "email"
    assert email_profile.dtype == "string"


def test_profile_allowed_values_low_cardinality():
    df = pd.DataFrame(
        {
            "country": ["FR", "FR", "DE", "ES"],
        }
    )

    profile = profile_dataframe(df, cat_threshold=10)
    country_profile = profile.columns_profiles["country"]

    assert country_profile.allowed_values == ["DE", "ES", "FR"]


def test_profile_to_dataframe_shape():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    profile = profile_dataframe(df)
    out = profile_to_dataframe(profile)

    assert list(out.columns) == [
        "column",
        "dtype",
        "nullable",
        "null_rate",
        "distinct",
        "unique_candidate",
        "primary_key_candidate",
        "pattern",
        "min",
        "max",
        "allowed_values",
        "flags",
    ]
    assert len(out) == 2