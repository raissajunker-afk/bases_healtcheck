from __future__ import annotations

from collections import Counter

from config import COLUMN_CANDIDATES, WINDOWS
from processing.utils import clean_dimension_value, infer_column, top_items

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de pandas.") from exc


def _score_absence_dataset(dataset: dict) -> int:
    score = 0
    if dataset["kind"] == "ausencias":
        score += 5
    columns = dataset["columns"]
    if infer_column(columns, COLUMN_CANDIDATES["absence_date"]):
        score += 3
    if infer_column(columns, COLUMN_CANDIDATES["consultor"]):
        score += 2
    return score


def processar_ausencias(bases: dict) -> dict:
    datasets = sorted(
        [dataset for dataset in bases["datasets"].values() if _score_absence_dataset(dataset) > 0],
        key=_score_absence_dataset,
        reverse=True,
    )

    if not datasets:
        return {
            "summary": {"datasets": [], "dias_ausencia": 0},
            "consultor_window_metrics": [],
            "absence_records": [],
            "audit": {"message": "Nenhuma base de ausencias foi identificada."},
        }

    normalized_frames = []
    for dataset in datasets:
        df = dataset["dataframe"].copy()
        consultor_col = infer_column(df.columns, COLUMN_CANDIDATES["consultor"])
        sf_col = infer_column(df.columns, COLUMN_CANDIDATES["sales_force"])
        gd_col = infer_column(df.columns, COLUMN_CANDIDATES["gd"])
        date_col = infer_column(df.columns, COLUMN_CANDIDATES["absence_date"])
        type_col = infer_column(df.columns, COLUMN_CANDIDATES["absence_type"])
        if date_col is None:
            continue

        df["absence_date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=["absence_date"]).copy()
        if df.empty:
            continue

        df["consultor"] = df[consultor_col].map(clean_dimension_value) if consultor_col else "Nao informado"
        df["sales_force"] = df[sf_col].map(clean_dimension_value) if sf_col else "Nao informado"
        df["gd"] = df[gd_col].map(clean_dimension_value) if gd_col else "Nao informado"
        df["absence_type"] = df[type_col].map(clean_dimension_value) if type_col else "Nao informado"
        normalized_frames.append(
            df[["consultor", "sales_force", "gd", "absence_date", "absence_type"]]
        )

    if not normalized_frames:
        return {
            "summary": {"datasets": [], "dias_ausencia": 0},
            "consultor_window_metrics": [],
            "absence_records": [],
            "audit": {"message": "As bases candidatas nao continham datas validas de ausencia."},
        }

    absence_df = pd.concat(normalized_frames, ignore_index=True)
    absence_df["absence_day"] = absence_df["absence_date"].dt.floor("D")
    absence_df = absence_df.drop_duplicates(
        subset=["consultor", "absence_day", "absence_type"]
    ).reset_index(drop=True)

    reference_date = absence_df["absence_date"].max()
    current_month_start = reference_date.replace(day=1)
    previous_month_end = current_month_start - pd.Timedelta(days=1)

    windows_frames = []
    for window_id in WINDOWS:
        if window_id == "mat_12m":
            mask = absence_df["absence_date"] >= reference_date - pd.Timedelta(days=365)
        elif window_id == "last_3m":
            mask = absence_df["absence_date"] >= reference_date - pd.Timedelta(days=90)
        elif window_id == "last_closed_month":
            mask = (
                (absence_df["absence_date"].dt.year == previous_month_end.year)
                & (absence_df["absence_date"].dt.month == previous_month_end.month)
            )
        elif window_id == "current_month_partial":
            mask = (
                (absence_df["absence_date"].dt.year == reference_date.year)
                & (absence_df["absence_date"].dt.month == reference_date.month)
            )
        else:
            mask = pd.Series(False, index=absence_df.index)
        frame = absence_df.loc[mask].copy()
        frame["window"] = window_id
        windows_frames.append(frame)

    windows_df = pd.concat(windows_frames, ignore_index=True)
    consultor_window = (
        windows_df.groupby(["consultor", "sales_force", "gd", "window"], dropna=False)
        .agg(
            dias_ausencia=("absence_day", "nunique"),
            tipos_ausencia=("absence_type", "nunique"),
        )
        .reset_index()
    )
    consultor_window["dias_uteis_referencia"] = consultor_window["window"].map(
        {
            "mat_12m": 252,
            "last_3m": 63,
            "last_closed_month": 21,
            "current_month_partial": 21,
        }
    )
    consultor_window["pct_ausencia"] = (
        consultor_window["dias_ausencia"] / consultor_window["dias_uteis_referencia"].clip(lower=1)
    ).round(4)

    absence_type_counts = Counter(absence_df["absence_type"].tolist())

    return {
        "summary": {
            "datasets": [dataset["name"] for dataset in datasets],
            "dias_ausencia": int(absence_df["absence_day"].nunique()),
            "consultores_com_ausencia": int(absence_df["consultor"].nunique()),
            "top_tipos_ausencia": top_items(absence_type_counts, limit=8),
        },
        "consultor_window_metrics": consultor_window.to_dict(orient="records"),
        "absence_records": absence_df.head(200).assign(
            absence_date=absence_df.head(200)["absence_date"].dt.strftime("%Y-%m-%d")
        ).to_dict(orient="records"),
        "audit": {
            "datasets": [dataset["name"] for dataset in datasets],
            "linhas_pos_deduplicacao": int(len(absence_df)),
        },
    }
