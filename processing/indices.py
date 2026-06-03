from __future__ import annotations

from functools import reduce

from processing.utils import clamp

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


KEYS = ["consultor", "sales_force", "gd", "window"]


def _as_frame(records: list[dict], columns: list[str]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records)


def calcular_indices(
    painel: dict,
    visitas: dict,
    ausencias: dict,
    cobertura: dict,
    territorio: dict,
    overlap: dict,
) -> dict:
    frames = [
        _as_frame(visitas.get("consultor_window_metrics", []), KEYS),
        _as_frame(ausencias.get("consultor_window_metrics", []), KEYS),
        _as_frame(cobertura.get("consultor_window_metrics", []), KEYS),
        _as_frame(territorio.get("consultor_window_metrics", []), KEYS),
    ]
    frames = [frame for frame in frames if not frame.empty]

    if not frames:
        return {
            "consultor_window_metrics": [],
            "summary": {"score_geral": 0.0},
        }

    combined = reduce(
        lambda left, right: left.merge(right, on=KEYS, how="outer"),
        frames,
    ).fillna(0)

    combined["score_produtividade"] = combined.get("visitas_por_dia", 0).map(
        lambda value: round(clamp((float(value) / 8.0) * 100.0), 2)
    )
    combined["score_cobertura"] = combined.get("pct_cobertura_mccp", 0).map(
        lambda value: round(clamp(float(value)), 2)
    )
    combined["score_capacidade"] = combined.get("pct_ausencia", 0).map(
        lambda value: round(clamp(100.0 - (float(value) * 100.0)), 2)
    )
    combined["score_territorio"] = combined.get("score_territorial", 0).map(
        lambda value: round(clamp(float(value)), 2)
    )
    combined["score_geral"] = (
        combined[
            [
                "score_produtividade",
                "score_cobertura",
                "score_capacidade",
                "score_territorio",
            ]
        ]
        .mean(axis=1)
        .round(2)
    )

    return {
        "consultor_window_metrics": combined.to_dict(orient="records"),
        "summary": {
            "score_geral": round(float(combined["score_geral"].mean()), 2),
            "consultores": int(combined["consultor"].nunique()),
        },
    }
