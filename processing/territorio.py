from __future__ import annotations

from processing.utils import clamp, safe_div

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


def calcular_territorio(bases: dict, visitas: dict, painel: dict) -> dict:
    consultor_window = pd.DataFrame(visitas.get("consultor_window_metrics", []))
    if consultor_window.empty:
        return {
            "summary": {"score_territorial": 0.0},
            "consultor_window_metrics": [],
            "audit": {"message": "Sem visitas estruturadas para calcular territorio."},
        }

    territory_df = consultor_window[
        [
            "consultor",
            "sales_force",
            "gd",
            "window",
            "cidades_visitadas",
            "ufs_visitadas",
            "bricks_visitados",
            "dias_com_visita",
        ]
    ].copy()

    territory_df["score_territorial"] = territory_df.apply(
        lambda row: round(
            clamp(
                100.0
                - (row["ufs_visitadas"] - 1) * 12.0
                - (row["cidades_visitadas"] - 5) * 2.5
                + safe_div(row["dias_com_visita"], max(row["ufs_visitadas"], 1)) * 3.0,
                0.0,
                100.0,
            ),
            2,
        ),
        axis=1,
    )

    return {
        "summary": {
            "score_territorial": round(float(territory_df["score_territorial"].mean()), 2)
        },
        "consultor_window_metrics": territory_df.to_dict(orient="records"),
        "audit": {
            "consultores_com_territorio": int(territory_df["consultor"].nunique()),
        },
    }
