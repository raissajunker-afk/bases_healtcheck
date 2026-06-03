from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from processing.common import detect_column, parse_date, pct


CONSULTOR_ALIASES = [
    "consultor",
    "consultor_nome",
    "nome_consultor",
    "representante",
    "colaborador",
]
MEDICO_ALIASES = ["mdm", "id_medico", "codigo_medico", "crm", "medico_id"]
CANAL_ALIASES = ["canal", "canal_visita", "tipo_visita", "channel"]
DATA_ALIASES = ["data_visita", "dt_visita", "data", "date"]


def processar_visitas(bases: dict[str, Any], painel: dict[str, Any]) -> dict[str, Any]:
    tables = bases.get("tables", {})
    visitas_rows: list[dict[str, Any]] = []
    for table_name in bases.get("domains", {}).get("visitas", []):
        visitas_rows.extend(tables.get(table_name, []))

    if not visitas_rows:
        return {
            "resumo": {
                "visitas_totais": 0,
                "visitas_f2f": 0,
                "pct_visitas_f2f": 0.0,
                "visitas_por_dia_media": 0.0,
            },
            "ranking_consultor": [],
            "serie_mensal": [],
            "visitados_por_consultor": {},
            "visitados_unicos": set(),
            "visitas_raw": [],
        }

    headers = visitas_rows[0].keys()
    consultor_col = detect_column(headers, CONSULTOR_ALIASES)
    medico_col = detect_column(headers, MEDICO_ALIASES)
    canal_col = detect_column(headers, CANAL_ALIASES)
    data_col = detect_column(headers, DATA_ALIASES)

    total = 0
    total_f2f = 0
    visitas_por_consultor: Counter[str] = Counter()
    visitas_por_dia: Counter[str] = Counter()
    serie_mensal_counter: Counter[str] = Counter()
    visitados_por_consultor: defaultdict[str, set[str]] = defaultdict(set)
    visitados_unicos: set[str] = set()

    for row in visitas_rows:
        total += 1
        consultor = str(row.get(consultor_col, "")).strip() if consultor_col else "sem_consultor"
        medico = str(row.get(medico_col, "")).strip() if medico_col else ""
        canal = str(row.get(canal_col, "")).strip().lower() if canal_col else ""
        data = parse_date(row.get(data_col)) if data_col else None

        if "f2f" in canal or "presencial" in canal:
            total_f2f += 1

        visitas_por_consultor[consultor] += 1
        if data:
            visitas_por_dia[data.strftime("%Y-%m-%d")] += 1
            serie_mensal_counter[data.strftime("%Y-%m")] += 1

        if medico:
            visitados_por_consultor[consultor].add(medico)
            visitados_unicos.add(medico)

    dias_visitados = len(visitas_por_dia)
    visitas_por_dia_media = (total / dias_visitados) if dias_visitados else 0.0

    ranking_consultor = [
        {"consultor": consultor, "visitas": volume}
        for consultor, volume in visitas_por_consultor.most_common(30)
    ]
    serie_mensal = [
        {"mes": mes, "visitas": visitas}
        for mes, visitas in sorted(serie_mensal_counter.items(), key=lambda item: item[0])
    ]

    return {
        "resumo": {
            "visitas_totais": total,
            "visitas_f2f": total_f2f,
            "pct_visitas_f2f": round(pct(total_f2f, total), 2),
            "visitas_por_dia_media": round(visitas_por_dia_media, 2),
        },
        "ranking_consultor": ranking_consultor,
        "serie_mensal": serie_mensal,
        "visitados_por_consultor": {
            consultor: sorted(list(medicos)) for consultor, medicos in visitados_por_consultor.items()
        },
        "visitados_unicos": sorted(list(visitados_unicos)),
        "visitas_raw": visitas_rows,
    }
