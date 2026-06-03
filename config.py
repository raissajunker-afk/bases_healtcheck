"""Configuração do portal Healthcheck — caminhos e saídas."""
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent
HEALTHCHECK_DIR = PROJECT_ROOT / "healthcheck"
BASES_DIR_LOCAL = HEALTHCHECK_DIR / "bases"
OUTPUT_DIR = HEALTHCHECK_DIR

DEFAULT_BASES_WINDOWS = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
)
DEFAULT_OUT_WINDOWS = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck"
)

BASES_PATH = Path(os.environ.get("HEALTHCHECK_BASES_PATH", DEFAULT_BASES_WINDOWS))
if not BASES_PATH.is_dir():
    BASES_PATH = BASES_DIR_LOCAL

OUT_PATH = Path(os.environ.get("HEALTHCHECK_OUT_PATH", DEFAULT_OUT_WINDOWS))
if not OUT_PATH.is_dir():
    OUT_PATH = OUTPUT_DIR

PAYLOAD_PATH = OUT_PATH / "payload.json"
PORTAL_HTML_PATH = OUT_PATH / "Healthcheck_Portal.html"
CONFIG_DIR = PROJECT_ROOT / "app" / "config"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SECTIONS_YAML = CONFIG_DIR / "sections.yaml"
