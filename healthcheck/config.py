"""
Configuração central do Healthcheck Operacional -> Portal Analítico Modular.

Este módulo concentra:
  - caminhos de entrada/saída
  - parâmetros metodológicos (janelas, dias úteis, benchmarks)
  - sinônimos de colunas para leitura tolerante das bases
  - utilidades de localização das bases

Nada aqui depende de bibliotecas externas. O projeto roda apenas com a
biblioteca padrão do Python (csv, json, datetime, statistics), o que facilita
a execução offline em ambientes corporativos sem permissão para `pip install`.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Raiz do projeto
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Caminho das bases (CSV / xlsx)
# ---------------------------------------------------------------------------
# Ordem de prioridade para localizar a pasta de bases:
#   1) variável de ambiente HEALTHCHECK_BASES
#   2) caminho corporativo do usuário (Windows / OneDrive)
#   3) pasta local ./bases dentro do projeto
#
# O caminho corporativo é o informado pelo usuário. Em outras máquinas ele
# simplesmente não existirá e o projeto cairá no ./bases local.
CORPORATE_BASES = Path(
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
)
LOCAL_BASES = ROOT / "bases"

OUTPUT_DIR = ROOT / "output"
AUDIT_DIR = OUTPUT_DIR / "audit"
PAYLOAD_PATH = OUTPUT_DIR / "payload.json"
HTML_PATH = OUTPUT_DIR / "Healthcheck_BU.html"

FRONTEND_DIR = ROOT / "frontend"


def resolve_bases_dir() -> Path:
    """Resolve a pasta de bases segundo a ordem de prioridade documentada."""
    env = os.environ.get("HEALTHCHECK_BASES")
    if env and Path(env).exists():
        return Path(env)
    if CORPORATE_BASES.exists():
        return CORPORATE_BASES
    return LOCAL_BASES


# ---------------------------------------------------------------------------
# Parâmetros metodológicos
# ---------------------------------------------------------------------------
# Janelas de análise suportadas pelo filtro global "janela".
JANELAS = {
    "mat": {"label": "MAT 12 meses", "meses": 12},
    "ult3m": {"label": "Últimos 3 meses", "meses": 3},
    "mes_fechado": {"label": "Último mês fechado", "meses": 1},
    "mes_atual": {"label": "Mês atual (parcial)", "meses": 0},
}
JANELA_PADRAO = "mat"

# Estimativa de dias úteis por mês quando não houver base de calendário.
DIAS_UTEIS_MES = 21

# Sales Forces a excluir do diagnóstico (ex.: forças descontinuadas).
SALES_FORCES_EXCLUIDAS: set[str] = set()

# ---------------------------------------------------------------------------
# Benchmarks centralizados (semáforo dos indicadores)
# ---------------------------------------------------------------------------
# good  -> verde (>= good)
# warn  -> amarelo (>= warn e < good)
# abaixo de warn -> vermelho
BENCHMARKS = {
    "pct_cobertura_f2f": {"good": 80, "warn": 60, "higher_is_better": True},
    "pct_cobertura_multi": {"good": 85, "warn": 65, "higher_is_better": True},
    "pct_cobertura_mccp": {"good": 80, "warn": 60, "higher_is_better": True},
    "pct_dentro_painel": {"good": 90, "warn": 75, "higher_is_better": True},
    "pct_dentro_mccp": {"good": 85, "warn": 70, "higher_is_better": True},
    "visitas_dia": {"good": 7, "warn": 5, "higher_is_better": True},
    "pct_ausencia": {"good": 5, "warn": 12, "higher_is_better": False},
    "freq_media_medico": {"good": 3, "warn": 1.5, "higher_is_better": True},
    "iaef": {"good": 75, "warn": 50, "higher_is_better": True},
    "icef": {"good": 75, "warn": 50, "higher_is_better": True},
    "ifef": {"good": 70, "warn": 45, "higher_is_better": True},
    "idef": {"good": 30, "warn": 60, "higher_is_better": False},
}


# ---------------------------------------------------------------------------
# Sinônimos de colunas (leitura tolerante)
# ---------------------------------------------------------------------------
# Mapeia o nome canônico -> lista de possíveis cabeçalhos encontrados nas bases.
# A normalização remove acentos, espaços e caixa antes da comparação.
COLUNAS_VISITAS = {
    "data": ["data", "data_visita", "dt_visita", "datavisita", "dataatendimento"],
    "consultor": ["consultor", "representante", "rep", "nome_consultor", "vendedor", "colaborador"],
    "sales_force": ["sales_force", "salesforce", "sf", "forca_vendas", "forcavendas", "linha"],
    "gd": ["gd", "gerente", "gerente_distrital", "gd_nome", "distrital"],
    "mdm": ["mdm", "id_medico", "cod_medico", "codigo_medico", "id_hcp"],
    "crm": ["crm", "crm_medico", "registro"],
    "nome_medico": ["nome_medico", "medico", "hcp", "nome_hcp", "nomemedico"],
    "especialidade": ["especialidade", "espec", "especialidade_primaria", "specialty"],
    "especialidade_sec": ["especialidade_secundaria", "espec_sec", "especialidade2"],
    "canal": ["canal", "tipo_visita", "tipo", "channel", "tipo_contato"],
    "cidade": ["cidade", "municipio", "city"],
    "uf": ["uf", "estado", "sigla_uf", "state"],
    "brick": ["brick", "setor", "microrregiao", "territorio_brick"],
    "no_painel": ["no_painel", "painel", "in_panel", "is_painel"],
    "no_mccp": ["no_mccp", "mccp", "in_mccp", "plano", "is_mccp"],
    "planejado": ["planejado", "planned", "is_planejado", "agendado"],
    "franquia": ["franquia", "franchise", "bu", "unidade_negocio"],
}

COLUNAS_AUSENCIAS = {
    "consultor": ["consultor", "representante", "rep", "nome_consultor", "colaborador"],
    "sales_force": ["sales_force", "salesforce", "sf", "forca_vendas", "linha"],
    "gd": ["gd", "gerente", "gerente_distrital", "distrital"],
    "data_inicio": ["data_inicio", "inicio", "dt_inicio", "data"],
    "data_fim": ["data_fim", "fim", "dt_fim"],
    "dias": ["dias", "qtd_dias", "duracao", "dias_ausencia"],
    "categoria": ["categoria", "tipo_ausencia", "classe"],
    "tipo": ["tipo", "motivo", "descricao"],
}

COLUNAS_PAINEL = {
    "consultor": ["consultor", "representante", "rep", "nome_consultor", "colaborador"],
    "sales_force": ["sales_force", "salesforce", "sf", "forca_vendas", "linha"],
    "gd": ["gd", "gerente", "gerente_distrital", "distrital"],
    "mdm": ["mdm", "id_medico", "cod_medico", "id_hcp"],
    "crm": ["crm", "crm_medico", "registro"],
    "nome_medico": ["nome_medico", "medico", "hcp", "nomemedico"],
    "especialidade": ["especialidade", "espec", "specialty"],
    "especialidade_sec": ["especialidade_secundaria", "espec_sec"],
    "franquia": ["franquia", "franchise", "bu"],
    "no_mccp": ["no_mccp", "mccp", "plano", "is_mccp"],
    "cidade": ["cidade", "municipio"],
    "uf": ["uf", "estado"],
    "brick": ["brick", "setor"],
}

COLUNAS_ESTRUTURA = {
    "consultor": ["consultor", "representante", "rep", "nome_consultor", "colaborador"],
    "sales_force": ["sales_force", "salesforce", "sf", "forca_vendas", "linha"],
    "gd": ["gd", "gerente", "gerente_distrital", "distrital"],
    "cidade_sede": ["cidade_sede", "cidade", "sede", "municipio_sede"],
    "uf_sede": ["uf_sede", "uf", "estado_sede"],
    "tipo_setor": ["tipo_setor", "perfil_setor", "tipo_territorio"],
    "painel_meta": ["painel_meta", "meta_painel", "painel_alvo"],
    "ativo": ["ativo", "status", "afastado"],
}

COLUNAS_FRANQUIAS = {
    "franquia": ["franquia", "franchise", "bu"],
    "especialidade": ["especialidade", "espec", "specialty"],
    "relevancia": ["relevancia", "relevance", "prioridade"],
    "peso": ["peso", "weight"],
    "papel": ["papel", "role"],
    "observacao": ["observacao", "obs", "nota"],
}

# Canais considerados presenciais (F2F).
CANAIS_F2F = {"f2f", "presencial", "face a face", "face_to_face", "visita", "campo"}
# Valores interpretados como verdadeiro em colunas booleanas textuais.
VERDADEIRO = {"1", "true", "sim", "s", "yes", "y", "verdadeiro", "x", "t"}
