"""Módulo de Visitas.

Limpa e deduplica visitas, calcula métricas de produtividade por consultor,
frequência por médico, mix de canais e série mensal.

Contrato:
    visitas = processar_visitas(bases, painel)

Deduplicação: uma visita é única por (consultor, médico, data, canal).
"""

from __future__ import annotations

import config
from processing import util


def _is_f2f(canal: str) -> bool:
    return util.norm_key(canal) in config.CANAIS_F2F or canal == ""


def processar_visitas(bases: dict, painel: dict) -> dict:
    brutas = bases.get("visitas", [])

    vistos: set[tuple] = set()
    limpas: list[dict] = []
    removidas_dedup = 0
    sem_data = 0

    for row in brutas:
        cons = util.norm_text(row.get("consultor"))
        if not cons:
            continue
        sf = util.norm_text(row.get("sales_force"))
        if util.norm_key(sf) in {util.norm_key(x) for x in config.SALES_FORCES_EXCLUIDAS}:
            continue
        d = util.parse_date(row.get("data"))
        if d is None:
            sem_data += 1
        mdm = util.norm_text(row.get("mdm")) or util.norm_text(row.get("crm")) or util.norm_text(row.get("nome_medico"))
        canal = util.norm_text(row.get("canal"))
        chave = (util.norm_key(cons), util.norm_key(mdm), str(d), util.norm_key(canal))
        if chave in vistos:
            removidas_dedup += 1
            continue
        vistos.add(chave)
        limpas.append(
            {
                "consultor": cons,
                "consultor_key": util.norm_key(cons),
                "sales_force": sf,
                "gd": util.norm_text(row.get("gd")),
                "data": d,
                "ym": util.ym(d),
                "mdm": mdm,
                "medico_key": util.norm_key(mdm),
                "nome_medico": util.norm_text(row.get("nome_medico")),
                "especialidade": util.norm_text(row.get("especialidade")),
                "franquia": util.norm_text(row.get("franquia")),
                "canal": canal,
                "is_f2f": _is_f2f(canal),
                "cidade": util.norm_text(row.get("cidade")),
                "uf": util.norm_text(row.get("uf")),
                "brick": util.norm_text(row.get("brick")),
                "no_painel": util.to_bool(row.get("no_painel")) if row.get("no_painel") is not None else True,
                "no_mccp": util.to_bool(row.get("no_mccp")),
                "planejado": util.to_bool(row.get("planejado")) if row.get("planejado") is not None else None,
            }
        )

    # ----- métricas por consultor -----
    consultor: dict[str, dict] = {}
    for v in limpas:
        ck = v["consultor_key"]
        c = consultor.setdefault(
            ck,
            {
                "consultor_key": ck,
                "consultor": v["consultor"],
                "sales_force": v["sales_force"],
                "gd": v["gd"],
                "visitas": 0,
                "visitas_f2f": 0,
                "_dias": set(),
                "_medicos": set(),
                "dentro_painel": 0,
                "dentro_mccp": 0,
                "planejadas": 0,
                "planejadas_base": 0,
            },
        )
        c["visitas"] += 1
        if v["is_f2f"]:
            c["visitas_f2f"] += 1
        if v["data"] is not None:
            c["_dias"].add(v["data"])
        if v["medico_key"]:
            c["_medicos"].add(v["medico_key"])
        if v["no_painel"]:
            c["dentro_painel"] += 1
        if v["no_mccp"]:
            c["dentro_mccp"] += 1
        if v["planejado"] is not None:
            c["planejadas_base"] += 1
            if v["planejado"]:
                c["planejadas"] += 1

    for c in consultor.values():
        dias = len(c.pop("_dias"))
        medicos_unicos = len(c.pop("_medicos"))
        c["dias_com_visita"] = dias
        c["medicos_visitados"] = medicos_unicos
        c["visitas_dia"] = util.rounded(util.safe_div(c["visitas"], dias), 2)
        c["pct_dentro_painel"] = util.pct(c["dentro_painel"], c["visitas"])
        c["pct_dentro_mccp"] = util.pct(c["dentro_mccp"], c["visitas"])
        c["pct_planejadas"] = util.pct(c["planejadas"], c["planejadas_base"]) if c["planejadas_base"] else 0.0

    # ----- frequência por médico -----
    medico: dict[str, dict] = {}
    for v in limpas:
        mk = v["medico_key"]
        if not mk:
            continue
        m = medico.setdefault(
            mk,
            {
                "medico_key": mk,
                "mdm": v["mdm"],
                "nome_medico": v["nome_medico"],
                "especialidade": v["especialidade"],
                "franquia": v["franquia"],
                "consultor": v["consultor"],
                "sales_force": v["sales_force"],
                "gd": v["gd"],
                "uf": v["uf"],
                "cidade": v["cidade"],
                "visitas": 0,
                "visitas_f2f": 0,
                "_datas": set(),
                "ultima_visita": None,
            },
        )
        m["visitas"] += 1
        if v["is_f2f"]:
            m["visitas_f2f"] += 1
        if v["data"] is not None:
            m["_datas"].add(v["data"])
            if m["ultima_visita"] is None or v["data"] > m["ultima_visita"]:
                m["ultima_visita"] = v["data"]

    for m in medico.values():
        datas = m.pop("_datas")
        m["frequencia"] = len(datas)
        m["ultima_visita"] = m["ultima_visita"].isoformat() if m["ultima_visita"] else ""

    # ----- série mensal (global e por consultor) -----
    serie_global: dict[str, dict] = {}
    serie_consultor: dict[tuple, dict] = {}
    for v in limpas:
        if not v["ym"]:
            continue
        g = serie_global.setdefault(v["ym"], {"ym": v["ym"], "visitas": 0, "visitas_f2f": 0, "_medicos": set()})
        g["visitas"] += 1
        if v["is_f2f"]:
            g["visitas_f2f"] += 1
        if v["medico_key"]:
            g["_medicos"].add(v["medico_key"])

        chave = (v["consultor_key"], v["ym"])
        s = serie_consultor.setdefault(
            chave,
            {"consultor_key": v["consultor_key"], "consultor": v["consultor"], "sales_force": v["sales_force"],
             "gd": v["gd"], "ym": v["ym"], "visitas": 0, "visitas_f2f": 0},
        )
        s["visitas"] += 1
        if v["is_f2f"]:
            s["visitas_f2f"] += 1

    serie_mensal = []
    for g in sorted(serie_global.values(), key=lambda x: x["ym"]):
        g["medicos_unicos"] = len(g.pop("_medicos"))
        serie_mensal.append(g)

    return {
        "visitas_limpas": limpas,
        "consultor": consultor,
        "medico": medico,
        "serie_mensal": serie_mensal,
        "serie_consultor": list(serie_consultor.values()),
        "auditoria": {
            "visitas_brutas": len(brutas),
            "visitas_validas": len(limpas),
            "removidas_dedup": removidas_dedup,
            "sem_data": sem_data,
        },
    }
