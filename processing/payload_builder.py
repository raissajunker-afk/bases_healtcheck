from __future__ import annotations

from datetime import datetime, timezone

from config import WINDOWS


SECTION_TITLES = {
    "executive_overview": "Executive Overview",
    "performance_comercial": "Performance Comercial",
    "cobertura_painel": "Cobertura e Painel",
    "visitacao_frequencia": "Visitacao e Frequencia",
    "eficiencia_territorial": "Eficiencia Territorial",
    "ausencias_capacidade": "Ausencias e Capacidade",
    "especialidades_franquias": "Especialidades e Franquias",
    "qualidade_execucao": "Qualidade de Execucao",
    "overlap_conflitos": "Overlap e Conflitos",
    "simulador_planejamento": "Simulador e Planejamento",
    "oportunidades_plano_acao": "Oportunidades e Plano de Acao",
    "governanca_auditoria": "Governanca e Auditoria",
    "canais_mix_omnichannel": "Canais e Mix Omnichannel",
    "cadastro_master_data": "Cadastro e Master Data",
    "tendencias_sazonalidade": "Tendencias e Sazonalidade",
}


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _build_dimensions(painel: dict, indices: dict) -> dict:
    consultores = list(painel.get("dimensions", {}).get("consultores", []))
    sales_forces = list(painel.get("dimensions", {}).get("sales_forces", []))
    gds = list(painel.get("dimensions", {}).get("gds", []))

    for row in indices.get("consultor_window_metrics", []):
        consultores.append(str(row.get("consultor", "")))
        sales_forces.append(str(row.get("sales_force", "")))
        gds.append(str(row.get("gd", "")))

    return {
        "consultores": _unique_sorted(consultores),
        "sales_forces": _unique_sorted(sales_forces),
        "gds": _unique_sorted(gds),
        "windows": [{"id": key, "label": value} for key, value in WINDOWS.items()],
    }


def _build_insights(indices: dict, cobertura: dict, ausencias: dict) -> list[dict]:
    insights: list[dict] = []
    summary = indices.get("summary", {})
    coverage_summary = cobertura.get("summary", {})
    absence_summary = ausencias.get("summary", {})

    score = float(summary.get("score_geral", 0.0))
    coverage = float(coverage_summary.get("cobertura_mccp", 0.0))
    absence_days = int(absence_summary.get("dias_ausencia", 0))

    if coverage < 60:
        insights.append(
            {
                "type": "alerta",
                "title": "Cobertura MCCP abaixo do desejado",
                "message": "Priorize reforco de cobertura F2F e revisao de painel para consultores com gap.",
            }
        )
    if score >= 75:
        insights.append(
            {
                "type": "oportunidade",
                "title": "Base consolidada com bom score geral",
                "message": "A infraestrutura ja permite usar rankings e plano de acao para priorizacao fina.",
            }
        )
    if absence_days > 0:
        insights.append(
            {
                "type": "risco",
                "title": "Capacidade afetada por ausencias",
                "message": "Reveja impacto de ausencias sobre cobertura e produtividade nos recortes de janela.",
            }
        )
    if not insights:
        insights.append(
            {
                "type": "info",
                "title": "Portal pronto para expansao incremental",
                "message": "Quando novas regras de negocio forem definidas, basta plugar novos agregados no payload.",
            }
        )
    return insights


def montar_payload(
    bases: dict,
    painel: dict,
    visitas: dict,
    ausencias: dict,
    cobertura: dict,
    territorio: dict,
    overlap: dict,
    indices: dict,
) -> dict:
    dimensions = _build_dimensions(painel, indices)
    generated_at = datetime.now(timezone.utc).isoformat()
    insights = _build_insights(indices, cobertura, ausencias)

    sections = {
        section_id: {
            "title": title,
            "summary": {
                "score_geral": indices.get("summary", {}).get("score_geral", 0.0),
                "consultores": painel.get("summary", {}).get("consultores_ativos", 0),
                "medicos": painel.get("summary", {}).get("medicos_painel", 0),
            },
        }
        for section_id, title in SECTION_TITLES.items()
    }

    return {
        "meta": {
            "title": "Portal Analitico - Healthcheck Operacional",
            "generated_at": generated_at,
            "base_dir": bases["base_dir"],
            "files_loaded": len(bases["catalog"]),
            "warnings": bases["warnings"],
        },
        "dimensions": dimensions,
        "analytics": {
            "consultor_window": indices.get("consultor_window_metrics", []),
            "monthly_series": visitas.get("monthly_series", []),
            "overlap_pairs": overlap.get("pairs", []),
            "opportunity_doctors": cobertura.get("opportunity_doctors", []),
            "specialty_franchise": cobertura.get("specialty_franchise_metrics", []),
            "top_specialties": painel.get("summary", {}).get("top_especialidades", []),
            "top_channels": visitas.get("summary", {}).get("top_canais", []),
            "file_catalog": bases.get("catalog", []),
            "visit_sample": visitas.get("visit_records", []),
            "panel_sample": painel.get("doctor_sample", []),
            "absence_sample": ausencias.get("absence_records", []),
            "insights": insights,
        },
        "sections": sections,
        "audit": {
            "painel": painel.get("audit", {}),
            "visitas": visitas.get("audit", {}),
            "ausencias": ausencias.get("audit", {}),
            "cobertura": cobertura.get("audit", {}),
            "territorio": territorio.get("audit", {}),
            "overlap": overlap.get("audit", {}),
        },
    }
