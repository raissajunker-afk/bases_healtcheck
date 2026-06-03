from __future__ import annotations

from pathlib import Path

from config import DEFAULT_ENCODING_CANDIDATES, SUPPORTED_EXTENSIONS
from processing.utils import normalize_text, slugify

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise RuntimeError(
        "Este projeto precisa de pandas para ler e consolidar os CSVs offline."
    ) from exc


def _read_csv_with_fallback(path: Path) -> tuple[pd.DataFrame, dict]:
    last_error: Exception | None = None
    for encoding in DEFAULT_ENCODING_CANDIDATES:
        for sep in (None, ";", ",", "\t", "|"):
            try:
                kwargs = {"encoding": encoding}
                if sep is None:
                    kwargs.update({"sep": None, "engine": "python"})
                else:
                    kwargs.update({"sep": sep})
                df = pd.read_csv(path, **kwargs)
                if len(df.columns) <= 1 and sep is None:
                    continue
                return df, {"encoding": encoding, "separator": sep or "auto"}
            except Exception as exc:  # noqa: BLE001 - robust CSV fallback
                last_error = exc
    raise RuntimeError(f"Falha ao ler {path}: {last_error}")


def _prepare_dataframe(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    prepared = df.copy()
    prepared.columns = [normalize_text(column) for column in prepared.columns]
    prepared = prepared.rename(
        columns={column: f"coluna_{index}" for index, column in enumerate(prepared.columns) if not column}
    )
    prepared["__source_file__"] = source_name
    return prepared


def _dataset_kind(path: Path) -> str:
    name = normalize_text(path.stem)
    if "visita" in name or "visit" in name:
        return "visitas"
    if "ausencia" in name or "absence" in name:
        return "ausencias"
    if "painel" in name or "mccp" in name or "doctor" in name or "medico" in name:
        return "painel"
    if "franquia" in name or "especialidade" in name:
        return "especialidades"
    return "geral"


def carregar_bases(bases_dir: Path) -> dict:
    if not bases_dir.exists():
        raise FileNotFoundError(
            f"Diretorio de bases nao encontrado: {bases_dir}. "
            "Use --bases-dir para apontar para a pasta correta."
        )

    files = sorted(
        path
        for path in bases_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        raise FileNotFoundError(
            f"Nenhum CSV encontrado em {bases_dir}. Esperado extensoes: {SUPPORTED_EXTENSIONS}"
        )

    datasets: dict[str, dict] = {}
    catalog: list[dict] = []
    warnings: list[str] = []

    for index, path in enumerate(files, start=1):
        dataset_id = slugify(path.stem)
        try:
            raw_df, read_meta = _read_csv_with_fallback(path)
            df = _prepare_dataframe(raw_df, path.name)
            columns = [str(column) for column in df.columns if not str(column).startswith("__")]
            kind = _dataset_kind(path)

            datasets[dataset_id] = {
                "id": dataset_id,
                "name": path.stem,
                "path": str(path),
                "kind": kind,
                "dataframe": df,
                "rows": int(len(df)),
                "columns": columns,
                "read_meta": read_meta,
            }
            catalog.append(
                {
                    "id": dataset_id,
                    "name": path.stem,
                    "path": str(path),
                    "kind": kind,
                    "rows": int(len(df)),
                    "columns": columns,
                    "encoding": read_meta["encoding"],
                    "separator": read_meta["separator"],
                    "order": index,
                }
            )
        except Exception as exc:  # noqa: BLE001 - continue auditing broken files
            warnings.append(f"{path.name}: {exc}")

    if not datasets:
        raise RuntimeError("Nenhuma base foi carregada com sucesso.")

    return {
        "base_dir": str(bases_dir),
        "datasets": datasets,
        "catalog": catalog,
        "warnings": warnings,
    }
