from __future__ import annotations

import math
import re
import unicodedata
from itertools import combinations
from typing import Iterable


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def slugify(value: object) -> str:
    normalized = normalize_text(value)
    return normalized or "sem_nome"


def infer_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    normalized_candidates = [normalize_text(candidate) for candidate in candidates]
    normalized_columns = {normalize_text(column): column for column in columns}

    for candidate in normalized_candidates:
        if candidate in normalized_columns:
            return normalized_columns[candidate]

    for candidate in normalized_candidates:
        for normalized_column, original_column in normalized_columns.items():
            if candidate and candidate in normalized_column:
                return original_column
    return None


def safe_div(numerator: float | int, denominator: float | int) -> float:
    if denominator in (0, None):
        return 0.0
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def percentile_score(value: float, reference: float) -> float:
    if reference <= 0:
        return 0.0
    return clamp((value / reference) * 100.0)


def coerce_bool(value: object) -> bool:
    normalized = normalize_text(value)
    return normalized in {
        "1",
        "sim",
        "s",
        "yes",
        "y",
        "true",
        "verdadeiro",
        "x",
        "mccp",
        "painel",
    }


def clean_dimension_value(value: object, fallback: str = "Nao informado") -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else fallback


def top_items(counts: dict[str, int], limit: int = 10) -> list[dict]:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"label": key, "value": value} for key, value in ordered[:limit]]


def pairwise(items: Iterable[str]) -> Iterable[tuple[str, str]]:
    return combinations(sorted(set(items)), 2)


def finite_number(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(result) or math.isinf(result):
        return 0.0
    return result
