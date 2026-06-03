from __future__ import annotations

from collections import Counter

from config import COLUMN_CANDIDATES, F2F_TERMS, WINDOWS
from processing.utils import clean_dimension_value, infer_column, normalize_text, top_items

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


def _score_visit_dataset(dataset: dict) -> int:
    score = 0
    if dataset["kind"] == "visitas":
        score += 5
    columns = dataset["columns"]
    if infer_column(columns, COLUMN_CANDIDATES["date"]):
        score += 3
    if infer_column(columns, COLUMN_CANDIDATES["consultor"]):
        score += 2
    return score


def _select_visit_datasets(bases: dict) -> list[dict]:
    datasets = [dataset for dataset in bases["datasets"].values() if _score_visit_dataset(dataset) > 0]
    return sorted(datasets, key=_score_visit_dataset, reverse=True)


def _previous_month(reference_date):
    current_month_start = reference_date.replace(day=1)
    previous_month_end = current_month_start - pd.Timedelta(days=1)
    return previous_month_end.year, previous_month_end.month


def processar_visitas(bases: dict, painel: dict) -> dict:
    datasets = _select_visit_datasets(bases)
    if not datasets:
        return {
            "summary": {
                "datasets": [],
                "visitas_totais": 0,
                "visitas_f2f": 0,
                "dias_com_visita": 0,
            },
            "consultor_window_metrics": [],
            "doctor_window_metrics": [],
            "monthly_series": [],
            "visit_records": [],
            "audit": {"message": "Nenhuma base de visitas foi identificada."},
        }

    normalized_frames = []
    for dataset in datasets:
        df = dataset["dataframe"].copy()
        consultor_col = infer_column(df.columns, COLUMN_CANDIDATES["consultor"])
        sf_col = infer_column(df.columns, COLUMN_CANDIDATES["sales_force"])
        gd_col = infer_column(df.columns, COLUMN_CANDIDATES["gd"])
        date_col = infer_column(df.columns, COLUMN_CANDIDATES["date"])
        doctor_id_col = infer_column(df.columns, COLUMN_CANDIDATES["doctor_id"])
        doctor_name_col = infer_column(df.columns, COLUMN_CANDIDATES["doctor_name"])
        channel_col = infer_column(df.columns, COLUMN_CANDIDATES["channel"])
        city_col = infer_column(df.columns, COLUMN_CANDIDATES["city"])
        state_col = infer_column(df.columns, COLUMN_CANDIDATES["state"])
        brick_col = infer_column(df.columns, COLUMN_CANDIDATES["brick"])

        if date_col is None:
            continue
        if doctor_id_col is None:
            df["doctor_id_fallback"] = df.index.astype(str)
            doctor_id_col = "doctor_id_fallback"

        df["visit_date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=["visit_date"]).copy()
        if df.empty:
            continue

        df["consultor"] = df[consultor_col].map(clean_dimension_value) if consultor_col else "Nao informado"
        df["sales_force"] = df[sf_col].map(clean_dimension_value) if sf_col else "Nao informado"
        df["gd"] = df[gd_col].map(clean_dimension_value) if gd_col else "Nao informado"
        df["doctor_id"] = df[doctor_id_col].astype(str).str.strip()
        df["doctor_name"] = (
            df[doctor_name_col].map(clean_dimension_value) if doctor_name_col else "Nao informado"
        )
        df["channel"] = df[channel_col].map(clean_dimension_value) if channel_col else "Nao informado"
        df["city"] = df[city_col].map(clean_dimension_value) if city_col else "Nao informado"
        df["state"] = df[state_col].map(clean_dimension_value) if state_col else "Nao informado"
        df["brick"] = df[brick_col].map(clean_dimension_value) if brick_col else "Nao informado"
        df["is_f2f"] = df["channel"].map(lambda value: normalize_text(value) in F2F_TERMS)
        df["source_dataset"] = dataset["name"]
        normalized_frames.append(
            df[
                [
                    "consultor",
                    "sales_force",
                    "gd",
                    "doctor_id",
                    "doctor_name",
                    "visit_date",
                    "channel",
                    "is_f2f",
                    "city",
                    "state",
                    "brick",
                    "source_dataset",
                ]
            ]
        )

    if not normalized_frames:
        return {
            "summary": {
                "datasets": [],
                "visitas_totais": 0,
                "visitas_f2f": 0,
                "dias_com_visita": 0,
            },
            "consultor_window_metrics": [],
            "doctor_window_metrics": [],
            "monthly_series": [],
            "visit_records": [],
            "audit": {"message": "As bases candidatas nao continham datas validas de visita."},
        }

    visits_df = pd.concat(normalized_frames, ignore_index=True)
    visits_df["visit_day"] = visits_df["visit_date"].dt.floor("D")
    visits_df = visits_df.drop_duplicates(
        subset=["consultor", "doctor_id", "visit_day", "channel", "source_dataset"]
    ).reset_index(drop=True)

    reference_date = visits_df["visit_date"].max()
    previous_year, previous_month = _previous_month(reference_date)

    windows_frames = []
    for window_id in WINDOWS:
        if window_id == "mat_12m":
            mask = visits_df["visit_date"] >= reference_date - pd.Timedelta(days=365)
        elif window_id == "last_3m":
            mask = visits_df["visit_date"] >= reference_date - pd.Timedelta(days=90)
        elif window_id == "last_closed_month":
            mask = (
                (visits_df["visit_date"].dt.year == previous_year)
                & (visits_df["visit_date"].dt.month == previous_month)
            )
        elif window_id == "current_month_partial":
            mask = (
                (visits_df["visit_date"].dt.year == reference_date.year)
                & (visits_df["visit_date"].dt.month == reference_date.month)
            )
        else:
            mask = pd.Series(False, index=visits_df.index)
        frame = visits_df.loc[mask].copy()
        frame["window"] = window_id
        windows_frames.append(frame)

    windows_df = pd.concat(windows_frames, ignore_index=True)

    consultor_window = (
        windows_df.groupby(["consultor", "sales_force", "gd", "window"], dropna=False)
        .agg(
            visitas_total=("doctor_id", "size"),
            visitas_f2f=("is_f2f", "sum"),
            dias_com_visita=("visit_day", "nunique"),
            medicos_visitados=("doctor_id", "nunique"),
            cidades_visitadas=("city", "nunique"),
            ufs_visitadas=("state", "nunique"),
            bricks_visitados=("brick", "nunique"),
        )
        .reset_index()
    )
    consultor_window["visitas_por_dia"] = (
        consultor_window["visitas_total"] / consultor_window["dias_com_visita"].clip(lower=1)
    ).round(2)

    doctor_window = (
        windows_df.groupby(
            ["consultor", "sales_force", "gd", "window", "doctor_id", "doctor_name"], dropna=False
        )
        .agg(
            visitas_total=("doctor_id", "size"),
            visitas_f2f=("is_f2f", "sum"),
            ultima_visita=("visit_date", "max"),
        )
        .reset_index()
    )
    doctor_window["teve_f2f"] = doctor_window["visitas_f2f"] > 0
    doctor_window["ultima_visita"] = doctor_window["ultima_visita"].dt.strftime("%Y-%m-%d")

    monthly_series = (
        visits_df.assign(month=visits_df["visit_date"].dt.to_period("M").astype(str))
        .groupby("month", dropna=False)
        .agg(visitas_total=("doctor_id", "size"), medicos_visitados=("doctor_id", "nunique"))
        .reset_index()
        .sort_values("month")
    )

    channel_counts = Counter(visits_df["channel"].tolist())

    summary = {
        "datasets": [dataset["name"] for dataset in datasets],
        "visitas_totais": int(len(visits_df)),
        "visitas_f2f": int(visits_df["is_f2f"].sum()),
        "dias_com_visita": int(visits_df["visit_day"].nunique()),
        "consultores_com_visita": int(visits_df["consultor"].nunique()),
        "medicos_visitados": int(visits_df["doctor_id"].nunique()),
        "top_canais": top_items(channel_counts, limit=8),
        "data_referencia": reference_date.strftime("%Y-%m-%d"),
    }

    return {
        "summary": summary,
        "consultor_window_metrics": consultor_window.to_dict(orient="records"),
        "doctor_window_metrics": doctor_window.to_dict(orient="records"),
        "monthly_series": monthly_series.to_dict(orient="records"),
        "visit_records": visits_df.head(200).assign(
            visit_date=visits_df.head(200)["visit_date"].dt.strftime("%Y-%m-%d")
        ).to_dict(orient="records"),
        "audit": {
            "datasets": [dataset["name"] for dataset in datasets],
            "linhas_pos_deduplicacao": int(len(visits_df)),
            "colunas_inferidas": {
                "consultor": infer_column(visits_df.columns, ["consultor"]),
                "doctor_id": infer_column(visits_df.columns, ["doctor_id"]),
                "visit_date": infer_column(visits_df.columns, ["visit_date"]),
            },
        },
    }
