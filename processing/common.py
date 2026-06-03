from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Iterable
import re
import unicodedata


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", without_marks).strip("_").lower()
    return cleaned


def detect_column(headers: Iterable[str], aliases: list[str]) -> str | None:
    lookup = {normalize_key(h): h for h in headers}
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(float(text.replace(",", ".")))
    except ValueError:
        return default


def parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def unique_values(records: Iterable[dict[str, Any]], key: str) -> set[str]:
    values = {
        str(record.get(key, "")).strip()
        for record in records
        if str(record.get(key, "")).strip()
    }
    return values


def top_counter(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    return [{"label": label, "value": value} for label, value in counter.most_common(limit)]


def pct(part: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return (part / total) * 100.0


def to_ascii_slug(value: str) -> str:
    return normalize_key(value or "unknown")
