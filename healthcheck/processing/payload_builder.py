"""Montagem do payload modular consumido pelo frontend.

Estrutura do payload:
{
  "meta": {...},                # informações de geração, fontes, auditoria
  "dimensions": {...},          # listas distintas para os filtros globais
  "datasets": {...},            # arrays de linhas usados pelos blocos
  "summaries": {...},           # agregados globais prontos (KPIs "value")
  "registry": [...],            # seções/subseções/páginas/blocos
}

Os blocos do registry referenciam `datasets` e `summaries` por nome, de modo
que adicionar uma página nova não exige código novo no frontend.
"""

from __future__ import annotations

from datetime import datetime

import config
from processing import registry as registry_mod
from processing import util


def _distinct(rows, field):
    vals = sorted({util.norm_text(r.get(field)) for r in rows if util.norm_text(r.get(field))})
    return vals


def montar_payload(bases, painel, visitas, ausencias, cobertura, territorio, overlap, especialidades, indices) -> dict:
    consultores = indices["consultores"]
    resumo_exec = indices["resumo_executivo"]

    # ---------------- datasets ----------------
    freq_medico = list(visitas.get("medico", {}).values())
    datasets = {
        "consultores": consultores,
        "medicos": cobertura.get("por_medico", []),
        "freq_medico": freq_medico,
        "serie_visitas": visitas.get("serie_mensal", []),
        "serie_consultor": visitas.get("serie_consultor", []),
        "serie_ausencias": ausencias.get("serie_mensal", []),
        "overlap_pares": overlap.get("pares", []),
        "esp_matriz": especialidades.get("matriz", []),
        "esp_franquias": especialidades.get("franquias", []),
        "esp_consultores": especialidades.get("consultores", []),
        "esp_oportunidade": especialidades.get("medicos_oportunidade", []),
    }

    # ---------------- summaries (KPIs "value") ----------------
    esp_resumo = especialidades.get("resumo", {})
    aud_vis = visitas.get("auditoria", {})
    summaries = {
        "executive": resumo_exec,
        "cobertura": cobertura.get("resumo", {}),
        "overlap_resumo": overlap.get("resumo", {}),
        "esp_franquias": {
            "iaef_global": esp_resumo.get("iaef", 0.0),
            "icef_global": esp_resumo.get("icef", 0.0),
            "ifef_global": esp_resumo.get("ifef", 0.0),
            "idef_global": esp_resumo.get("idef", 0.0),
            "sem_classificacao": esp_resumo.get("medicos_sem_classificacao", 0),
            "pct_sem_classificacao": esp_resumo.get("pct_sem_classificacao", 0.0),
        },
        "audit_kv": {
            "visitas_validas": aud_vis.get("visitas_validas", 0),
            "removidas_dedup": aud_vis.get("removidas_dedup", 0),
            "sem_data": aud_vis.get("sem_data", 0),
            "medicos_sem_classificacao": esp_resumo.get("medicos_sem_classificacao", 0),
        },
    }

    # ---------------- dimensions (filtros) ----------------
    dimensions = {
        "gd": _distinct(consultores, "gd"),
        "sales_force": _distinct(consultores, "sales_force"),
        "consultor": _distinct(consultores, "consultor"),
        "janelas": [{"id": k, "label": v["label"]} for k, v in config.JANELAS.items()],
        "janela_padrao": config.JANELA_PADRAO,
    }

    # período coberto pela série mensal
    meses = [s["ym"] for s in datasets["serie_visitas"]]
    periodo = {"inicio": meses[0] if meses else "", "fim": meses[-1] if meses else ""}

    # ---------------- meta / auditoria ----------------
    meta = {
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "titulo": "Healthcheck Operacional — Portal Analítico",
        "origem_painel": painel.get("origem_painel", "vazio"),
        "periodo": periodo,
        "fontes": bases.get("meta", {}),
        "auditoria": {
            "visitas": visitas.get("auditoria", {}),
            "ausencias": ausencias.get("auditoria", {}),
            "especialidades": especialidades.get("auditoria", {}),
            "cobertura_resumo": cobertura.get("resumo", {}),
        },
        "benchmarks": config.BENCHMARKS,
    }

    payload = {
        "meta": meta,
        "dimensions": dimensions,
        "datasets": datasets,
        "summaries": summaries,
        "registry": registry_mod.build_registry(),
    }
    return payload
