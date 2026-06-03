"""Módulo de Índices finais.

Consolida as métricas por consultor vindas dos módulos anteriores em um único
registro por consultor (dataset `consultores`), calcula índices derivados e
gera os resumos executivos globais.

Contrato:
    indices = calcular_indices(painel, visitas, ausencias, cobertura,
                               territorio, overlap, especialidades)
"""

from __future__ import annotations

import statistics

import config
from processing import util


def _media(valores: list[float]) -> float:
    valores = [v for v in valores if v is not None]
    return util.rounded(statistics.fmean(valores), 2) if valores else 0.0


def calcular_indices(painel, visitas, ausencias, cobertura, territorio, overlap, especialidades) -> dict:
    estrutura = painel.get("consultores", {})
    v_cons = visitas.get("consultor", {})
    a_cons = ausencias.get("consultor", {})
    cob_cons = cobertura.get("por_consultor", {})
    ter_cons = territorio.get("por_consultor", {})
    esp_cons = {c["consultor_key"]: c for c in especialidades.get("consultores", [])}

    chaves = set(estrutura) | set(v_cons) | set(a_cons) | set(cob_cons) | set(ter_cons)

    dias_uteis_periodo = config.DIAS_UTEIS_MES * config.JANELAS[config.JANELA_PADRAO]["meses"]

    consultores: list[dict] = []
    for ck in sorted(chaves):
        est = estrutura.get(ck, {})
        v = v_cons.get(ck, {})
        a = a_cons.get(ck, {})
        cob = cob_cons.get(ck, {})
        ter = ter_cons.get(ck, {})
        esp = esp_cons.get(ck, {})

        nome = est.get("consultor") or v.get("consultor") or cob.get("consultor") or ck
        sf = est.get("sales_force") or v.get("sales_force") or cob.get("sales_force") or ""
        gd = est.get("gd") or v.get("gd") or cob.get("gd") or ""

        dias_ausencia = a.get("dias_ausencia", 0.0)
        pct_ausencia = util.pct(dias_ausencia, dias_uteis_periodo) if dias_uteis_periodo else 0.0

        registro = {
            "consultor_key": ck,
            "consultor": nome,
            "sales_force": sf,
            "gd": gd,
            "ativo": est.get("ativo", True),
            "cidade_sede": est.get("cidade_sede", ter.get("cidade_sede", "")),
            "uf_sede": est.get("uf_sede", ter.get("uf_sede", "")),
            "tipo_setor": est.get("tipo_setor", ter.get("tipo_setor", "")),
            "perfil_deslocamento": ter.get("perfil_deslocamento", ""),
            # painel
            "painel": est.get("painel", cob.get("hcp_alvo", 0)),
            "painel_meta": est.get("painel_meta", 0),
            # visitas / produtividade
            "visitas": v.get("visitas", 0),
            "visitas_f2f": v.get("visitas_f2f", 0),
            "dias_com_visita": v.get("dias_com_visita", 0),
            "visitas_dia": v.get("visitas_dia", 0.0),
            "medicos_visitados": v.get("medicos_visitados", 0),
            "pct_dentro_painel": v.get("pct_dentro_painel", 0.0),
            "pct_dentro_mccp": v.get("pct_dentro_mccp", 0.0),
            "pct_planejadas": v.get("pct_planejadas", 0.0),
            # cobertura
            "hcp_alvo": cob.get("hcp_alvo", 0),
            "hcp_mccp": cob.get("hcp_mccp", 0),
            "hcp_coberto_f2f": cob.get("hcp_coberto_f2f", 0),
            "hcp_nao_coberto": cob.get("hcp_nao_coberto", 0),
            "pct_cobertura_f2f": cob.get("pct_cobertura_f2f", 0.0),
            "pct_cobertura_multi": cob.get("pct_cobertura_multi", 0.0),
            "pct_cobertura_mccp": cob.get("pct_cobertura_mccp", 0.0),
            # ausências
            "dias_ausencia": dias_ausencia,
            "dias_produtiva": a.get("dias_produtiva", 0.0),
            "dias_pessoal": a.get("dias_pessoal", 0.0),
            "pct_ausencia": pct_ausencia,
            "dias_uteis": dias_uteis_periodo,
            "capacidade_disponivel": max(0, dias_uteis_periodo - round(dias_ausencia)),
            # território
            "cidades_visitadas": ter.get("cidades_visitadas", 0),
            "ufs_visitadas": ter.get("ufs_visitadas", 0),
            "bricks_visitados": ter.get("bricks_visitados", 0),
            "pct_visitas_uf_sede": ter.get("pct_visitas_uf_sede", 0.0),
            "score_territorio": ter.get("score_territorio", 0.0),
            # especialidades / estratégia
            "iaef": esp.get("iaef", 0.0),
            "icef": esp.get("icef", 0.0),
            "ifef": esp.get("ifef", 0.0),
            "gap_estrategico": esp.get("gap_estrategico", 0),
        }

        # Dias sem visita e sem ausência (gap não explicado)
        registro["gap_nao_explicado"] = max(
            0, dias_uteis_periodo - registro["dias_com_visita"] - round(dias_ausencia)
        )

        # Score de prioridade de ação (maior = mais urgente)
        score = (
            (100 - registro["pct_cobertura_f2f"]) * 0.5
            + min(registro["painel"], 200) * 0.15
            + registro["gap_estrategico"] * 0.8
            + registro["pct_ausencia"] * 0.5
        )
        registro["score_prioridade"] = util.rounded(score, 1)
        consultores.append(registro)

    # ----- resumos globais -----
    ativos = [c for c in consultores if c.get("ativo", True)]
    n_consultores = len(ativos) or len(consultores)

    resumo_executivo = {
        "consultores_ativos": n_consultores,
        "consultores_total": len(consultores),
        "medicos_painel": sum(c["painel"] for c in consultores),
        "painel_medio": _media([c["painel"] for c in consultores]),
        "visitas_total": sum(c["visitas"] for c in consultores),
        "visitas_f2f_total": sum(c["visitas_f2f"] for c in consultores),
        "visitas_dia_media": _media([c["visitas_dia"] for c in consultores if c["visitas_dia"] > 0]),
        "pct_cobertura_f2f": cobertura.get("resumo", {}).get("pct_cobertura_f2f", 0.0),
        "pct_cobertura_multi": cobertura.get("resumo", {}).get("pct_cobertura_multi", 0.0),
        "pct_cobertura_mccp": cobertura.get("resumo", {}).get("pct_cobertura_mccp", 0.0),
        "pct_dentro_mccp": _media([c["pct_dentro_mccp"] for c in consultores]),
        "pct_ausencia_media": _media([c["pct_ausencia"] for c in consultores]),
        "iaef": especialidades.get("resumo", {}).get("iaef", 0.0),
        "icef": especialidades.get("resumo", {}).get("icef", 0.0),
        "medicos_compartilhados": overlap.get("resumo", {}).get("medicos_compartilhados", 0),
    }

    return {
        "consultores": consultores,
        "resumo_executivo": resumo_executivo,
    }
