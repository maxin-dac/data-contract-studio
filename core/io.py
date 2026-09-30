from __future__ import annotations

import csv
import io
from typing import Tuple

import pandas as pd

try:
    from charset_normalizer import from_bytes
except ImportError:  # pragma: no cover
    from_bytes = None


DEFAULT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _decode_sample(data: bytes) -> Tuple[str, str]:
    sample = data[:1_000_000]

    if from_bytes is not None:
        best = from_bytes(sample).best()
        if best is not None and best.encoding:
            try:
                return sample.decode(best.encoding), str(best.encoding)
            except Exception:
                pass

    for encoding in DEFAULT_ENCODINGS:
        try:
            return sample.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    return sample.decode("latin-1", errors="replace"), "latin-1"


def _sniff_delimiter(sample: str) -> str:
    sample = sample[:65536]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return str(dialect.delimiter)
    except csv.Error:
        counts = {
            ",": sample.count(","),
            ";": sample.count(";"),
            "\t": sample.count("\t"),
            "|": sample.count("|"),
        }
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def _parse_header(sample_text: str, delimiter: str) -> list[str]:
    reader = csv.reader(io.StringIO(sample_text), delimiter=delimiter)

    for row in reader:
        if row and any(str(cell).strip() for cell in row):
            return [str(col).lstrip("\ufeff") for col in row]

    raise ValueError("CSV file appears empty")


def _make_unique_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []

    for col in columns:
        name = str(col).strip()

        if name in seen:
            seen[name] += 1
            out.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            out.append(name)

    return out


def read_csv_bytes(
    data: bytes,
    max_rows: int = 200_000,
) -> Tuple[pd.DataFrame, bool, str, str]:
    """
    Read CSV bytes with encoding/delimiter detection.

    Returns:
        df: parsed DataFrame
        truncated: whether the file exceeded max_rows
        encoding: detected encoding
        delimiter: detected delimiter
    """
    if not data:
        raise ValueError("Empty CSV file")

    sample_text, encoding = _decode_sample(data)
    delimiter = _sniff_delimiter(sample_text)
    header = _parse_header(sample_text, delimiter)

    # Colonnes temporaires garanties uniques pour éviter que pandas
    # ne renomme lui-même les colonnes dupliquées en "a.1", "b.1", etc.
    temp_columns = [f"__dds_tmp_{i}__" for i in range(len(header))]

    buf = io.BytesIO(data)

    try:
        df = pd.read_csv(
            buf,
            sep=delimiter,
            encoding=encoding,
            engine="python",
            header=None,
            skiprows=1,
            names=temp_columns,
            nrows=max_rows + 1,
        )
    except UnicodeDecodeError:
        encoding = "latin-1"
        buf.seek(0)
        df = pd.read_csv(
            buf,
            sep=delimiter,
            encoding=encoding,
            engine="python",
            header=None,
            skiprows=1,
            names=temp_columns,
            nrows=max_rows + 1,
        )

    truncated = len(df) > max_rows
    if truncated:
        df = df.iloc[:max_rows].copy()

    df.columns = _make_unique_columns(header)

    return df, truncated, encoding, delimiter