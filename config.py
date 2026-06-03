"""Configuração — bases SEMPRE na subpasta `bases/` do projeto."""
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent
HEALTHCHECK_DIR = PROJECT_ROOT / "healthcheck"

# Pasta bases dentro do healthcheck (conteúdo do 7z)
BASES_LOCAL = HEALTHCHECK_DIR / "bases"
OUT_LOCAL = HEALTHCHECK_DIR

# Caminho no seu PC (OneDrive) — deve apontar para a pasta bases
DEFAULT_BASES_WINDOWS = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
)
DEFAULT_OUT_WINDOWS = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck"
)

def _resolve_bases() -> Path:
    env = os.environ.get("HEALTHCHECK_BASES_PATH")
    if env:
        p = Path(env)
        return p if p.is_dir() else p
    if DEFAULT_BASES_WINDOWS.is_dir():
        return DEFAULT_BASES_WINDOWS
    return BASES_LOCAL


def _resolve_out() -> Path:
    env = os.environ.get("HEALTHCHECK_OUT_PATH")
    if env:
        return Path(env)
    if DEFAULT_OUT_WINDOWS.is_dir():
        return DEFAULT_OUT_WINDOWS
    return OUT_LOCAL


BASES_PATH = _resolve_bases()
OUT_PATH = _resolve_out()

PAYLOAD_PATH = OUT_PATH / "payload.json"
PORTAL_HTML_PATH = OUT_PATH / "Healthcheck_Portal.html"
LEGACY_HTML_GLOB = "Healthcheck_*.html"

CONFIG_DIR = PROJECT_ROOT / "app" / "config"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SECTIONS_JSON = CONFIG_DIR / "sections.json"
LEGACY_PY = HEALTHCHECK_DIR / "gerar_html_legacy.py"
if not LEGACY_PY.exists():
    LEGACY_PY = HEALTHCHECK_DIR / "html (13).py"
