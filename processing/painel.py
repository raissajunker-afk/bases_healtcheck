from __future__ import annotations

from collections import Counter

from config import COLUMN_CANDIDATES
from processing.utils import clean_dimension_value, coerce_bool, infer_column, top_items

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


def _score_panel_dataset(dataset: dict) -> int:
    score = 0
    if dataset["kind"] == "painel":
        score += 5
    columns = dataset["columns"]
    if infer_column(columns, COLUMN_CANDIDATES["doctor_id"]):
        score += 4
    if infer_column(columns, COLUMN_CANDIDATES["consultor"]):
        score += 2
    if infer_column(columns, COLUMN_CANDIDATES["mccp_flag"]):
        score += 2
    return score


def _select_panel_dataset(bases: dict) -> dict | None:
    candidates = sorted(
        bases["datasets"].values(),
        key=_score_panel_dataset,
        reverse=True,
    )
    if not candidates or _score_panel_dataset(candidates[0]) <= 0:
        return None
    return candidates[0]


def processar_painel(bases: dict) -> dict:
    dataset = _select_panel_dataset(bases)
    if dataset is None:
        return {
            "summary": {
                "dataset": None,
                "consultores_ativos": 0,
                "medicos_painel": 0,
                "medicos_mccp": 0,
            },
            "consultor_metrics": [],
            "panel_records": [],
            "doctor_sample": [],
            "dimensions": {"consultores": [], "sales_forces": [], "gds": []},
            "audit": {"message": "Nenhuma base de painel/MCCP foi identificada."},
        }

    df = dataset["dataframe"].copy()
    consultor_col = infer_column(df.columns, COLUMN_CANDIDATES["consultor"])
    sf_col = infer_column(df.columns, COLUMN_CANDIDATES["sales_force"])
    gd_col = infer_column(df.columns, COLUMN_CANDIDATES["gd"])
    doctor_id_col = infer_column(df.columns, COLUMN_CANDIDATES["doctor_id"])
    doctor_name_col = infer_column(df.columns, COLUMN_CANDIDATES["doctor_name"])
    mccp_col = infer_column(df.columns, COLUMN_CANDIDATES["mccp_flag"])
    panel_col = infer_column(df.columns, COLUMN_CANDIDATES["panel_flag"])
    specialty_primary_col = infer_column(df.columns, COLUMN_CANDIDATES["specialty_primary"])
    specialty_secondary_col = infer_column(df.columns, COLUMN_CANDIDATES["specialty_secondary"])
    franchise_col = infer_column(df.columns, COLUMN_CANDIDATES["franchise"])

    if doctor_id_col is None:
        df["doctor_id_fallback"] = df.index.astype(str)
        doctor_id_col = "doctor_id_fallback"

    df["consultor"] = df[consultor_col].map(clean_dimension_value) if consultor_col else "Nao informado"
    df["sales_force"] = df[sf_col].map(clean_dimension_value) if sf_col else "Nao informado"
    df["gd"] = df[gd_col].map(clean_dimension_value) if gd_col else "Nao informado"
    df["doctor_id"] = df[doctor_id_col].astype(str).str.strip()
    df["doctor_name"] = (
        df[doctor_name_col].map(clean_dimension_value) if doctor_name_col else "Nao informado"
    )
    df["mccp_flag"] = df[mccp_col].map(coerce_bool) if mccp_col else False
    df["panel_flag"] = df[panel_col].map(coerce_bool) if panel_col else True
    df["specialty_primary"] = (
        df[specialty_primary_col].map(clean_dimension_value)
        if specialty_primary_col
        else "sem_classificacao"
    )
    df["specialty_secondary"] = (
        df[specialty_secondary_col].map(clean_dimension_value)
        if specialty_secondary_col
        else "sem_classificacao"
    )
    df["franchise"] = (
        df[franchise_col].map(clean_dimension_value) if franchise_col else "Nao informado"
    )

    panel_df = (
        df[
            [
                "consultor",
                "sales_force",
                "gd",
                "doctor_id",
                "doctor_name",
                "mccp_flag",
                "panel_flag",
                "specialty_primary",
                "specialty_secondary",
                "franchise",
            ]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    by_consultor = (
        panel_df.groupby(["consultor", "sales_force", "gd"], dropna=False)
        .agg(
            medicos_painel=("doctor_id", "nunique"),
            medicos_mccp=("mccp_flag", "sum"),
            especialidades_validas=("specialty_primary", lambda values: int((values != "sem_classificacao").sum())),
        )
        .reset_index()
    )
    by_consultor["painel_medio"] = by_consultor["medicos_painel"]

    specialty_counts = Counter(panel_df["specialty_primary"].tolist())

    summary = {
        "dataset": dataset["name"],
        "consultores_ativos": int(panel_df["consultor"].nunique()),
        "medicos_painel": int(panel_df["doctor_id"].nunique()),
        "medicos_mccp": int(panel_df.loc[panel_df["mccp_flag"], "doctor_id"].nunique()),
        "top_especialidades": top_items(specialty_counts, limit=8),
    }

    dimensions = {
        "consultores": sorted(panel_df["consultor"].dropna().astype(str).unique().tolist()),
        "sales_forces": sorted(panel_df["sales_force"].dropna().astype(str).unique().tolist()),
        "gds": sorted(panel_df["gd"].dropna().astype(str).unique().tolist()),
    }

    return {
        "summary": summary,
        "consultor_metrics": by_consultor.to_dict(orient="records"),
        "panel_records": panel_df.to_dict(orient="records"),
        "doctor_sample": panel_df.head(200).to_dict(orient="records"),
        "dimensions": dimensions,
        "audit": {
            "dataset": dataset["name"],
            "linhas_origem": dataset["rows"],
            "linhas_unicas": int(len(panel_df)),
            "colunas": dataset["columns"],
        },
    }
