"""
Configuração do Portal Analítico do Healthcheck Operacional.

O motor de processamento é o `processar.py` original (regras de negócio reais:
deduplicação, exclusões de SF, afastados, cobertura ICP-F2F/Multi, MCCP, IPT,
território, overlap etc.). Ele lê as bases brutas e gera `payload.json`.

Este portal:
  1. roda `processar.py` sobre as bases reais  -> payload.json (contrato real)
  2. adapta esse payload para a estrutura modular do portal (datasets/summaries)
  3. gera um HTML self-contained com a navegação Home → Seção → Página.

Sem dependências externas para o portal em si (só stdlib). O `processar.py`
requer pandas/numpy/openpyxl, como no projeto original.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Caminhos das bases / saídas (mesma convenção do processar.py)
# ---------------------------------------------------------------------------
CORPORATE_BASES = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
)
LOCAL_BASES = ROOT / "bases"

OUTPUT_DIR = ROOT / "output"
AUDIT_DIR = OUTPUT_DIR / "audit"
PAYLOAD_PATH = OUTPUT_DIR / "payload.json"           # payload do processar.py (contrato real)
PORTAL_PAYLOAD_PATH = OUTPUT_DIR / "portal_payload.json"  # payload adaptado p/ o portal
HTML_PATH = OUTPUT_DIR / "Healthcheck_Portal.html"

PROCESSAR_PATH = ROOT / "processar.py"
FRONTEND_DIR = ROOT / "frontend"


def resolve_bases_dir() -> Path:
    """Resolve a pasta de bases: env > caminho corporativo > ./bases local."""
    env = os.environ.get("HEALTHCHECK_BASES")
    if env and Path(env).exists():
        return Path(env)
    if CORPORATE_BASES.exists():
        return CORPORATE_BASES
    return LOCAL_BASES


# ---------------------------------------------------------------------------
# Janelas de análise -> sufixo do campo no payload real
# ---------------------------------------------------------------------------
# Os campos do consultor existem em variantes: <base>, <base>_mat, _3m, _1m, _parcial.
JANELAS = {
    "mat": {"label": "MAT 12 meses", "sufixo": "_mat"},
    "ult3m": {"label": "Últimos 3 meses", "sufixo": "_3m"},
    "mes_fechado": {"label": "Último mês fechado", "sufixo": "_1m"},
    "mes_atual": {"label": "Mês atual (parcial)", "sufixo": "_parcial"},
}
JANELA_PADRAO = "mat"

# ---------------------------------------------------------------------------
# Benchmarks centralizados (semáforo) — chaves = campos reais do payload
# ---------------------------------------------------------------------------
BENCHMARKS = {
    "pctCoberturaF2F": {"good": 80, "warn": 60, "higher_is_better": True},
    "pctCoberturaMulti": {"good": 85, "warn": 65, "higher_is_better": True},
    "mccp_pct_cumprido": {"good": 80, "warn": 50, "higher_is_better": True},
    "pct_dentro_mccp": {"good": 85, "warn": 70, "higher_is_better": True},
    "vis_dia_media": {"good": 6, "warn": 4, "higher_is_better": True},
    "pct_ausencia": {"good": 15, "warn": 25, "higher_is_better": False},
    "freq_medico_mes": {"good": 1.0, "warn": 0.5, "higher_is_better": True},
    "ipa_pct": {"good": 80, "warn": 60, "higher_is_better": True},
    "score_territorio": {"good": 70, "warn": 50, "higher_is_better": True},
    "ipt": {"good": 70, "warn": 50, "higher_is_better": True},
    "pct_visitas_uf_sede": {"good": 70, "warn": 50, "higher_is_better": True},
    "pct_cobertura_cidades": {"good": 60, "warn": 40, "higher_is_better": True},
}
