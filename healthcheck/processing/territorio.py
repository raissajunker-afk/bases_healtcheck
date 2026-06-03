"""Módulo de Território.

Avalia desenho e execução territorial por consultor: UF/cidade sede, número de
cidades e UFs visitadas, % de visitas na UF sede, perfil de deslocamento e um
score territorial simples.

Contrato:
    territorio = calcular_territorio(bases, visitas, painel)
"""

from __future__ import annotations

from processing import util


def calcular_territorio(bases: dict, visitas: dict, painel: dict) -> dict:
    limpas = visitas.get("visitas_limpas", [])
    consultores_estrutura = painel.get("consultores", {})

    acc: dict[str, dict] = {}
    for v in limpas:
        ck = v["consultor_key"]
        c = acc.setdefault(
            ck,
            {
                "consultor_key": ck,
                "consultor": v["consultor"],
                "sales_force": v["sales_force"],
                "gd": v["gd"],
                "_cidades": set(),
                "_ufs": set(),
                "_bricks": set(),
                "visitas": 0,
                "_visitas_uf": {},
            },
        )
        c["visitas"] += 1
        if v["cidade"]:
            c["_cidades"].add(util.norm_key(v["cidade"]))
        if v["uf"]:
            c["_ufs"].add(util.norm_key(v["uf"]))
            c["_visitas_uf"][util.norm_key(v["uf"])] = c["_visitas_uf"].get(util.norm_key(v["uf"]), 0) + 1
        if v["brick"]:
            c["_bricks"].add(util.norm_key(v["brick"]))

    por_consultor: dict[str, dict] = {}
    for ck, c in acc.items():
        est = consultores_estrutura.get(ck, {})
        uf_sede = util.norm_key(est.get("uf_sede", ""))
        visitas_uf = c.pop("_visitas_uf")
        visitas_sede = visitas_uf.get(uf_sede, 0) if uf_sede else 0
        n_cidades = len(c.pop("_cidades"))
        n_ufs = len(c.pop("_ufs"))
        n_bricks = len(c.pop("_bricks"))
        total = c["visitas"]
        pct_uf_sede = util.pct(visitas_sede, total) if uf_sede else 0.0

        if n_ufs <= 1:
            perfil = "local"
        elif n_ufs == 2:
            perfil = "viagem_interna"
        else:
            perfil = "viagem_interestadual"

        # Score territorial: concentração na sede + foco geográfico.
        score = util.rounded(0.6 * pct_uf_sede + 0.4 * (100 - min(100, n_cidades * 4)), 1)

        por_consultor[ck] = {
            "consultor_key": ck,
            "consultor": c["consultor"],
            "sales_force": c["sales_force"],
            "gd": c["gd"],
            "cidade_sede": est.get("cidade_sede", ""),
            "uf_sede": est.get("uf_sede", ""),
            "tipo_setor": est.get("tipo_setor", "") or perfil,
            "perfil_deslocamento": perfil,
            "cidades_visitadas": n_cidades,
            "ufs_visitadas": n_ufs,
            "bricks_visitados": n_bricks,
            "pct_visitas_uf_sede": pct_uf_sede,
            "score_territorio": score,
        }

    return {"por_consultor": por_consultor}
