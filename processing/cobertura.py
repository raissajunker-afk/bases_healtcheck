from __future__ import annotations

from processing.utils import safe_div

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


def calcular_cobertura(bases: dict, painel: dict, visitas: dict) -> dict:
    panel_records = painel.get("panel_records", [])
    doctor_window_metrics = visitas.get("doctor_window_metrics", [])

    if not panel_records:
        return {
            "summary": {"cobertura_f2f": 0.0, "cobertura_multi": 0.0},
            "consultor_window_metrics": [],
            "opportunity_doctors": [],
            "specialty_franchise_metrics": [],
            "audit": {"message": "Sem painel estruturado para calcular cobertura."},
        }

    panel_df = pd.DataFrame(panel_records)
    visits_df = pd.DataFrame(doctor_window_metrics)

    if visits_df.empty:
        panel_windows = []
        for window_id in ("mat_12m", "last_3m", "last_closed_month", "current_month_partial"):
            temp = panel_df.copy()
            temp["window"] = window_id
            panel_windows.append(temp)
        panel_windows_df = pd.concat(panel_windows, ignore_index=True)
        merged = panel_windows_df.copy()
        merged["visitas_total"] = 0
        merged["teve_f2f"] = False
    else:
        panel_windows = []
        for window_id in visits_df["window"].dropna().unique().tolist():
            temp = panel_df.copy()
            temp["window"] = window_id
            panel_windows.append(temp)
        panel_windows_df = pd.concat(panel_windows, ignore_index=True)
        merged = panel_windows_df.merge(
            visits_df[
                [
                    "consultor",
                    "sales_force",
                    "gd",
                    "window",
                    "doctor_id",
                    "visitas_total",
                    "teve_f2f",
                    "ultima_visita",
                ]
            ],
            on=["consultor", "sales_force", "gd", "window", "doctor_id"],
            how="left",
        )
        merged["visitas_total"] = merged["visitas_total"].fillna(0)
        merged["teve_f2f"] = merged["teve_f2f"].fillna(False)

    merged["coberto_multi"] = merged["visitas_total"] > 0
    merged["coberto_f2f"] = merged["teve_f2f"]
    merged["mccp_coberto_f2f"] = merged["mccp_flag"] & merged["coberto_f2f"]

    consultor_window = (
        merged.groupby(["consultor", "sales_force", "gd", "window"], dropna=False)
        .agg(
            medicos_painel=("doctor_id", "nunique"),
            medicos_mccp=("mccp_flag", "sum"),
            medicos_cobertos_multi=("coberto_multi", "sum"),
            medicos_cobertos_f2f=("coberto_f2f", "sum"),
            medicos_mccp_cobertos_f2f=("mccp_coberto_f2f", "sum"),
        )
        .reset_index()
    )
    consultor_window["pct_cobertura_multi"] = consultor_window.apply(
        lambda row: round(
            safe_div(row["medicos_cobertos_multi"], row["medicos_painel"]) * 100.0, 2
        ),
        axis=1,
    )
    consultor_window["pct_cobertura_f2f"] = consultor_window.apply(
        lambda row: round(
            safe_div(row["medicos_cobertos_f2f"], row["medicos_painel"]) * 100.0, 2
        ),
        axis=1,
    )
    consultor_window["pct_cobertura_mccp"] = consultor_window.apply(
        lambda row: round(
            safe_div(row["medicos_mccp_cobertos_f2f"], row["medicos_mccp"]) * 100.0, 2
        ),
        axis=1,
    )

    mat_df = merged.loc[merged["window"] == "mat_12m"].copy()
    opportunities = mat_df.loc[~mat_df["coberto_multi"]].copy()
    opportunities["dias_desde_ultima_visita"] = opportunities["ultima_visita"].fillna("sem_visita")

    specialty_franchise = (
        mat_df.groupby(["franchise", "specialty_primary"], dropna=False)
        .agg(
            medicos_painel=("doctor_id", "nunique"),
            medicos_cobertos=("coberto_multi", "sum"),
            medicos_f2f=("coberto_f2f", "sum"),
            medicos_mccp=("mccp_flag", "sum"),
        )
        .reset_index()
    )
    specialty_franchise["pct_cobertura"] = specialty_franchise.apply(
        lambda row: round(safe_div(row["medicos_cobertos"], row["medicos_painel"]) * 100.0, 2),
        axis=1,
    )

    summary = {
        "cobertura_f2f": round(float(consultor_window["pct_cobertura_f2f"].mean()), 2)
        if not consultor_window.empty
        else 0.0,
        "cobertura_multi": round(float(consultor_window["pct_cobertura_multi"].mean()), 2)
        if not consultor_window.empty
        else 0.0,
        "cobertura_mccp": round(float(consultor_window["pct_cobertura_mccp"].mean()), 2)
        if not consultor_window.empty
        else 0.0,
    }

    return {
        "summary": summary,
        "consultor_window_metrics": consultor_window.to_dict(orient="records"),
        "opportunity_doctors": opportunities[
            [
                "consultor",
                "sales_force",
                "gd",
                "doctor_id",
                "doctor_name",
                "specialty_primary",
                "specialty_secondary",
                "franchise",
                "mccp_flag",
                "dias_desde_ultima_visita",
            ]
        ]
        .head(200)
        .to_dict(orient="records"),
        "specialty_franchise_metrics": specialty_franchise.head(200).to_dict(orient="records"),
        "audit": {
            "medicos_sem_cobertura_mat": int((~mat_df["coberto_multi"]).sum()) if not mat_df.empty else 0,
        },
    }
