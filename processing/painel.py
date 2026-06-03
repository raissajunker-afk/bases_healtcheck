from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from processing.common import detect_column, normalize_key


CONSULTOR_ALIASES = [
    "consultor",
    "consultor_nome",
    "nome_consultor",
    "representante",
    "colaborador",
]
SALES_FORCE_ALIASES = ["sales_force", "salesforce", "sf", "forca_venda", "franquia"]
GD_ALIASES = ["gd", "gerente_distrital", "distrito", "gerencia_distrital"]
MEDICO_ID_ALIASES = ["mdm", "id_medico", "codigo_medico", "crm", "medico_id"]
MEDICO_NOME_ALIASES = ["nome_medico", "medico", "nome_hcp"]
ESPECIALIDADE_ALIASES = ["especialidade", "especialidade_primaria", "especialidade1"]


def _iter_base_records(bases: dict[str, Any]) -> list[dict[str, Any]]:
    tables = bases.get("tables", {})
    painel_tables = [tables[name] for name in bases.get("domains", {}).get("painel", []) if name in tables]
    if painel_tables:
        output: list[dict[str, Any]] = []
        for table in painel_tables:
            output.extend(table)
        return output

    # fallback para manter pipeline funcional quando nao houver base de painel dedicada
    output = []
    for table in tables.values():
        output.extend(table)
    return output


def processar_painel(bases: dict[str, Any]) -> dict[str, Any]:
    records = _iter_base_records(bases)
    if not records:
        return {
            "consultores": [],
            "sales_forces": [],
            "gds": [],
            "medicos": [],
            "kpis": {
                "total_consultores_ativos": 0,
                "total_medicos_painel": 0,
                "painel_medio_por_consultor": 0.0,
            },
            "auditoria": {"medicos_sem_especialidade": 0},
        }

    headers = records[0].keys()
    consultor_col = detect_column(headers, CONSULTOR_ALIASES)
    sf_col = detect_column(headers, SALES_FORCE_ALIASES)
    gd_col = detect_column(headers, GD_ALIASES)
    medico_id_col = detect_column(headers, MEDICO_ID_ALIASES)
    medico_nome_col = detect_column(headers, MEDICO_NOME_ALIASES)
    especialidade_col = detect_column(headers, ESPECIALIDADE_ALIASES)

    consultor_to_medicos: defaultdict[str, set[str]] = defaultdict(set)
    consultor_meta: dict[str, dict[str, str]] = {}
    sf_counter: Counter[str] = Counter()
    gd_counter: Counter[str] = Counter()
    medicos: dict[str, dict[str, str]] = {}
    sem_especialidade = 0

    for row in records:
        consultor = str(row.get(consultor_col, "")).strip() if consultor_col else ""
        sales_force = str(row.get(sf_col, "")).strip() if sf_col else ""
        gd = str(row.get(gd_col, "")).strip() if gd_col else ""
        medico_id = str(row.get(medico_id_col, "")).strip() if medico_id_col else ""
        medico_nome = str(row.get(medico_nome_col, "")).strip() if medico_nome_col else ""
        especialidade = str(row.get(especialidade_col, "")).strip() if especialidade_col else ""

        if not medico_id and medico_nome:
            medico_id = normalize_key(medico_nome)

        if consultor:
            consultor_meta.setdefault(
                consultor,
                {
                    "consultor": consultor,
                    "sales_force": sales_force or "sem_sales_force",
                    "gd": gd or "sem_gd",
                },
            )
            if sales_force:
                sf_counter[sales_force] += 1
            if gd:
                gd_counter[gd] += 1

        if medico_id:
            if consultor:
                consultor_to_medicos[consultor].add(medico_id)
            if not especialidade:
                sem_especialidade += 1
            medicos.setdefault(
                medico_id,
                {
                    "medico_id": medico_id,
                    "nome": medico_nome or medico_id,
                    "especialidade_primaria": especialidade or "sem_classificacao",
                },
            )

    consultores = []
    for consultor, meta in consultor_meta.items():
        consultores.append(
            {
                "consultor": consultor,
                "sales_force": meta["sales_force"],
                "gd": meta["gd"],
                "medicos_painel": len(consultor_to_medicos.get(consultor, set())),
            }
        )
    consultores.sort(key=lambda item: item["consultor"])

    sales_forces = [
        {"sales_force": sf, "rows": rows}
        for sf, rows in sorted(sf_counter.items(), key=lambda item: (-item[1], item[0]))
    ]
    gds = [{"gd": gd, "rows": rows} for gd, rows in sorted(gd_counter.items(), key=lambda item: (-item[1], item[0]))]
    medicos_list = sorted(medicos.values(), key=lambda item: item["nome"])

    total_consultores = len(consultores)
    total_medicos = len(medicos_list)
    painel_medio = (total_medicos / total_consultores) if total_consultores else 0.0

    return {
        "consultores": consultores,
        "sales_forces": sales_forces,
        "gds": gds,
        "medicos": medicos_list,
        "kpis": {
            "total_consultores_ativos": total_consultores,
            "total_medicos_painel": total_medicos,
            "painel_medio_por_consultor": round(painel_medio, 2),
        },
        "auditoria": {"medicos_sem_especialidade": sem_especialidade},
    }
