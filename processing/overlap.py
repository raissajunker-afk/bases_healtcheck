from __future__ import annotations

from collections import Counter

from processing.utils import pairwise

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


def calcular_overlap(bases: dict, visitas: dict, painel: dict) -> dict:
    doctor_window = pd.DataFrame(visitas.get("doctor_window_metrics", []))
    if doctor_window.empty:
        return {
            "summary": {"pares_com_overlap": 0, "medicos_compartilhados": 0},
            "pairs": [],
            "audit": {"message": "Sem visitas estruturadas para calcular overlap."},
        }

    mat_df = doctor_window.loc[doctor_window["window"] == "mat_12m"].copy()
    if mat_df.empty:
        return {
            "summary": {"pares_com_overlap": 0, "medicos_compartilhados": 0},
            "pairs": [],
            "audit": {"message": "Janela MAT 12m vazia para overlap."},
        }

    overlap_counter: Counter[tuple[str, str]] = Counter()
    doctor_counter = 0
    for _, doctor_group in mat_df.groupby("doctor_id"):
        consultores = doctor_group["consultor"].dropna().astype(str).unique().tolist()
        if len(consultores) <= 1:
            continue
        doctor_counter += 1
        for pair in pairwise(consultores):
            overlap_counter[pair] += 1

    pairs = [
        {
            "consultor_a": pair[0],
            "consultor_b": pair[1],
            "medicos_compartilhados": count,
        }
        for pair, count in overlap_counter.most_common(100)
    ]

    return {
        "summary": {
            "pares_com_overlap": len(pairs),
            "medicos_compartilhados": doctor_counter,
        },
        "pairs": pairs,
        "audit": {
            "pares_top": len(pairs),
        },
    }
