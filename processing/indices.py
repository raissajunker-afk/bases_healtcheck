from __future__ import annotations


def calcular_indices(
    *,
    painel: dict,
    visitas: dict,
    ausencias: dict,
    cobertura: dict,
    territorio: dict,
    overlap: dict,
) -> dict:
    total_consultores = max(1, painel.get("kpis", {}).get("total_consultores_ativos", 0))
    cobertura_pct = cobertura.get("summary", {}).get("pct_cobertura_f2f", 0.0)
    visitas_dia = visitas.get("resumo", {}).get("visitas_por_dia_media", 0.0)
    dias_ausencia = ausencias.get("resumo", {}).get("dias_ausencia_total", 0.0)
    overlap_pairs = overlap.get("summary", {}).get("pares_com_overlap", 0)
    score_territorial = 0.0
    territory_scores = territorio.get("score_territorio", [])
    if territory_scores:
        score_territorial = sum(item.get("score_territorial", 0.0) for item in territory_scores) / len(
            territory_scores
        )

    iaef = min(100.0, max(0.0, (cobertura_pct * 0.6) + (score_territorial * 0.4)))
    icef = min(100.0, max(0.0, cobertura_pct))
    ifef = min(100.0, max(0.0, visitas_dia * 8))
    idef = min(100.0, max(0.0, 100.0 - (overlap_pairs / total_consultores)))
    gap_estrategico = max(0.0, 100.0 - ((iaef + icef + ifef + idef) / 4.0) + (dias_ausencia / total_consultores))

    return {
        "iaef": round(iaef, 2),
        "icef": round(icef, 2),
        "ifef": round(ifef, 2),
        "idef": round(idef, 2),
        "gap_estrategico_especialidade": round(gap_estrategico, 2),
    }
