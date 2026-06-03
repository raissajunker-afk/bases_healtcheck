"""Fase 3 — blocos nativos por página no payload.portal."""
from __future__ import annotations

from typing import Any


def _rank_table(title: str, rows: list, fname: str, val_label: str) -> dict:
    return {
        "type": "table",
        "title": title,
        "exportCsv": fname,
        "columns": [
            {"key": "rank", "label": "#", "num": True},
            {"key": "nome", "label": "Consultor"},
            {"key": "sales_force", "label": "SF"},
            {"key": "valor", "label": val_label, "num": True, "format": "decimal"},
        ],
        "rows": rows,
    }


def attach_native_blocks(portal: dict[str, Any], payload: dict[str, Any]) -> None:
    sections = portal["sections"]
    k = payload.get("kpis", {})
    meta = payload.get("meta", {})
    cs = payload.get("consultores", [])

    # --- Executive ---
    ex = sections["executive"]
    s = ex["summary"]
    ex.setdefault("pages", {})
    ex["pages"]["snapshot"] = {
        "blocks": [
            {
                "type": "kpi_row",
                "title": "Indicadores principais",
                "items": [
                    {"label": "Consultores ativos", "value": s.get("n_consultores"), "format": "int"},
                    {"label": "Painel médio", "value": s.get("painel_medio"), "format": "decimal"},
                    {"label": "Visitas/dia", "value": s.get("vis_dia_media"), "format": "decimal", "good": 5, "warn": 4},
                    {"label": "MCCP % time", "value": s.get("mccp_pct_cumprido_team"), "format": "percent", "good": 80, "warn": 60},
                    {"label": "% Ausência", "value": s.get("pct_ausencia_media"), "format": "percent", "invert": True, "good": 20, "warn": 25},
                    {"label": "Overlap intra", "value": s.get("overlap_intra_medio"), "format": "percent", "invert": True, "good": 10, "warn": 15},
                ],
            },
            {"type": "insight", "title": "Leitura automática", "items": ex.get("insights", [])},
            {"type": "legacy_link", "vista": "overview", "anchor": "kpi-grid"},
        ]
    }

    alert_rows = [
        {
            "nome": c.get("nome"),
            "sales_force": c.get("sales_force"),
            "pctCoberturaF2F": c.get("pctCoberturaF2F"),
            "mccp_pct_cumprido": c.get("mccp_pct_cumprido"),
            "pct_ausencia": c.get("pct_ausencia"),
        }
        for c in cs
        if not c.get("afastado")
        and ((c.get("pctCoberturaF2F") or 100) < 60 or (c.get("mccp_pct_cumprido") or 100) < 50)
    ][:25]
    ex["pages"]["alertas"] = {
        "blocks": [
            {"type": "insight", "title": "Alertas", "items": ex.get("insights", [])},
            {
                "type": "table",
                "title": "Consultores em atenção",
                "exportCsv": "alertas_consultores.csv",
                "columns": [
                    {"key": "nome", "label": "Consultor"},
                    {"key": "sales_force", "label": "SF"},
                    {"key": "pctCoberturaF2F", "label": "Cob F2F%", "num": True, "format": "percent"},
                    {"key": "mccp_pct_cumprido", "label": "MCCP%", "num": True, "format": "percent"},
                    {"key": "pct_ausencia", "label": "Ausência%", "num": True, "format": "percent"},
                ],
                "rows": alert_rows,
            },
            {"type": "legacy_link", "vista": "overview"},
        ]
    }

    visitas_series = (sections.get("visitacao", {}).get("series") or {}).get("visitas_time") or []
    chart_vis = [
        {
            "label": str(x.get("mes") or x.get("ym") or "")[:7],
            "value": x.get("valor") or x.get("visitas") or x.get("v"),
        }
        for x in (visitas_series[-12:] if isinstance(visitas_series, list) else [])
    ]
    ex["pages"]["evolucao"] = {
        "blocks": [
            {"type": "bar_chart", "title": "Visitas — série time (MAT)", "series": chart_vis},
            {"type": "legacy_link", "vista": "timeline"},
        ]
    }

    sf_rows = payload.get("sales_forces", [])
    ex["pages"]["resumo_sf"] = {
        "blocks": [
            {
                "type": "table",
                "title": "Resumo por Sales Force",
                "exportCsv": "resumo_sf.csv",
                "columns": [
                    {"key": "nome", "label": "SF"},
                    {"key": "n_consultores", "label": "REPs", "num": True, "format": "int"},
                    {"key": "painel_medio", "label": "Painel méd.", "num": True, "format": "decimal"},
                    {"key": "vis_dia_media", "label": "Vis/dia", "num": True, "format": "decimal"},
                ],
                "rows": [
                    {
                        "nome": r.get("nome") or r.get("sales_force"),
                        "n_consultores": r.get("n_consultores"),
                        "painel_medio": r.get("painel_medio") or r.get("painel_media"),
                        "vis_dia_media": r.get("vis_dia_media"),
                    }
                    for r in sf_rows
                ],
            },
            {"type": "legacy_link", "vista": "overview", "anchor": "sf-block"},
        ]
    }

    gd_rows = payload.get("gds", [])
    ex["pages"]["resumo_gd"] = {
        "blocks": [
            {
                "type": "table",
                "title": "Resumo por GD",
                "exportCsv": "resumo_gd.csv",
                "columns": [
                    {"key": "nome", "label": "GD"},
                    {"key": "n_consultores", "label": "REPs", "num": True, "format": "int"},
                    {"key": "vis_dia_media", "label": "Vis/dia média", "num": True, "format": "decimal"},
                ],
                "rows": [
                    {
                        "nome": r.get("nome") or r.get("gd_name"),
                        "n_consultores": r.get("n_consultores"),
                        "vis_dia_media": r.get("vis_dia_media"),
                    }
                    for r in gd_rows
                ],
            },
            {"type": "legacy_link", "vista": "overview", "anchor": "gd-summary-block"},
        ]
    }

    # --- Performance ---
    perf = sections["performance"]
    rk = perf.get("rankings", {})
    perf.setdefault("pages", {})
    perf["pages"]["geral"] = {
        "blocks": [
            {
                "type": "kpi_row",
                "title": "Produtividade",
                "items": [
                    {"label": "Visitas MAT", "value": k.get("vis_total_12m"), "format": "int"},
                    {"label": "Vis/dia média", "value": k.get("vis_dia_media"), "format": "decimal"},
                    {"label": "Meta vis/dia", "value": meta.get("meta_visitas_dia_default"), "format": "decimal"},
                ],
            },
            {"type": "legacy_link", "vista": "visitation"},
        ]
    }
    perf["pages"]["por_consultor"] = {
        "blocks": [
            _rank_table("Consultores — visitas/dia", rk.get("top_vis_dia", [])[:20], "consultores_vis_dia.csv", "Vis/dia"),
            {"type": "legacy_link", "vista": "detail"},
        ]
    }
    perf["pages"]["alta"] = {
        "blocks": [
            _rank_table("Top visitas/dia", rk.get("top_vis_dia", [])[:15], "top_vis_dia.csv", "Vis/dia"),
            _rank_table("Top MCCP %", rk.get("top_mccp", [])[:15], "top_mccp.csv", "MCCP%"),
            {"type": "legacy_link", "vista": "detail"},
        ]
    }
    perf["pages"]["baixa"] = {
        "blocks": [
            _rank_table("Menor visitas/dia", rk.get("bottom_vis_dia", [])[:15], "bottom_vis_dia.csv", "Vis/dia"),
            _rank_table("Menor MCCP %", rk.get("bottom_mccp", [])[:15], "bottom_mccp.csv", "MCCP%"),
            {"type": "legacy_link", "vista": "detail"},
        ]
    }

    # --- Cobertura ---
    cob = sections["cobertura"]
    cs_summ = cob["summary"]
    cob.setdefault("pages", {})
    cob["pages"]["mccp"] = {
        "blocks": [
            {
                "type": "kpi_row",
                "title": "MCCP e plano",
                "items": [
                    {"label": "MCCP % cumprido", "value": cs_summ.get("mccp_pct_cumprido_team"), "format": "percent", "good": 80, "warn": 60},
                    {"label": "% dentro MCCP", "value": cs_summ.get("pct_dentro_mccp_team"), "format": "percent"},
                ],
            },
            _rank_table("Menor cobertura F2F", cob.get("rankings", {}).get("menor_cobertura", []), "menor_cobertura.csv", "Cob%"),
            {"type": "legacy_link", "vista": "visitation"},
        ]
    }
    cob["pages"]["f2f"] = {
        "blocks": [
            {
                "type": "kpi_row",
                "title": "Cobertura",
                "items": [
                    {"label": "F2F média", "value": cs_summ.get("pct_cobertura_f2f_media"), "format": "percent", "good": 80, "warn": 60},
                    {"label": "Multicanal média", "value": cs_summ.get("pct_cobertura_multi_media"), "format": "percent"},
                ],
            },
            _rank_table("Maior cobertura F2F", cob.get("rankings", {}).get("maior_cobertura", []), "maior_cobertura.csv", "Cob%"),
            {"type": "legacy_link", "vista": "visitation"},
        ]
    }
    parados = sorted(
        [c for c in cs if not c.get("afastado")],
        key=lambda c: c.get("pctCoberturaF2F") or 0,
    )[:30]
    cob["pages"]["parados"] = {
        "blocks": [
            {
                "type": "table",
                "title": "Menor cobertura F2F (ativação)",
                "exportCsv": "medicos_baixa_cobertura.csv",
                "columns": [
                    {"key": "nome", "label": "Consultor"},
                    {"key": "painel_size", "label": "Painel", "num": True, "format": "int"},
                    {"key": "pctCoberturaF2F", "label": "Cob F2F%", "num": True, "format": "percent"},
                    {"key": "mccp_pct_cumprido", "label": "MCCP%", "num": True, "format": "percent"},
                ],
                "rows": [
                    {
                        "nome": c.get("nome"),
                        "painel_size": c.get("painel_size"),
                        "pctCoberturaF2F": c.get("pctCoberturaF2F"),
                        "mccp_pct_cumprido": c.get("mccp_pct_cumprido"),
                    }
                    for c in parados
                ],
            },
            {"type": "legacy_link", "vista": "detail"},
        ]
    }

    # --- Oportunidades ---
    op = sections["oportunidades"]
    opps = op.get("oportunidades", [])[:50]
    op.setdefault("pages", {})
    op_page = {
        "blocks": [
            {"type": "insight", "title": "Priorização", "items": op.get("insights", [])},
            {
                "type": "table",
                "title": "Ranking de oportunidades (score)",
                "exportCsv": "oportunidades_prioritarias.csv",
                "columns": [
                    {"key": "nome", "label": "Consultor"},
                    {"key": "sales_force", "label": "SF"},
                    {"key": "pctCoberturaF2F", "label": "Cob F2F%", "num": True, "format": "percent"},
                    {"key": "gap_medicos_estimado", "label": "Gap médicos", "num": True, "format": "int"},
                    {"key": "score_prioridade", "label": "Score", "num": True, "format": "decimal"},
                ],
                "rows": opps,
            },
            {"type": "legacy_link", "vista": "detail"},
        ]
    }
    op["pages"]["prioritarias"] = op_page
    op["pages"]["por_consultor"] = op_page
    op["pages"]["ativacao"] = cob["pages"]["parados"]

    # --- Visitação ---
    vis = sections["visitacao"]
    fd = payload.get("freq_dist_mccp") or {}
    freq_series = [{"label": str(lbl), "value": v} for lbl, v in fd.items()]
    vis.setdefault("pages", {})
    vis["pages"]["frequencia"] = {
        "blocks": [
            {"type": "bar_chart", "title": "Distribuição frequência MCCP", "series": freq_series},
            {"type": "legacy_link", "vista": "visitation"},
        ]
    }

    # --- Ausências ---
    aus = sections["ausencias"]
    aus_series = aus.get("series") or []
    chart_aus = []
    if isinstance(aus_series, list):
        chart_aus = [
            {
                "label": str(x.get("mes") or x.get("ym") or "")[:7],
                "value": x.get("valor") or x.get("pct") or x.get("v"),
            }
            for x in aus_series[-12:]
        ]
    aus.setdefault("pages", {})
    aus["pages"]["total"] = {
        "blocks": [
            {
                "type": "kpi_row",
                "title": "Ausência",
                "items": [
                    {
                        "label": "% Ausência média",
                        "value": aus.get("summary", {}).get("pct_ausencia_media"),
                        "format": "percent",
                        "invert": True,
                        "good": 20,
                        "warn": 25,
                    },
                ],
            },
            {"type": "bar_chart", "title": "Série ausência time", "series": chart_aus},
            {"type": "legacy_link", "vista": "absence"},
        ]
    }

    # --- Overlap ---
    ov = sections["overlap"]
    pares = ov.get("pares", [])[:30]
    ov.setdefault("pages", {})
    ov["pages"]["intra"] = {
        "blocks": [
            {
                "type": "kpi_row",
                "title": "Overlap",
                "items": [
                    {"label": "Pares", "value": ov.get("summary", {}).get("n_pares"), "format": "int"},
                    {"label": "Overlap intra médio", "value": ov.get("summary", {}).get("overlap_intra_medio"), "format": "percent"},
                ],
            },
            {
                "type": "table",
                "title": "Top pares compartilhados",
                "exportCsv": "overlap_pares.csv",
                "columns": [
                    {"key": "consultor_a", "label": "Consultor A"},
                    {"key": "consultor_b", "label": "Consultor B"},
                    {"key": "shared", "label": "Compartilhados", "num": True, "format": "int"},
                ],
                "rows": [
                    {
                        "consultor_a": p.get("consultor_a"),
                        "consultor_b": p.get("consultor_b"),
                        "shared": p.get("shared") or p.get("medicos_compartilhados") or p.get("n_shared"),
                    }
                    for p in pares
                ],
            },
            {"type": "legacy_link", "vista": "overlap"},
        ]
    }

    # --- Governança ---
    audit = portal.get("audit", {})
    gov = sections.setdefault("governanca", {})
    gov.setdefault("pages", {})
    gov["pages"]["fontes"] = {
        "blocks": [
            {
                "type": "table",
                "title": "Arquivos em bases/",
                "exportCsv": "auditoria_fontes.csv",
                "columns": [
                    {"key": "nome", "label": "Arquivo"},
                    {"key": "encontrado", "label": "OK"},
                    {"key": "linhas", "label": "Linhas", "num": True, "format": "int"},
                ],
                "rows": [
                    {
                        "nome": a.get("nome"),
                        "encontrado": "Sim" if a.get("encontrado") else "Não",
                        "linhas": a.get("linhas"),
                    }
                    for a in audit.get("arquivos", [])
                ],
            },
            {
                "type": "text",
                "text": f"Janela: {audit.get('janela', '')} · BU: {audit.get('bu', '')} · Pasta: {audit.get('bases_dir', '')}",
            },
            {"type": "legacy_link", "vista": "gloss"},
        ]
    }
