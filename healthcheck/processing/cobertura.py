"""Módulo de Cobertura.

Cruza o snapshot de painel com as visitas para responder: estamos cobrindo os
médicos certos? Calcula cobertura F2F, multicanal e MCCP por consultor, além do
status de cobertura por médico (coberto / não coberto / MCCP sem F2F).

Contrato:
    cobertura = calcular_cobertura(bases, painel, visitas)
"""

from __future__ import annotations

from processing import util


def calcular_cobertura(bases: dict, painel: dict, visitas: dict) -> dict:
    medicos_painel = painel.get("medicos", {})
    freq_medico = visitas.get("medico", {})

    medico_cobertura: list[dict] = []
    por_consultor: dict[str, dict] = {}

    def cons_acc(ck, nome, sf, gd):
        return por_consultor.setdefault(
            ck,
            {
                "consultor_key": ck,
                "consultor": nome,
                "sales_force": sf,
                "gd": gd,
                "hcp_alvo": 0,
                "hcp_mccp": 0,
                "hcp_coberto_f2f": 0,
                "hcp_coberto_multi": 0,
                "hcp_mccp_coberto_f2f": 0,
                "hcp_nao_coberto": 0,
            },
        )

    for chave, m in medicos_painel.items():
        ck = util.norm_key(m.get("consultor"))
        nome = m.get("consultor", "")
        sf = m.get("sales_force", "")
        gd = m.get("gd", "")
        acc = cons_acc(ck, nome, sf, gd)

        fm = freq_medico.get(chave) or freq_medico.get(util.norm_key(m.get("mdm"))) or {}
        visitas_total = fm.get("visitas", 0)
        visitas_f2f = fm.get("visitas_f2f", 0)
        no_mccp = bool(m.get("no_mccp"))
        coberto_f2f = visitas_f2f > 0
        coberto_multi = visitas_total > 0

        acc["hcp_alvo"] += 1
        if no_mccp:
            acc["hcp_mccp"] += 1
        if coberto_f2f:
            acc["hcp_coberto_f2f"] += 1
            if no_mccp:
                acc["hcp_mccp_coberto_f2f"] += 1
        if coberto_multi:
            acc["hcp_coberto_multi"] += 1
        if not coberto_multi:
            acc["hcp_nao_coberto"] += 1

        status = "coberto_f2f" if coberto_f2f else ("coberto_multi" if coberto_multi else "nao_coberto")
        medico_cobertura.append(
            {
                "chave": chave,
                "mdm": m.get("mdm", ""),
                "crm": m.get("crm", ""),
                "nome_medico": m.get("nome_medico", ""),
                "especialidade": m.get("especialidade", ""),
                "franquia": m.get("franquia", ""),
                "consultor": nome,
                "sales_force": sf,
                "gd": gd,
                "uf": m.get("uf", ""),
                "cidade": m.get("cidade", ""),
                "no_mccp": no_mccp,
                "visitas": visitas_total,
                "visitas_f2f": visitas_f2f,
                "coberto_f2f": coberto_f2f,
                "coberto_multi": coberto_multi,
                "mccp_sem_f2f": bool(no_mccp and not coberto_f2f),
                "ultima_visita": fm.get("ultima_visita", ""),
                "status": status,
            }
        )

    for c in por_consultor.values():
        c["pct_cobertura_f2f"] = util.pct(c["hcp_coberto_f2f"], c["hcp_alvo"])
        c["pct_cobertura_multi"] = util.pct(c["hcp_coberto_multi"], c["hcp_alvo"])
        c["pct_cobertura_mccp"] = util.pct(c["hcp_mccp_coberto_f2f"], c["hcp_mccp"])

    total_alvo = sum(c["hcp_alvo"] for c in por_consultor.values())
    total_f2f = sum(c["hcp_coberto_f2f"] for c in por_consultor.values())
    total_multi = sum(c["hcp_coberto_multi"] for c in por_consultor.values())
    total_mccp = sum(c["hcp_mccp"] for c in por_consultor.values())
    total_mccp_f2f = sum(c["hcp_mccp_coberto_f2f"] for c in por_consultor.values())

    resumo = {
        "hcp_alvo": total_alvo,
        "hcp_mccp": total_mccp,
        "hcp_coberto_f2f": total_f2f,
        "hcp_coberto_multi": total_multi,
        "hcp_nao_coberto": total_alvo - total_multi,
        "pct_cobertura_f2f": util.pct(total_f2f, total_alvo),
        "pct_cobertura_multi": util.pct(total_multi, total_alvo),
        "pct_cobertura_mccp": util.pct(total_mccp_f2f, total_mccp),
    }

    return {
        "por_consultor": por_consultor,
        "por_medico": medico_cobertura,
        "resumo": resumo,
    }
