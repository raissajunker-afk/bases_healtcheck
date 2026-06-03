from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

from processing.common import detect_column


CONSULTOR_ALIASES = [
    "consultor",
    "consultor_nome",
    "nome_consultor",
    "representante",
    "colaborador",
]
MEDICO_ALIASES = ["mdm", "id_medico", "codigo_medico", "crm", "medico_id"]


def calcular_overlap(
    bases: dict[str, Any],
    visitas: dict[str, Any],
    painel: dict[str, Any],
) -> dict[str, Any]:
    _ = visitas
    _ = painel
    tables = bases.get("tables", {})
    visita_tables = bases.get("domains", {}).get("visitas", [])
    rows: list[dict[str, Any]] = []
    for name in visita_tables:
        rows.extend(tables.get(name, []))

    if not rows:
        return {
            "summary": {"medicos_compartilhados": 0, "pares_com_overlap": 0},
            "pares_overlap": [],
        }

    headers = rows[0].keys()
    consultor_col = detect_column(headers, CONSULTOR_ALIASES)
    medico_col = detect_column(headers, MEDICO_ALIASES)

    medico_to_consultores: defaultdict[str, set[str]] = defaultdict(set)
    for row in rows:
        consultor = str(row.get(consultor_col, "")).strip() if consultor_col else ""
        medico = str(row.get(medico_col, "")).strip() if medico_col else ""
        if consultor and medico:
            medico_to_consultores[medico].add(consultor)

    pair_counter: Counter[tuple[str, str]] = Counter()
    for consultores in medico_to_consultores.values():
        if len(consultores) > 1:
            for pair in combinations(sorted(consultores), 2):
                pair_counter[pair] += 1

    pares_overlap = [
        {"consultor_a": pair[0], "consultor_b": pair[1], "medicos_compartilhados": total}
        for pair, total in pair_counter.most_common(100)
    ]

    medicos_compartilhados = sum(1 for consultores in medico_to_consultores.values() if len(consultores) > 1)
    return {
        "summary": {
            "medicos_compartilhados": medicos_compartilhados,
            "pares_com_overlap": len(pair_counter),
        },
        "pares_overlap": pares_overlap,
    }
