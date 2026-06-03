from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASES_DIR = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
)
LOCAL_BASES_DIR = ROOT_DIR / "bases"
OUTPUT_DIR = ROOT_DIR / "output"
PAYLOAD_PATH = OUTPUT_DIR / "payload.json"
HTML_OUTPUT_PATH = OUTPUT_DIR / "Healthcheck_BU.html"
AUDIT_DIR = OUTPUT_DIR / "audit"

SUPPORTED_EXTENSIONS = (".csv",)
DEFAULT_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp1252", "latin1")

WINDOWS = {
    "mat_12m": "MAT 12m",
    "last_3m": "Ultimos 3m",
    "last_closed_month": "Ultimo mes fechado",
    "current_month_partial": "Mes atual parcial",
}

COLUMN_CANDIDATES = {
    "consultor": [
        "consultor",
        "representante",
        "rep",
        "nome_consultor",
        "consultor_nome",
        "owner",
    ],
    "sales_force": [
        "sales_force",
        "sf",
        "forca_venda",
        "forca_de_venda",
        "frente",
        "time",
    ],
    "gd": [
        "gd",
        "gerente_distrital",
        "distrito",
        "district_manager",
        "gerente",
    ],
    "doctor_id": [
        "mdm",
        "id_medico",
        "cod_medico",
        "codigo_medico",
        "hcp_id",
        "doctor_id",
        "crm",
    ],
    "doctor_name": [
        "nome_medico",
        "medico",
        "doctor_name",
        "nome_hcp",
        "hcp_name",
    ],
    "specialty_primary": [
        "especialidade",
        "especialidade_primaria",
        "specialty",
        "primary_specialty",
    ],
    "specialty_secondary": [
        "especialidade_secundaria",
        "secondary_specialty",
    ],
    "franchise": [
        "franquia",
        "franchise",
        "bu",
        "brand_unit",
    ],
    "mccp_flag": [
        "mccp",
        "target_mccp",
        "alvo_mccp",
        "flag_mccp",
    ],
    "panel_flag": [
        "painel",
        "panel",
        "no_painel",
        "flag_painel",
    ],
    "date": [
        "data",
        "data_visita",
        "visit_date",
        "dt_visita",
        "date",
        "competencia",
    ],
    "channel": [
        "canal",
        "channel",
        "tipo_visita",
        "visit_channel",
    ],
    "city": [
        "cidade",
        "city",
        "municipio",
    ],
    "state": [
        "uf",
        "estado",
        "state",
    ],
    "brick": [
        "brick",
        "microarea",
        "micro_area",
        "territorio",
    ],
    "absence_date": [
        "data",
        "dt_ausencia",
        "data_ausencia",
        "date",
    ],
    "absence_type": [
        "tipo_ausencia",
        "categoria_ausencia",
        "absence_type",
        "motivo",
    ],
}

F2F_TERMS = {
    "f2f",
    "face to face",
    "face-to-face",
    "presencial",
    "fisica",
    "visita presencial",
}


def resolve_bases_dir(custom_dir: str | None = None) -> Path:
    if custom_dir:
        return Path(custom_dir).expanduser()
    if DEFAULT_BASES_DIR.exists():
        return DEFAULT_BASES_DIR
    if LOCAL_BASES_DIR.exists():
        return LOCAL_BASES_DIR
    return DEFAULT_BASES_DIR
