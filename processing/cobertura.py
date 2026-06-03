from __future__ import annotations

from typing import Any

from processing.common import pct


def calcular_cobertura(
    bases: dict[str, Any],
    painel: dict[str, Any],
    visitas: dict[str, Any],
) -> dict[str, Any]:
    _ = bases  # reservado para evolucoes futuras sem quebrar assinatura

    medicos_painel = {
        item.get("medico_id", "")
        for item in painel.get("medicos", [])
        if item.get("medico_id")
    }
    medicos_visitados = set(visitas.get("visitados_unicos", []))
    medicos_cobertos = medicos_painel.intersection(medicos_visitados)
    medicos_nao_cobertos = medicos_painel.difference(medicos_visitados)

    cobertura_pct = pct(len(medicos_cobertos), len(medicos_painel))

    consultores_painel = {
        item.get("consultor", ""): item.get("medicos_painel", 0) for item in painel.get("consultores", [])
    }
    visitados_por_consultor = visitas.get("visitados_por_consultor", {})

    ranking_consultor = []
    for consultor, total_medicos in consultores_painel.items():
        visitados = len(visitados_por_consultor.get(consultor, []))
        cobertura_consultor = pct(visitados, total_medicos)
        ranking_consultor.append(
            {
                "consultor": consultor,
                "medicos_painel": total_medicos,
                "medicos_visitados": visitados,
                "pct_cobertura_f2f": round(cobertura_consultor, 2),
            }
        )
    ranking_consultor.sort(key=lambda item: item["pct_cobertura_f2f"], reverse=True)

    return {
        "summary": {
            "medicos_painel": len(medicos_painel),
            "medicos_visitados": len(medicos_cobertos),
            "medicos_nao_cobertos": len(medicos_nao_cobertos),
            "pct_cobertura_f2f": round(cobertura_pct, 2),
            "pct_cobertura_multicanal": round(cobertura_pct, 2),
        },
        "ranking_consultor": ranking_consultor[:50],
        "medicos_nao_cobertos": [
            {"medico_id": medico_id} for medico_id in sorted(list(medicos_nao_cobertos))[:500]
        ],
    }
