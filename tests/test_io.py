from __future__ import annotations

import pandas as pd
import pytest

from core.io import read_csv_bytes


def test_read_basic_csv():
    data = b"a,b\n1,2\n3,4\n"
    df, truncated, encoding, delimiter = read_csv_bytes(data)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2
    assert truncated is False
    assert delimiter == ","
    assert encoding in {"utf-8", "utf-8-sig", "ascii", "windows-1252", "ISO-8859-1"}


def test_read_semicolon_csv():
    data = "name;age\nAlice;30\nBob;25\n".encode("utf-8")
    df, truncated, encoding, delimiter = read_csv_bytes(data)

    assert delimiter == ";"
    assert list(df.columns) == ["name", "age"]
    assert len(df) == 2
    assert truncated is False


def test_truncation():
    rows = [b"id"] + [str(i).encode() for i in range(10)]
    data = b"\n".join(rows)

    df, truncated, _, _ = read_csv_bytes(data, max_rows=3)

    assert truncated is True
    assert len(df) == 3


def test_duplicate_columns_are_renamed():
    data = b"a,a,b\n1,2,3\n"
    df, _, _, _ = read_csv_bytes(data)

    assert list(df.columns) == ["a", "a_1", "b"]


def test_empty_file_raises():
    with pytest.raises(ValueError):
        read_csv_bytes(b"")