"""
Fase 2 — Enriquece payload.json com camada modular (portal).

Mantém todas as chaves legadas na raiz (html 13.py / portal legado).
Adiciona chave `portal` com dimensions, sections, pages, audit, insights.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

_SECTIONS_PATH = Path(__file__).resolve().parent.parent / "app" / "config" / "sections.json"


def _load_sections_registry() -> dict[str, Any]:
    if _SECTIONS_PATH.exists():
        return json.loads(_SECTIONS_PATH.read_text(encoding="utf-8"))
    return {"sections": []}


def _dim_consultores(consultores: list[dict]) -> list[dict]:
    out = []
    for c in consultores:
        out.append({
            "isid": c.get("ISID"),
            "nome": c.get("nome"),
            "sales_force": c.get("sales_force"),
            "gd_code": c.get("gd_code"),
            "gd_name": c.get("gd_name"),
            "territorio": c.get("territorio"),
            "afastado": bool(c.get("afastado")),
            "painel_size": c.get("painel_size"),
            "vis_dia_media": c.get("vis_dia_media"),
            "pctCoberturaF2F": c.get("pctCoberturaF2F"),
            "pctCoberturaMulti": c.get("pctCoberturaMulti"),
            "mccp_pct_cumprido": c.get("mccp_pct_cumprido"),
            "pct_ausencia": c.get("pct_ausencia"),
            "tipo_setor": c.get("tipo_setor"),
            "score_territorio": c.get("score_territorio"),
        })
    return out


def _rank_consultores(consultores: list[dict], field: str, n: int = 15, reverse: bool = True) -> list[dict]:
    ativos = [c for c in consultores if not c.get("afastado")]
    key_fn = lambda c: c.get(field) or 0
    sorted_cs = sorted(ativos, key=key_fn, reverse=reverse)
    rows = []
    for i, c in enumerate(sorted_cs[:n], 1):
        rows.append({
            "rank": i,
            "isid": c.get("ISID"),
            "nome": c.get("nome"),
            "sales_force": c.get("sales_force"),
            "valor": c.get(field),
        })
    return rows


def _insights_executive(kpis: dict, consultores: list[dict]) -> list[dict]:
    insights = []
    mccp = kpis.get("mccp_pct_cumprido_team")
    if mccp is not None and mccp < 60:
        insights.append({
            "type": "alerta",
            "text": f"MCCP do time em {mccp:.1f}% — abaixo do patamar de 60%.",
        })
    aus = kpis.get("pct_ausencia_media")
    if aus is not None and aus > 25:
        insights.append({
            "type": "risco",
            "text": f"Ausência média do time em {aus:.1f}% — revisar capacidade.",
        })
    ov = kpis.get("overlap_intra_medio")
    if ov is not None and ov > 15:
        insights.append({
            "type": "oportunidade",
            "text": f"Overlap intra médio {ov:.1f}% — avaliar redistribuição de painel.",
        })
    baixa_cob = sum(
        1 for c in consultores
        if not c.get("afastado") and (c.get("pctCoberturaF2F") or 0) < 60
    )
    if baixa_cob:
        insights.append({
            "type": "oportunidade",
            "text": f"{baixa_cob} consultor(es) com cobertura F2F < 60%.",
        })
    if not insights:
        insights.append({
            "type": "tendencia",
            "text": "Indicadores agregados dentro de faixas típicas para o recorte MAT.",
        })
    return insights


def _build_audit(meta: dict, bases_dir: str | None = None) -> dict[str, Any]:
    bases = Path(bases_dir) if bases_dir else None
    arquivos_esperados = [
        "estrutura.xlsx",
        "ausencias_de_campo_visao_geral.csv",
        "relatorio_visitas_24.csv",
        "relatorio_visitas_25.csv",
        "relatorio_visitas_26.csv",
        "relatorio_painel.csv",
        "relatorio_mccp.csv",
        "relatorio_1030.csv",
        "relatorio_brickagem.csv",
    ]
    arquivos = []
    for nome in arquivos_esperados:
        info = {"nome": nome, "encontrado": False, "linhas": None}
        if bases:
            fp = bases / nome
            if fp.exists():
                info["encontrado"] = True
                info["bytes"] = fp.stat().st_size
                if nome.endswith(".csv"):
                    try:
                        with open(fp, encoding="utf-8-sig", errors="ignore") as f:
                            info["linhas"] = sum(1 for _ in f) - 1
                    except Exception:
                        pass
        arquivos.append(info)

    return {
        "gerado_em": meta.get("gerado_em"),
        "janela": meta.get("janela_label"),
        "bu": meta.get("bu"),
        "sfs_excluidas": meta.get("sfs_excluidas", []),
        "bases_dir": str(bases) if bases else None,
        "arquivos": arquivos,
        "observacoes": meta.get("observacoes", {}),
        "dedup_regras": meta.get("observacoes", {}).get("dedup_regras"),
    }


def _section_executive(payload: dict) -> dict[str, Any]:
    k = payload.get("kpis", {})
    cs = payload.get("consultores", [])
    return {
        "summary": {
            "n_consultores": k.get("n_consultores"),
            "painel_medio": k.get("painel_medio"),
            "vis_dia_media": k.get("vis_dia_media"),
            "pct_cobertura_f2f_team": k.get("mccp_pct_cumprido_team"),  # proxy; ICP no consultor
            "mccp_pct_cumprido_team": k.get("mccp_pct_cumprido_team"),
            "pct_ausencia_media": k.get("pct_ausencia_media"),
            "overlap_intra_medio": k.get("overlap_intra_medio"),
        },
        "insights": _insights_executive(k, cs),
        "pages": {
            "snapshot": {
                "cards": [
                    {"id": "n_consultores", "label": "Consultores", "value": k.get("n_consultores"), "format": "int"},
                    {"id": "painel_medio", "label": "Painel médio", "value": k.get("painel_medio"), "format": "decimal"},
                    {"id": "vis_dia", "label": "Visitas/dia", "value": k.get("vis_dia_media"), "format": "decimal"},
                    {"id": "mccp_team", "label": "MCCP % time", "value": k.get("mccp_pct_cumprido_team"), "format": "percent"},
                ],
            },
        },
    }


def _section_performance(payload: dict) -> dict[str, Any]:
    cs = payload.get("consultores", [])
    return {
        "summary": {
            "vis_total_12m": payload.get("kpis", {}).get("vis_total_12m"),
            "vis_dia_media": payload.get("kpis", {}).get("vis_dia_media"),
        },
        "rankings": {
            "top_vis_dia": _rank_consultores(cs, "vis_dia_media"),
            "bottom_vis_dia": _rank_consultores(cs, "vis_dia_media", reverse=False),
            "top_mccp": _rank_consultores(cs, "mccp_pct_cumprido"),
            "bottom_mccp": _rank_consultores(cs, "mccp_pct_cumprido", reverse=False),
        },
        "pages": {
            "por_consultor": {
                "tables": [{"id": "consultores", "rows": len(cs)}],
            },
        },
    }


def _section_cobertura(payload: dict) -> dict[str, Any]:
    cs = payload.get("consultores", [])
    ativos = [c for c in cs if not c.get("afastado")]
    cob_media = (
        sum(c.get("pctCoberturaF2F") or 0 for c in ativos) / len(ativos) if ativos else 0
    )
    multi_media = (
        sum(c.get("pctCoberturaMulti") or 0 for c in ativos) / len(ativos) if ativos else 0
    )
    return {
        "summary": {
            "pct_cobertura_f2f_media": round(cob_media, 1),
            "pct_cobertura_multi_media": round(multi_media, 1),
            "mccp_pct_cumprido_team": payload.get("kpis", {}).get("mccp_pct_cumprido_team"),
            "pct_dentro_mccp_team": payload.get("kpis", {}).get("pct_dentro_mccp_team"),
        },
        "rankings": {
            "menor_cobertura": _rank_consultores(cs, "pctCoberturaF2F", reverse=False),
            "maior_cobertura": _rank_consultores(cs, "pctCoberturaF2F"),
        },
        "pages": {
            "mccp": {"legacyVista": "visitation"},
            "f2f": {"legacyVista": "visitation"},
        },
    }


def _section_oportunidades(payload: dict) -> dict[str, Any]:
    cs = payload.get("consultores", [])
    gaps = []
    for c in cs:
        if c.get("afastado"):
            continue
        painel = c.get("painel_size") or 0
        cob = c.get("pctCoberturaF2F") or 0
        gap_est = painel * (1 - cob / 100) if painel else 0
        if gap_est > 5 or cob < 70:
            gaps.append({
                "isid": c.get("ISID"),
                "nome": c.get("nome"),
                "sales_force": c.get("sales_force"),
                "painel_size": painel,
                "pctCoberturaF2F": cob,
                "mccp_pct_cumprido": c.get("mccp_pct_cumprido"),
                "gap_medicos_estimado": round(gap_est, 0),
                "score_prioridade": round(gap_est * (1 + max(0, 80 - cob) / 100), 1),
            })
    gaps.sort(key=lambda x: -x["score_prioridade"])
    return {
        "summary": {"n_oportunidades": len(gaps)},
        "oportunidades": gaps[:100],
        "insights": [
            {
                "type": "recomendacao",
                "text": "Lista consolidada de gaps de cobertura — não recalcula MCCP (usa payload legado).",
            }
        ],
    }


def _build_pages_registry(sections_cfg: dict) -> dict[str, Any]:
    pages = {}
    for sec in sections_cfg.get("sections", []):
        for sub in sec.get("subsections", []):
            pid = f"{sec['id']}.{sub['id']}"
            pages[pid] = {
                "sectionId": sec["id"],
                "sectionTitle": sec["title"],
                "pageId": sub["id"],
                "title": sub["title"],
                "businessQuestion": sub.get("question"),
                "decisionSupported": sub.get("decision"),
                "legacyVista": sub.get("legacyVista"),
                "legacyAnchor": sub.get("legacyAnchor"),
            }
    return pages


def enriquecer_payload_portal(
    payload: dict[str, Any],
    bases_dir: str | None = None,
) -> dict[str, Any]:
    """
    Adiciona payload['portal'] sem remover chaves legadas.
    """
    sections_cfg = _load_sections_registry()
    meta = payload.get("meta", {})
    consultores = payload.get("consultores", [])

    if bases_dir is None:
        try:
            import processar

            bases_dir = getattr(processar, "BASES_DIR", None)
        except Exception:
            bases_dir = None

    portal = {
        "version": 2,
        "schema": "healthcheck.portal.v2",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dimensions": {
            "consultores": _dim_consultores(consultores),
            "sales_forces": payload.get("sales_forces", []),
            "gds": payload.get("gds", []),
            "n_consultores": len(consultores),
            "n_medicos_meta": len(payload.get("medicos_meta", {})),
        },
        "sections": {
            "executive": _section_executive(payload),
            "performance": _section_performance(payload),
            "cobertura": _section_cobertura(payload),
            "visitacao": {
                "summary": {
                    "freq_dist_mccp": payload.get("freq_dist_mccp"),
                },
                "series": {
                    "visitas_time": payload.get("series_team", {}).get("visitas"),
                    "ausencia_time": payload.get("series_team", {}).get("ausencia"),
                },
            },
            "territorio": {
                "summary": {
                    "n_local": sum(1 for c in consultores if c.get("tipo_setor") == "Local"),
                    "n_viagem": sum(
                        1
                        for c in consultores
                        if c.get("tipo_setor") and "Viagem" in str(c.get("tipo_setor"))
                    ),
                },
            },
            "ausencias": {
                "summary": {"pct_ausencia_media": payload.get("kpis", {}).get("pct_ausencia_media")},
                "series": payload.get("series_team", {}).get("ausencia"),
            },
            "especialidades_franquias": {
                "summary": {},
                "matriz": [],
                "insights": [
                    {
                        "type": "alerta",
                        "text": "Adicione bases/franquias_especialidades.csv e processe na Fase 3.",
                    }
                ],
            },
            "qualidade_execucao": {
                "summary": {
                    "pct_dentro_mccp_team": payload.get("kpis", {}).get("pct_dentro_mccp_team"),
                },
            },
            "overlap": {
                "summary": {
                    "n_pares": len(payload.get("pares_overlap", [])),
                    "overlap_intra_medio": payload.get("kpis", {}).get("overlap_intra_medio"),
                },
                "pares": (payload.get("pares_overlap") or [])[:50],
            },
            "simulador": {
                "summary": {
                    "meta_painel": meta.get("meta_painel_default"),
                    "meta_visitas_dia": meta.get("meta_visitas_dia_default"),
                },
            },
            "oportunidades": _section_oportunidades(payload),
            "governanca": {"audit_ref": "audit"},
            "canal_digital": {
                "summary": {
                    "icp_note": "Detalhe ICP F2F/Multi por consultor em dimensions.consultores",
                },
            },
            "benchmarking": {
                "summary": {
                    "meta_painel": meta.get("meta_painel_default"),
                    "painel_medio": payload.get("kpis", {}).get("painel_medio"),
                    "meta_vis_dia": meta.get("meta_visitas_dia_default"),
                    "vis_dia_media": payload.get("kpis", {}).get("vis_dia_media"),
                },
            },
            "relacionamento": {
                "summary": {"freq_dist_mccp": payload.get("freq_dist_mccp")},
            },
        },
        "pages": _build_pages_registry(sections_cfg),
        "audit": _build_audit(meta, bases_dir),
        "insights_global": _insights_executive(payload.get("kpis", {}), consultores),
    }

    payload["portal"] = portal
    return payload
