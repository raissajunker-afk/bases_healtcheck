"""Módulo de Overlap e Conflitos.

Identifica médicos compartilhados entre consultores e monta pares com
quantidade de médicos em comum e intensidade do compartilhamento.

Contrato:
    overlap = calcular_overlap(bases, visitas, painel)
"""

from __future__ import annotations

from itertools import combinations

from processing import util


def calcular_overlap(bases: dict, visitas: dict, painel: dict) -> dict:
    limpas = visitas.get("visitas_limpas", [])

    # médico -> {consultor_key -> {nome, sf, gd, visitas, datas}}
    medico_consultores: dict[str, dict] = {}
    for v in limpas:
        mk = v["medico_key"]
        if not mk:
            continue
        d = medico_consultores.setdefault(mk, {})
        info = d.setdefault(
            v["consultor_key"],
            {"consultor": v["consultor"], "sales_force": v["sales_force"], "gd": v["gd"], "visitas": 0, "datas": set()},
        )
        info["visitas"] += 1
        if v["data"]:
            info["datas"].add(v["data"])

    pares: dict[tuple, dict] = {}
    medicos_compartilhados = 0
    for mk, conss in medico_consultores.items():
        if len(conss) < 2:
            continue
        medicos_compartilhados += 1
        for a, b in combinations(sorted(conss.keys()), 2):
            chave = (a, b)
            p = pares.setdefault(
                chave,
                {
                    "consultor_a": conss[a]["consultor"],
                    "consultor_b": conss[b]["consultor"],
                    "sf_a": conss[a]["sales_force"],
                    "sf_b": conss[b]["sales_force"],
                    "medicos_compartilhados": 0,
                    "mesmo_dia": 0,
                    "cross_team": conss[a]["sales_force"] != conss[b]["sales_force"],
                },
            )
            p["medicos_compartilhados"] += 1
            if conss[a]["datas"] & conss[b]["datas"]:
                p["mesmo_dia"] += 1

    lista_pares = sorted(pares.values(), key=lambda x: x["medicos_compartilhados"], reverse=True)

    return {
        "pares": lista_pares,
        "resumo": {
            "medicos_compartilhados": medicos_compartilhados,
            "pares_em_overlap": len(lista_pares),
            "pares_cross_team": sum(1 for p in lista_pares if p["cross_team"]),
        },
    }
