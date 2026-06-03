from __future__ import annotations

from collections import Counter
from typing import Any

from processing.common import detect_column, safe_float


CONSULTOR_ALIASES = [
    "consultor",
    "consultor_nome",
    "nome_consultor",
    "representante",
    "colaborador",
]
TIPO_ALIASES = ["tipo_ausencia", "categoria_ausencia", "tipo", "motivo", "ausencia_tipo"]
DIAS_ALIASES = ["dias", "dias_ausencia", "qtd_dias", "dias_totais"]


def processar_ausencias(bases: dict[str, Any]) -> dict[str, Any]:
    tables = bases.get("tables", {})
    rows: list[dict[str, Any]] = []
    for table_name in bases.get("domains", {}).get("ausencias", []):
        rows.extend(tables.get(table_name, []))

    if not rows:
        return {
            "resumo": {"dias_ausencia_total": 0.0, "registros_ausencia": 0},
            "por_tipo": [],
            "por_consultor": [],
        }

    headers = rows[0].keys()
    consultor_col = detect_column(headers, CONSULTOR_ALIASES)
    tipo_col = detect_column(headers, TIPO_ALIASES)
    dias_col = detect_column(headers, DIAS_ALIASES)

    total_dias = 0.0
    tipo_counter: Counter[str] = Counter()
    consultor_counter: Counter[str] = Counter()

    for row in rows:
        dias = safe_float(row.get(dias_col), default=1.0) if dias_col else 1.0
        total_dias += dias
        tipo = str(row.get(tipo_col, "")).strip() if tipo_col else "sem_tipo"
        consultor = str(row.get(consultor_col, "")).strip() if consultor_col else "sem_consultor"
        tipo_counter[tipo or "sem_tipo"] += dias
        consultor_counter[consultor or "sem_consultor"] += dias

    por_tipo = [
        {"tipo_ausencia": tipo, "dias": round(dias, 2)}
        for tipo, dias in tipo_counter.most_common(20)
    ]
    por_consultor = [
        {"consultor": consultor, "dias_ausencia": round(dias, 2)}
        for consultor, dias in consultor_counter.most_common(30)
    ]

    return {
        "resumo": {
            "dias_ausencia_total": round(total_dias, 2),
            "registros_ausencia": len(rows),
        },
        "por_tipo": por_tipo,
        "por_consultor": por_consultor,
    }
