"""Módulo de Especialidades e Franquias (camada estratégica - seção 7).

Cruza o mapa estratégico `franquias_especialidades.csv` com o painel e as
visitas para avaliar aderência, cobertura, frequência e dispersão por
combinação Especialidade × Franquia.

Indicadores produzidos:
  IAEF - Índice de Aderência Especialidade-Franquia (% visitas em espec. relevante)
  ICEF - Índice de Cobertura Especialidade-Franquia (% médicos relevantes cobertos F2F)
  IFEF - Índice de Frequência Especialidade-Franquia (frequência média normalizada)
  IDEF - Índice de Dispersão Especialidade-Franquia (concentração do esforço)

Regras:
  - Especialidade nunca é hardcodada no código (vem da base de configuração).
  - Especialidade ausente/vazia => "sem_classificacao" (auditada).
  - Uma especialidade pode pertencer a mais de uma franquia.

Contrato:
    especialidades = calcular_especialidades(bases, painel, visitas, cobertura)
"""

from __future__ import annotations

from processing import util

SEM_CLASSIFICACAO = "sem_classificacao"
FREQ_ESPERADA = 3  # visitas/médico relevante usadas como base do IFEF


def _mapa_franquias(franquias_rows: list[dict]) -> dict[str, list[dict]]:
    """especialidade_key -> [{franquia, relevancia, peso, papel}]."""
    mapa: dict[str, list[dict]] = {}
    for row in franquias_rows:
        esp = util.norm_key(row.get("especialidade"))
        if not esp:
            continue
        mapa.setdefault(esp, []).append(
            {
                "franquia": util.norm_text(row.get("franquia")),
                "relevancia": util.norm_key(row.get("relevancia")) or "media",
                "peso": util.to_float(row.get("peso"), 1.0),
                "papel": util.norm_text(row.get("papel")),
            }
        )
    return mapa


def calcular_especialidades(bases: dict, painel: dict, visitas: dict, cobertura: dict) -> dict:
    franquias_rows = bases.get("franquias_especialidades") or bases.get("franquias") or []
    mapa = _mapa_franquias(franquias_rows)
    medicos_painel = painel.get("medicos", {})
    freq_medico = visitas.get("medico", {})
    cob_por_medico = {c["chave"]: c for c in cobertura.get("por_medico", [])}

    matriz: dict[tuple, dict] = {}
    franquia_acc: dict[str, dict] = {}
    consultor_acc: dict[str, dict] = {}
    sem_classificacao = 0
    total_medicos = 0
    medicos_oportunidade: list[dict] = []

    for chave, m in medicos_painel.items():
        total_medicos += 1
        esp_key = util.norm_key(m.get("especialidade"))
        fm = freq_medico.get(chave) or {}
        cob = cob_por_medico.get(chave) or {}
        visitado = (fm.get("visitas", 0) or 0) > 0
        coberto_f2f = bool(cob.get("coberto_f2f"))
        freq = fm.get("frequencia", 0)
        no_mccp = bool(m.get("no_mccp"))

        destinos = mapa.get(esp_key)
        if not destinos:
            sem_classificacao += 1
            destinos = [{"franquia": util.norm_text(m.get("franquia")) or "Sem Franquia",
                         "relevancia": "sem_classificacao", "peso": 0.0, "papel": ""}]
            esp_label = m.get("especialidade") or SEM_CLASSIFICACAO
        else:
            esp_label = m.get("especialidade")

        for d in destinos:
            fr = d["franquia"] or "Sem Franquia"
            relevante = d["relevancia"] in {"alta", "media", "média"}
            ckey = (fr, esp_label)
            cell = matriz.setdefault(
                ckey,
                {
                    "franquia": fr,
                    "especialidade": esp_label,
                    "relevancia": d["relevancia"],
                    "no_painel": 0,
                    "no_mccp": 0,
                    "visitados": 0,
                    "cobertos_f2f": 0,
                    "soma_freq": 0,
                },
            )
            cell["no_painel"] += 1
            if no_mccp:
                cell["no_mccp"] += 1
            if visitado:
                cell["visitados"] += 1
            if coberto_f2f:
                cell["cobertos_f2f"] += 1
            cell["soma_freq"] += freq

            # acumulado por franquia
            fa = franquia_acc.setdefault(
                fr,
                {"franquia": fr, "relevantes": 0, "no_painel": 0, "no_mccp": 0, "visitados": 0,
                 "cobertos_f2f": 0, "soma_freq": 0, "_especialidades": set()},
            )
            fa["no_painel"] += 1
            fa["_especialidades"].add(esp_label)
            if relevante:
                fa["relevantes"] += 1
            if no_mccp:
                fa["no_mccp"] += 1
            if visitado:
                fa["visitados"] += 1
            if coberto_f2f:
                fa["cobertos_f2f"] += 1
            fa["soma_freq"] += freq

            # acumulado por consultor (gap estratégico)
            ck = util.norm_key(m.get("consultor"))
            ca = consultor_acc.setdefault(
                ck,
                {"consultor_key": ck, "consultor": m.get("consultor", ""),
                 "sales_force": m.get("sales_force", ""), "gd": m.get("gd", ""),
                 "relevantes": 0, "cobertos_f2f": 0, "mccp_sem_f2f": 0, "soma_freq": 0},
            )
            if relevante:
                ca["relevantes"] += 1
                if coberto_f2f:
                    ca["cobertos_f2f"] += 1
                if no_mccp and not coberto_f2f:
                    ca["mccp_sem_f2f"] += 1
                ca["soma_freq"] += freq

            # médicos prioritários sem cobertura
            if relevante and not coberto_f2f:
                medicos_oportunidade.append(
                    {
                        "mdm": m.get("mdm", ""),
                        "crm": m.get("crm", ""),
                        "nome_medico": m.get("nome_medico", ""),
                        "especialidade": esp_label,
                        "franquia": fr,
                        "consultor": m.get("consultor", ""),
                        "sales_force": m.get("sales_force", ""),
                        "gd": m.get("gd", ""),
                        "no_mccp": no_mccp,
                        "ultima_visita": fm.get("ultima_visita", ""),
                        "visitas": fm.get("visitas", 0),
                    }
                )

    # finalizar matriz
    lista_matriz = []
    for cell in matriz.values():
        cell["cobertura_f2f"] = util.pct(cell["cobertos_f2f"], cell["no_painel"])
        cell["freq_media"] = util.rounded(util.safe_div(cell["soma_freq"], cell["visitados"]), 2)
        cell["gap"] = cell["no_painel"] - cell["cobertos_f2f"]
        cob = cell["cobertura_f2f"]
        if cell["relevancia"] == "sem_classificacao":
            cell["status"] = "sem_dado"
        elif cob >= 75:
            cell["status"] = "saudavel"
        elif cob >= 50:
            cell["status"] = "atencao"
        else:
            cell["status"] = "critico"
        cell.pop("soma_freq", None)
        lista_matriz.append(cell)
    lista_matriz.sort(key=lambda x: (x["franquia"], -x["no_painel"]))

    # finalizar franquias + índices
    lista_franquias = []
    for fa in franquia_acc.values():
        n_esp = len(fa.pop("_especialidades"))
        cobertos = fa["cobertos_f2f"]
        relevantes = fa["relevantes"] or fa["no_painel"]
        icef = util.pct(cobertos, fa["no_painel"])
        ifef = util.rounded(min(100.0, 100.0 * util.safe_div(util.safe_div(fa["soma_freq"], max(fa["visitados"], 1)), FREQ_ESPERADA)), 1)
        # dispersão: muitas especialidades com poucos médicos = dispersão alta
        idef = util.rounded(min(100.0, 100.0 * util.safe_div(n_esp, max(fa["no_painel"], 1)) * 5), 1)
        lista_franquias.append(
            {
                "franquia": fa["franquia"],
                "especialidades": n_esp,
                "medicos_painel": fa["no_painel"],
                "medicos_relevantes": fa["relevantes"],
                "medicos_mccp": fa["no_mccp"],
                "medicos_visitados": fa["visitados"],
                "cobertos_f2f": fa["cobertos_f2f"],
                "icef": icef,
                "ifef": ifef,
                "idef": idef,
                "gap": fa["no_painel"] - fa["cobertos_f2f"],
            }
        )
    lista_franquias.sort(key=lambda x: -x["gap"])

    # finalizar consultores
    lista_consultores = []
    for ca in consultor_acc.values():
        ca["icef"] = util.pct(ca["cobertos_f2f"], ca["relevantes"])
        ca["gap_estrategico"] = ca["relevantes"] - ca["cobertos_f2f"]
        ca["ifef"] = util.rounded(min(100.0, 100.0 * util.safe_div(util.safe_div(ca["soma_freq"], max(ca["cobertos_f2f"], 1)), FREQ_ESPERADA)), 1)
        ca["iaef"] = ca["icef"]  # aproximação por consultor
        ca.pop("soma_freq", None)
        lista_consultores.append(ca)
    lista_consultores.sort(key=lambda x: -x["gap_estrategico"])

    # índices globais
    total_visitas = visitas.get("auditoria", {}).get("visitas_validas", 0)
    visitas_relevantes = 0
    for v in visitas.get("visitas_limpas", []):
        if util.norm_key(v.get("especialidade")) in mapa:
            visitas_relevantes += 1
    iaef = util.pct(visitas_relevantes, total_visitas)
    icef_global = cobertura.get("resumo", {}).get("pct_cobertura_f2f", 0)
    todas_freq = [m.get("frequencia", 0) for m in freq_medico.values() if m.get("frequencia", 0) > 0]
    ifef_global = util.rounded(min(100.0, 100.0 * util.safe_div(sum(todas_freq), max(len(todas_freq), 1)) / FREQ_ESPERADA), 1) if todas_freq else 0.0
    n_esp_total = len({c["especialidade"] for c in lista_matriz})
    idef_global = util.rounded(min(100.0, 100.0 * util.safe_div(n_esp_total, max(total_medicos, 1)) * 5), 1)

    resumo = {
        "total_medicos": total_medicos,
        "medicos_sem_classificacao": sem_classificacao,
        "pct_sem_classificacao": util.pct(sem_classificacao, total_medicos),
        "total_franquias": len({f["franquia"] for f in lista_franquias}),
        "pct_visitas_relevantes": iaef,
        "pct_visitas_nao_relevantes": util.rounded(100 - iaef, 1),
        "iaef": iaef,
        "icef": icef_global,
        "ifef": ifef_global,
        "idef": idef_global,
        "medicos_oportunidade": len(medicos_oportunidade),
    }

    medicos_oportunidade.sort(key=lambda x: (x["no_mccp"] is False, x["visitas"]))

    return {
        "resumo": resumo,
        "matriz": lista_matriz,
        "franquias": lista_franquias,
        "consultores": lista_consultores,
        "medicos_oportunidade": medicos_oportunidade,
        "auditoria": {
            "mapa_configurado": bool(mapa),
            "especialidades_mapeadas": len(mapa),
            "medicos_sem_classificacao": sem_classificacao,
        },
    }
