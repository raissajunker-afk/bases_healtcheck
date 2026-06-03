from __future__ import annotations

from collections import defaultdict
from typing import Any

from processing.common import detect_column


CONSULTOR_ALIASES = [
    "consultor",
    "consultor_nome",
    "nome_consultor",
    "representante",
    "colaborador",
]
UF_ALIASES = ["uf", "estado"]
CIDADE_ALIASES = ["cidade", "municipio"]
BRICK_ALIASES = ["brick", "setor", "territorio"]


def _classificar_setor(total_ufs: int, total_cidades: int) -> str:
    if total_ufs > 1:
        return "viagem_interestadual"
    if total_cidades > 1:
        return "viagem_interna"
    return "local"


def calcular_territorio(
    bases: dict[str, Any],
    visitas: dict[str, Any],
    painel: dict[str, Any],
) -> dict[str, Any]:
    _ = painel
    tables = bases.get("tables", {})
    visita_tables = bases.get("domains", {}).get("visitas", [])
    rows: list[dict[str, Any]] = []
    for name in visita_tables:
        rows.extend(tables.get(name, []))

    if not rows:
        return {
            "summary": {"consultores_com_dados_territoriais": 0, "bricks_unicos": 0},
            "ranking_territorio": [],
            "score_territorio": [],
        }

    headers = rows[0].keys()
    consultor_col = detect_column(headers, CONSULTOR_ALIASES)
    uf_col = detect_column(headers, UF_ALIASES)
    cidade_col = detect_column(headers, CIDADE_ALIASES)
    brick_col = detect_column(headers, BRICK_ALIASES)

    consultor_ufs: defaultdict[str, set[str]] = defaultdict(set)
    consultor_cidades: defaultdict[str, set[str]] = defaultdict(set)
    consultor_bricks: defaultdict[str, set[str]] = defaultdict(set)
    all_bricks: set[str] = set()

    for row in rows:
        consultor = str(row.get(consultor_col, "")).strip() if consultor_col else "sem_consultor"
        uf = str(row.get(uf_col, "")).strip() if uf_col else ""
        cidade = str(row.get(cidade_col, "")).strip() if cidade_col else ""
        brick = str(row.get(brick_col, "")).strip() if brick_col else ""

        if uf:
            consultor_ufs[consultor].add(uf)
        if cidade:
            consultor_cidades[consultor].add(cidade)
        if brick:
            consultor_bricks[consultor].add(brick)
            all_bricks.add(brick)

    ranking_territorio = []
    for consultor in sorted(set(list(consultor_ufs.keys()) + list(consultor_cidades.keys()))):
        total_ufs = len(consultor_ufs.get(consultor, set()))
        total_cidades = len(consultor_cidades.get(consultor, set()))
        total_bricks = len(consultor_bricks.get(consultor, set()))
        tipo = _classificar_setor(total_ufs, total_cidades)
        ranking_territorio.append(
            {
                "consultor": consultor,
                "ufs_visitadas": total_ufs,
                "cidades_visitadas": total_cidades,
                "bricks_visitados": total_bricks,
                "tipo_setor": tipo,
            }
        )
    ranking_territorio.sort(key=lambda item: item["bricks_visitados"], reverse=True)

    visitas_por_dia_media = visitas.get("resumo", {}).get("visitas_por_dia_media", 0.0)
    score_territorio = []
    for item in ranking_territorio:
        dispersao = (item["ufs_visitadas"] * 1.5) + (item["cidades_visitadas"] * 0.5)
        score = max(0.0, 100.0 - (dispersao * 2.5) + (visitas_por_dia_media * 1.2))
        score_territorio.append(
            {
                "consultor": item["consultor"],
                "score_territorial": round(min(score, 100.0), 2),
                "tipo_setor": item["tipo_setor"],
            }
        )

    return {
        "summary": {
            "consultores_com_dados_territoriais": len(ranking_territorio),
            "bricks_unicos": len(all_bricks),
        },
        "ranking_territorio": ranking_territorio[:50],
        "score_territorio": sorted(score_territorio, key=lambda item: item["score_territorial"], reverse=True)[:50],
    }
