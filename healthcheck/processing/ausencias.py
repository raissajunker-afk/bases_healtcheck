"""Módulo de Ausências.

Deduplica ausências, classifica em produtiva/pessoal e calcula dias de
ausência por consultor, além de capacidade disponível estimada.

Contrato:
    ausencias = processar_ausencias(bases)
"""

from __future__ import annotations

import config
from processing import util

# Categorização: palavras-chave -> categoria padronizada.
_PRODUTIVA = {"treinamento", "reuniao", "reunião", "congresso", "evento", "ciclo", "interno", "workshop"}
_PESSOAL = {"ferias", "férias", "atestado", "doenca", "doença", "licenca", "licença", "folga", "pessoal", "falta"}


def _classificar(categoria: str, tipo: str) -> str:
    txt = util.norm_key(f"{categoria} {tipo}")
    if any(p in txt for p in _PRODUTIVA):
        return "produtiva"
    if any(p in txt for p in _PESSOAL):
        return "pessoal"
    return "outra"


def processar_ausencias(bases: dict) -> dict:
    brutas = bases.get("ausencias", [])

    vistos: set[tuple] = set()
    limpas: list[dict] = []
    removidas_dedup = 0

    for row in brutas:
        cons = util.norm_text(row.get("consultor"))
        if not cons:
            continue
        ini = util.parse_date(row.get("data_inicio"))
        fim = util.parse_date(row.get("data_fim"))
        dias = util.to_float(row.get("dias"))
        if dias <= 0 and ini and fim:
            dias = (fim - ini).days + 1
        if dias <= 0 and ini:
            dias = 1
        categoria = _classificar(util.norm_text(row.get("categoria")), util.norm_text(row.get("tipo")))
        chave = (util.norm_key(cons), str(ini), str(fim), util.norm_key(row.get("tipo")))
        if chave in vistos:
            removidas_dedup += 1
            continue
        vistos.add(chave)
        limpas.append(
            {
                "consultor": cons,
                "consultor_key": util.norm_key(cons),
                "sales_force": util.norm_text(row.get("sales_force")),
                "gd": util.norm_text(row.get("gd")),
                "data_inicio": ini,
                "ym": util.ym(ini),
                "dias": dias,
                "categoria": categoria,
                "tipo": util.norm_text(row.get("tipo")),
            }
        )

    consultor: dict[str, dict] = {}
    for a in limpas:
        ck = a["consultor_key"]
        c = consultor.setdefault(
            ck,
            {
                "consultor_key": ck,
                "consultor": a["consultor"],
                "sales_force": a["sales_force"],
                "gd": a["gd"],
                "dias_ausencia": 0.0,
                "dias_produtiva": 0.0,
                "dias_pessoal": 0.0,
                "dias_outra": 0.0,
            },
        )
        c["dias_ausencia"] += a["dias"]
        c[f"dias_{a['categoria']}"] = c.get(f"dias_{a['categoria']}", 0.0) + a["dias"]

    for c in consultor.values():
        for k in ("dias_ausencia", "dias_produtiva", "dias_pessoal", "dias_outra"):
            c[k] = util.rounded(c[k], 1)

    # série mensal de ausências
    serie: dict[str, dict] = {}
    for a in limpas:
        if not a["ym"]:
            continue
        s = serie.setdefault(a["ym"], {"ym": a["ym"], "dias_ausencia": 0.0})
        s["dias_ausencia"] += a["dias"]
    serie_mensal = [
        {"ym": s["ym"], "dias_ausencia": util.rounded(s["dias_ausencia"], 1)}
        for s in sorted(serie.values(), key=lambda x: x["ym"])
    ]

    return {
        "ausencias_limpas": limpas,
        "consultor": consultor,
        "serie_mensal": serie_mensal,
        "auditoria": {
            "ausencias_brutas": len(brutas),
            "ausencias_validas": len(limpas),
            "removidas_dedup": removidas_dedup,
        },
    }
