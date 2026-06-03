"""Registry do portal — 15 macro seções ligadas aos CAMPOS REAIS do payload.

Única fonte de verdade da navegação Home → Seção → Página → Blocos.
Cada bloco é resolvido por configuração contra os `datasets`/`summaries` reais
produzidos pelo `processar.py` (via adapter). Nenhuma fórmula é recalculada aqui.

Campos reais usados (dataset `consultores`): pctCoberturaF2F, pctCoberturaMulti,
mccp_pct_cumprido, pct_dentro_mccp, vis_dia_media, visitas_12m, pct_ausencia,
ipa_pct, ipt, score_territorio, cidades_visitadas_n, pct_visitas_uf_sede,
pct_overlap_intra, painel_size, etc. KPIs de time vêm do dataset `kpis`.
"""

from __future__ import annotations


# ---- construtores de bloco ----
def kpi(id, title, dataset, *, agg="value", field=None, num=None, den=None,
        fmt="int", benchmark=None, subtitle=None):
    return {"type": "kpi", "id": id, "title": title, "dataset": dataset, "agg": agg,
            "field": field, "num": num, "den": den, "format": fmt,
            "benchmark": benchmark, "subtitle": subtitle}


def table(id, title, dataset, columns, *, sort=None, dir="desc", limit=50):
    return {"type": "table", "id": id, "title": title, "dataset": dataset,
            "columns": columns, "sort": sort, "dir": dir, "limit": limit}


def ranking(id, title, dataset, label_field, value_field, *, fmt="int",
            dir="desc", limit=15, extra=None):
    return {"type": "ranking", "id": id, "title": title, "dataset": dataset,
            "labelField": label_field, "valueField": value_field, "format": fmt,
            "dir": dir, "limit": limit, "extra": extra or []}


def chart(id, title, dataset, chart_type, *, x=None, series=None, label=None, value=None):
    return {"type": "chart", "id": id, "title": title, "dataset": dataset,
            "chartType": chart_type, "x": x, "series": series or [],
            "labelField": label, "valueField": value}


def insight(id, title, rules):
    return {"type": "insight", "id": id, "title": title, "rules": rules}


def export_block(id, title, dataset):
    return {"type": "export", "id": id, "title": title, "dataset": dataset}


def methodology(id, title, items):
    return {"type": "methodology", "id": id, "title": title, "items": items}


def simulator(id, title, inputs, outputs):
    return {"type": "simulator", "id": id, "title": title, "inputs": inputs, "outputs": outputs}


def audit(id, title, path):
    return {"type": "audit", "id": id, "title": title, "path": path}


def empty(id, title, msg):
    return {"type": "empty", "id": id, "title": title, "message": msg}


def col(field, label, fmt="text"):
    return {"field": field, "label": label, "format": fmt}


C_CONS = col("consultor", "Consultor")
C_SF = col("sales_force", "Sales Force")
C_GD = col("gd", "GD")


def _page(section, section_id, subsection, page_id, title, question, decision, blocks):
    return {"id": page_id, "section": section, "sectionId": section_id,
            "subsection": subsection, "title": title, "businessQuestion": question,
            "decisionSupported": decision, "blocks": blocks}


def build_registry() -> list[dict]:
    S: list[dict] = []

    # 1. EXECUTIVE OVERVIEW ---------------------------------------------------
    S.append({"id": "executive", "title": "Executive Overview", "icon": "compass",
              "descricao": "Leitura rápida para liderança com os principais sinais do negócio.",
              "subsections": [
        {"id": "snapshot", "title": "Snapshot Executivo", "page": _page(
            "Executive Overview", "executive", "Snapshot Executivo", "exec_snapshot",
            "Snapshot Executivo", "Qual a fotografia atual da operação?",
            "Onde olhar primeiro.",
            [
                kpi("k_cons", "Consultores", "kpis", field="n_consultores"),
                kpi("k_painel", "Painel total", "kpis", field="painel_total_time"),
                kpi("k_painel_med", "Painel médio/consultor", "kpis", field="painel_medio", fmt="decimal2"),
                kpi("k_vdia", "Visitas/dia (média)", "kpis", field="vis_dia_media", fmt="decimal2", benchmark="vis_dia_media"),
                kpi("k_mccp", "MCCP cumprido (time)", "kpis", field="mccp_pct_cumprido_team", fmt="percent", benchmark="mccp_pct_cumprido"),
                kpi("k_dentro", "Visitas dentro MCCP", "kpis", field="pct_dentro_mccp_team", fmt="percent", benchmark="pct_dentro_mccp"),
                kpi("k_aus", "Ausência média", "kpis", field="pct_ausencia_media", fmt="percent", benchmark="pct_ausencia"),
                kpi("k_vis", "Visitas no MAT", "kpis", field="vis_total_12m"),
                chart("c_evol", "Evolução de visitas (mensal)", "serie_visitas", "line", x="ym",
                      series=[{"field": "visitas", "label": "Visitas"}, {"field": "medicos_unicos_time", "label": "Médicos únicos"}]),
                insight("i_exec", "Insight executivo", [
                    {"if": {"field": "k_mccp", "op": "<", "value": 50}, "level": "risco", "text": "Cumprimento MCCP do time abaixo de 50%: risco de não atingir o plano do trimestre."},
                    {"if": {"field": "k_aus", "op": ">", "value": 25}, "level": "alerta", "text": "Ausência média elevada — impacto direto na capacidade de cobertura."},
                ]),
            ])},
        {"id": "alertas", "title": "Alertas Prioritários", "page": _page(
            "Executive Overview", "executive", "Alertas Prioritários", "exec_alertas",
            "Alertas Prioritários", "Onde estão os maiores riscos agora?",
            "Direcionar a atenção da liderança.",
            [
                ranking("r_low_cob", "Menor cobertura F2F", "consultores", "consultor", "pctCoberturaF2F", fmt="percent", dir="asc", extra=[C_SF]),
                ranking("r_low_mccp", "Menor cumprimento MCCP", "consultores", "consultor", "mccp_pct_cumprido", fmt="percent", dir="asc", extra=[C_SF]),
                ranking("r_aus", "Maior % de ausência", "consultores", "consultor", "pct_ausencia", fmt="percent", extra=[C_SF]),
                export_block("e_alertas", "Exportar consultores", "consultores"),
            ])},
        {"id": "evolucao", "title": "Evolução Geral", "page": _page(
            "Executive Overview", "executive", "Evolução Geral", "exec_evol",
            "Evolução Geral", "Como a atividade vem evoluindo?",
            "Identificar tendências e quedas de ritmo.",
            [
                chart("c_vis", "Visitas por mês", "serie_visitas", "bar", x="ym", series=[{"field": "visitas", "label": "Visitas"}]),
                chart("c_pv", "Visitas dentro vs fora do painel", "serie_pv", "line", x="ym",
                      series=[{"field": "vis_no_painel", "label": "No painel"}, {"field": "vis_fora_painel", "label": "Fora painel"}]),
                chart("c_aus", "Ausência (%) por mês", "serie_ausencias", "line", x="ym", series=[{"field": "pct_ausencia", "label": "% Ausência"}]),
            ])},
        {"id": "por_sf", "title": "Resumo por Sales Force", "page": _page(
            "Executive Overview", "executive", "Resumo por Sales Force", "exec_sf",
            "Resumo por Sales Force", "Como cada SF se compara?",
            "Comparar forças de vendas.",
            [
                table("t_sf", "Indicadores por Sales Force", "sales_forces",
                      [C_SF, col("n_consultores", "Consultores", "int"), col("painel_medio", "Painel médio", "decimal2"),
                       col("vis_dia_media", "Vis/dia", "decimal2"), col("pct_ausencia_media", "Ausência", "percent"),
                       col("medicos_unicos_mes_medio", "Méd. únicos/mês", "decimal2")], sort="n_consultores", limit=20),
                chart("c_sf_vdia", "Visitas/dia por SF", "sales_forces", "bar", label="sales_force", value="vis_dia_media"),
            ])},
        {"id": "por_gd", "title": "Resumo por GD", "page": _page(
            "Executive Overview", "executive", "Resumo por GD", "exec_gd",
            "Resumo por GD", "Como cada GD se compara?",
            "Comparar gerências distritais.",
            [
                table("t_gd", "Indicadores por GD", "gds",
                      [C_GD, col("n_consultores", "Consultores", "int"), col("painel_medio", "Painel médio", "decimal2"),
                       col("vis_dia_media", "Vis/dia", "decimal2"), col("pct_ausencia_media", "Ausência", "percent")], sort="n_consultores", limit=20),
                chart("c_gd_vdia", "Visitas/dia por GD", "gds", "bar", label="gd", value="vis_dia_media"),
            ])},
    ]})

    # 2. PERFORMANCE COMERCIAL -----------------------------------------------
    S.append({"id": "performance", "title": "Performance Comercial", "icon": "trend",
              "descricao": "Produtividade comercial e execução do time.",
              "subsections": [
        {"id": "prod", "title": "Produtividade Geral", "page": _page(
            "Performance Comercial", "performance", "Produtividade Geral", "perf_prod",
            "Produtividade Geral", "O time está com bom ritmo?",
            "Avaliar volume e ritmo.",
            [
                kpi("k_vdia", "Visitas/dia (média)", "consultores", agg="mean", field="vis_dia_media", fmt="decimal2", benchmark="vis_dia_media"),
                kpi("k_vis", "Visitas (MAT)", "consultores", agg="sum", field="visitas_12m"),
                kpi("k_med", "Médicos únicos/mês (média)", "consultores", agg="mean", field="medicos_unicos_mes", fmt="decimal2"),
                kpi("k_freq", "Frequência/médico/mês", "consultores", agg="mean", field="freq_medico_mes", fmt="decimal2", benchmark="freq_medico_mes"),
                chart("c_dist", "Visitas/dia por consultor", "consultores", "bar", label="consultor", value="vis_dia_media"),
                chart("c_serie", "Série de visitas (time)", "serie_visitas", "line", x="ym", series=[{"field": "vis_dia_team", "label": "Vis/dia time"}]),
            ])},
        {"id": "por_cons", "title": "Performance por Consultor", "page": _page(
            "Performance Comercial", "performance", "Performance por Consultor", "perf_cons",
            "Performance por Consultor", "Quem performa e quem precisa de apoio?",
            "Reconhecimento e suporte.",
            [
                table("t_cons", "Performance por consultor", "consultores",
                      [C_CONS, C_SF, col("visitas_12m", "Visitas", "int"), col("vis_dia_media", "Vis/dia", "decimal2"),
                       col("medicos_unicos_mes", "Méd/mês", "decimal2"), col("pctCoberturaF2F", "Cob. F2F", "percent"),
                       col("mccp_pct_cumprido", "MCCP", "percent")], sort="visitas_12m", limit=80),
                export_block("e_cons", "Exportar base de consultores", "consultores"),
            ])},
        {"id": "alta", "title": "Ranking de Alta Performance", "page": _page(
            "Performance Comercial", "performance", "Ranking de Alta Performance", "perf_alta",
            "Ranking de Alta Performance", "Quem são os destaques?",
            "Estudar boas práticas.",
            [
                ranking("r_vis", "Top visitas/dia", "consultores", "consultor", "vis_dia_media", fmt="decimal2", extra=[C_SF]),
                ranking("r_cob", "Top cobertura F2F", "consultores", "consultor", "pctCoberturaF2F", fmt="percent", extra=[C_SF]),
            ])},
        {"id": "baixa", "title": "Ranking de Baixa Performance", "page": _page(
            "Performance Comercial", "performance", "Ranking de Baixa Performance", "perf_baixa",
            "Ranking de Baixa Performance", "Quem precisa de atenção?",
            "Direcionar apoio.",
            [
                ranking("r_vis", "Menor visitas/dia", "consultores", "consultor", "vis_dia_media", fmt="decimal2", dir="asc", extra=[C_SF]),
                ranking("r_cob", "Menor cobertura F2F", "consultores", "consultor", "pctCoberturaF2F", fmt="percent", dir="asc", extra=[C_SF]),
                export_block("e_low", "Exportar para plano de apoio", "consultores"),
            ])},
        {"id": "tendencia", "title": "Tendência de Visitação", "page": _page(
            "Performance Comercial", "performance", "Tendência de Visitação", "perf_tend",
            "Tendência de Visitação", "O ritmo recente sobe ou cai?",
            "Detectar aceleração/desaceleração (use a janela no topo).",
            [
                chart("c_tend", "Visitas/dia do time por mês", "serie_visitas", "line", x="ym", series=[{"field": "vis_dia_team", "label": "Vis/dia time"}]),
                ranking("r_slope", "Tendência vis/dia (slope) por consultor", "consultores", "consultor", "slope_vis_dia", fmt="decimal2", extra=[C_SF]),
            ])},
    ]})

    # 3. COBERTURA E PAINEL ---------------------------------------------------
    S.append({"id": "cobertura", "title": "Cobertura e Painel", "icon": "target",
              "descricao": "Estamos cobrindo os médicos certos?",
              "subsections": [
        {"id": "mccp", "title": "Cobertura MCCP", "page": _page(
            "Cobertura e Painel", "cobertura", "Cobertura MCCP", "cob_mccp",
            "Cobertura MCCP", "Estamos cumprindo o plano (MCCP) do trimestre?",
            "Priorizar reforço onde o cumprimento está baixo.",
            [
                kpi("k_target", "Meta MCCP (trimestre)", "kpis", field="mccp_target_total_q"),
                kpi("k_real", "Realizado MCCP", "kpis", field="mccp_realizado_total_q"),
                kpi("k_pct", "% Cumprido (time)", "kpis", field="mccp_pct_cumprido_team", fmt="percent", benchmark="mccp_pct_cumprido"),
                kpi("k_freq", "Frequência média/tri", "kpis", field="mccp_freq_media_tri_team", fmt="decimal2"),
                ranking("r_mccp", "Cumprimento MCCP por consultor", "consultores", "consultor", "mccp_pct_cumprido", fmt="percent", dir="asc", extra=[C_SF]),
                table("t_mccp", "MCCP por consultor", "consultores",
                      [C_CONS, C_SF, col("mccp_panel", "Painel", "int"), col("mccp_target_tri", "Meta tri", "int"),
                       col("mccp_realizado", "Realizado", "int"), col("mccp_pct_cumprido", "% Cumprido", "percent")],
                      sort="mccp_pct_cumprido", dir="asc", limit=80),
                insight("i_mccp", "Insight de cobertura", [
                    {"if": {"field": "k_pct", "op": "<", "value": 50}, "level": "risco", "text": "Cumprimento MCCP do time abaixo de 50%."},
                ]),
                export_block("e_mccp", "Exportar MCCP por consultor", "consultores"),
            ])},
        {"id": "f2f", "title": "Cobertura F2F (ICP-F2F)", "page": _page(
            "Cobertura e Painel", "cobertura", "Cobertura F2F", "cob_f2f",
            "Cobertura F2F", "Quantos HCPs do painel recebem visita presencial?",
            "Priorizar gaps de cobertura presencial.",
            [
                kpi("k_cob", "ICP-F2F (média)", "consultores", agg="mean", field="pctCoberturaF2F", fmt="percent", benchmark="pctCoberturaF2F"),
                kpi("k_alvo", "HCPs alvo (total)", "consultores", agg="sum", field="hcpsAlvoTotal"),
                kpi("k_cobf2f", "HCPs cobertos F2F", "consultores", agg="sum", field="hcpsCobertosF2F"),
                ranking("r_cob", "ICP-F2F por consultor", "consultores", "consultor", "pctCoberturaF2F", fmt="percent", dir="asc", extra=[C_SF]),
                chart("c_sf", "ICP-F2F por SF", "consultores", "bar", label="sales_force", value="pctCoberturaF2F"),
            ])},
        {"id": "multi", "title": "Cobertura Multicanal (ICP-Multi)", "page": _page(
            "Cobertura e Painel", "cobertura", "Cobertura Multicanal", "cob_multi",
            "Cobertura Multicanal", "Quantos HCPs são alcançados por qualquer canal?",
            "Avaliar alcance multicanal.",
            [
                kpi("k_multi", "ICP-Multi (média)", "consultores", agg="mean", field="pctCoberturaMulti", fmt="percent", benchmark="pctCoberturaMulti"),
                kpi("k_cobmulti", "HCPs cobertos Multi", "consultores", agg="sum", field="hcpsCobertosMulti"),
                ranking("r_multi", "ICP-Multi por consultor", "consultores", "consultor", "pctCoberturaMulti", fmt="percent", dir="asc", extra=[C_SF]),
            ])},
        {"id": "painel", "title": "Dentro vs Fora do Painel", "page": _page(
            "Cobertura e Painel", "cobertura", "Dentro vs Fora do Painel", "cob_painel",
            "Dentro vs Fora do Painel", "Quanta energia vai para fora do painel?",
            "Reduzir esforço fora do alvo.",
            [
                chart("c_pv", "Visitas dentro vs fora do painel (mensal)", "serie_pv", "line", x="ym",
                      series=[{"field": "vis_no_painel", "label": "No painel"}, {"field": "vis_fora_painel", "label": "Fora painel"}]),
                chart("c_pct", "% visitas no painel (mensal)", "serie_pv", "line", x="ym", series=[{"field": "pct_no_painel", "label": "% no painel"}]),
            ])},
        {"id": "parados", "title": "Médicos no Plano sem Cobertura", "page": _page(
            "Cobertura e Painel", "cobertura", "Médicos no Plano sem Cobertura", "cob_parados",
            "Médicos no Plano sem Cobertura", "Onde há mais HCPs alvo descobertos?",
            "Reativar cobertura.",
            [
                ranking("r_gap", "Maior gap F2F (alvo - cobertos)", "consultores", "consultor", "hcpsAlvoTotal", extra=[C_SF, col("hcpsCobertosF2F", "Cobertos", "int")]),
                table("t_gap", "Gap de cobertura por consultor", "consultores",
                      [C_CONS, C_SF, col("hcpsAlvoTotal", "Alvo", "int"), col("hcpsCobertosF2F", "Cobertos F2F", "int"),
                       col("pctCoberturaF2F", "ICP-F2F", "percent")], sort="pctCoberturaF2F", dir="asc", limit=80),
            ])},
    ]})

    # 4. VISITAÇÃO E FREQUÊNCIA ----------------------------------------------
    S.append({"id": "visitacao", "title": "Visitação e Frequência", "icon": "calendar",
              "descricao": "Ritmo, cadência e consistência de visitação.",
              "subsections": [
        {"id": "freq", "title": "Frequência", "page": _page(
            "Visitação e Frequência", "visitacao", "Frequência", "vis_freq",
            "Frequência", "Com que frequência os médicos são visitados?",
            "Ajustar cadência.",
            [
                kpi("k_freq", "Frequência/médico/mês", "consultores", agg="mean", field="freq_medico_mes", fmt="decimal2", benchmark="freq_medico_mes"),
                kpi("k_freq_mccp", "Frequência MCCP/tri (média)", "consultores", agg="mean", field="mccp_freq_media_tri", fmt="decimal2"),
                chart("c_freqdist", "Distribuição de frequência MCCP", "freq_dist_mccp", "bar", label="faixa", value="n"),
                ranking("r_freq", "Frequência/médico/mês por consultor", "consultores", "consultor", "freq_medico_mes", fmt="decimal2", extra=[C_SF]),
            ])},
        {"id": "consist", "title": "Consistência Mensal", "page": _page(
            "Visitação e Frequência", "visitacao", "Consistência Mensal", "vis_consist",
            "Consistência Mensal", "O ritmo é constante mês a mês?",
            "Detectar meses fracos.",
            [
                chart("c_mes", "Visitas por mês", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Visitas"}]),
                chart("c_cons", "Consultores ativos por mês", "serie_visitas", "bar", x="ym", series=[{"field": "consultores_ativos", "label": "Ativos"}]),
            ])},
        {"id": "vdia", "title": "Visitas por Dia", "page": _page(
            "Visitação e Frequência", "visitacao", "Visitas por Dia", "vis_dia",
            "Visitas por Dia", "A produtividade diária é adequada?",
            "Otimizar agenda.",
            [
                kpi("k_vdia", "Visitas/dia (média)", "consultores", agg="mean", field="vis_dia_media", fmt="decimal2", benchmark="vis_dia_media"),
                kpi("k_cv", "Variabilidade (CV vis/dia)", "consultores", agg="mean", field="cv_vis_dia", fmt="decimal2"),
                ranking("r_vdia", "Visitas/dia por consultor", "consultores", "consultor", "vis_dia_media", fmt="decimal2", extra=[C_SF]),
            ])},
        {"id": "medunicos", "title": "Médicos Únicos", "page": _page(
            "Visitação e Frequência", "visitacao", "Médicos Únicos", "vis_med",
            "Médicos Únicos", "Quantos médicos diferentes são alcançados?",
            "Ampliar alcance.",
            [
                kpi("k_med", "Médicos únicos/mês (time)", "kpis", field="medicos_unicos_mes_time"),
                chart("c_med", "Médicos únicos por mês", "serie_visitas", "line", x="ym", series=[{"field": "medicos_unicos_time", "label": "Médicos únicos"}]),
                ranking("r_med", "Médicos únicos/mês por consultor", "consultores", "consultor", "medicos_unicos_mes", fmt="decimal2", extra=[C_SF]),
            ])},
        {"id": "sazon", "title": "Sazonalidade", "page": _page(
            "Visitação e Frequência", "visitacao", "Sazonalidade", "vis_sazon",
            "Sazonalidade", "Há padrões sazonais?",
            "Planejar picos e vales.",
            [
                chart("c_sazon", "Visitas e médicos únicos por mês", "serie_visitas", "line", x="ym",
                      series=[{"field": "visitas", "label": "Visitas"}, {"field": "medicos_unicos_time", "label": "Médicos únicos"}]),
            ])},
    ]})

    # 5. EFICIÊNCIA TERRITORIAL ----------------------------------------------
    S.append({"id": "territorio", "title": "Eficiência Territorial", "icon": "map",
              "descricao": "O território está bem desenhado e executado?",
              "subsections": [
        {"id": "perfil", "title": "Perfil de Setor", "page": _page(
            "Eficiência Territorial", "territorio", "Perfil de Setor", "ter_perfil",
            "Perfil de Setor", "Como se distribui o perfil dos setores?",
            "Calibrar expectativas por tipo de setor.",
            [
                chart("c_perfil", "Consultores por tipo de setor", "consultores", "donut", label="tipo_setor", value="ISID"),
                table("t_perfil", "Perfil por consultor", "consultores",
                      [C_CONS, col("uf_sede", "UF Sede"), col("cidade_sede", "Cidade Sede"), col("tipo_setor", "Tipo Setor"),
                       col("meses_no_setor", "Meses no setor", "int")], sort="meses_no_setor", limit=80),
            ])},
        {"id": "desloc", "title": "Deslocamento", "page": _page(
            "Eficiência Territorial", "territorio", "Deslocamento", "ter_desloc",
            "Deslocamento", "Quanto o time se desloca para fora da sede?",
            "Avaliar custo de deslocamento.",
            [
                kpi("k_ufsede", "% visitas na UF sede (média)", "consultores", agg="mean", field="pct_visitas_uf_sede", fmt="percent", benchmark="pct_visitas_uf_sede"),
                ranking("r_fora", "Maior % fora da UF sede", "consultores", "consultor", "pct_visitas_fora_uf_sede", fmt="percent", extra=[C_SF]),
                ranking("r_ufs", "Mais UFs visitadas", "consultores", "consultor", "n_ufs_visitadas", extra=[C_SF]),
            ])},
        {"id": "cidades", "title": "Cobertura de Cidades", "page": _page(
            "Eficiência Territorial", "territorio", "Cobertura de Cidades", "ter_cidades",
            "Cobertura de Cidades", "As cidades alocadas estão sendo visitadas?",
            "Priorizar cidades não visitadas.",
            [
                kpi("k_cob_cid", "% cobertura de cidades (média)", "consultores", agg="mean", field="pct_cobertura_cidades", fmt="percent", benchmark="pct_cobertura_cidades"),
                table("t_cid", "Cidades por consultor", "consultores",
                      [C_CONS, col("cidades_alocadas_n", "Alocadas", "int"), col("cidades_alocadas_visitadas_n", "Visitadas", "int"),
                       col("cidades_nao_visitadas_n", "Não visitadas", "int"), col("pct_cobertura_cidades", "% cobertura", "percent")],
                      sort="pct_cobertura_cidades", dir="asc", limit=80),
            ])},
        {"id": "score", "title": "Score de Território", "page": _page(
            "Eficiência Territorial", "territorio", "Score de Território", "ter_score",
            "Score de Território", "Quais territórios estão mais eficientes?",
            "Priorizar redesenho.",
            [
                kpi("k_score", "Score território (média)", "consultores", agg="mean", field="score_territorio", fmt="decimal2", benchmark="score_territorio"),
                ranking("r_score", "Score território por consultor", "consultores", "consultor", "score_territorio", fmt="decimal2", dir="asc", extra=[C_SF]),
                export_block("e_ter", "Exportar território", "consultores"),
            ])},
        {"id": "brickagem", "title": "Brickagem", "page": _page(
            "Eficiência Territorial", "territorio", "Brickagem", "ter_brick",
            "Brickagem", "Há brickagem subutilizada?",
            "Sanear alocação territorial.",
            [
                ranking("r_brick", "Subutilização (menor cobertura de cidades)", "consultores", "consultor", "pct_cobertura_cidades", fmt="percent", dir="asc", extra=[C_SF]),
            ])},
    ]})

    # 6. AUSÊNCIAS E CAPACIDADE ----------------------------------------------
    S.append({"id": "ausencias", "title": "Ausências e Capacidade", "icon": "clock",
              "descricao": "Perda de capacidade, ausências e dias não explicados.",
              "subsections": [
        {"id": "total", "title": "Ausência Total", "page": _page(
            "Ausências e Capacidade", "ausencias", "Ausência Total", "aus_total",
            "Ausência Total", "Quanto da capacidade é perdida em ausências?",
            "Dimensionar impacto.",
            [
                kpi("k_pct", "% ausência (média)", "consultores", agg="mean", field="pct_ausencia", fmt="percent", benchmark="pct_ausencia"),
                kpi("k_dias", "Dias de ausência (MAT, total)", "consultores", agg="sum", field="ausencia_12m"),
                kpi("k_trab", "Dias trabalhados/mês (média)", "consultores", agg="mean", field="dias_trabalhados_mes", fmt="decimal2"),
                ranking("r_aus", "Maior % de ausência", "consultores", "consultor", "pct_ausencia", fmt="percent", extra=[C_SF]),
                chart("c_aus", "Ausência (%) por mês", "serie_ausencias", "line", x="ym", series=[{"field": "pct_ausencia", "label": "% Ausência"}]),
            ])},
        {"id": "produtiva", "title": "Ausência Produtiva", "page": _page(
            "Ausências e Capacidade", "ausencias", "Ausência Produtiva", "aus_prod",
            "Ausência Produtiva", "Quanto é reunião/treino/congresso?",
            "Separar produtiva de perda real.",
            [
                chart("c_prod", "Composição de ausência produtiva (mensal)", "serie_ausencias", "line", x="ym",
                      series=[{"field": "reunioes", "label": "Reuniões"}, {"field": "treinamento", "label": "Treinamento"}, {"field": "congressos", "label": "Congressos"}]),
                ranking("r_reun", "Dias de reunião (MAT)", "consultores", "consultor", "reunioes_12m", fmt="decimal2", extra=[C_SF]),
            ])},
        {"id": "pessoal", "title": "Ausência Pessoal", "page": _page(
            "Ausências e Capacidade", "ausencias", "Ausência Pessoal", "aus_pessoal",
            "Ausência Pessoal", "Quanto é ausência pessoal (férias/atestado)?",
            "Planejar coberturas.",
            [
                chart("c_pess", "Ausência pessoal por mês", "serie_ausencias", "bar", x="ym", series=[{"field": "pessoais", "label": "Pessoais"}]),
                ranking("r_pess", "Dias pessoais (MAT)", "consultores", "consultor", "pessoais_12m", fmt="decimal2", extra=[C_SF]),
            ])},
        {"id": "capacidade", "title": "Capacidade Disponível", "page": _page(
            "Ausências e Capacidade", "ausencias", "Capacidade Disponível", "aus_cap",
            "Capacidade Disponível", "Qual a capacidade real disponível?",
            "Metas realistas.",
            [
                kpi("k_cap", "Capacidade dias/ano (média)", "consultores", agg="mean", field="capacidade_dias_ano", fmt="decimal2"),
                kpi("k_gap", "Gap dias não explicados (média)", "consultores", agg="mean", field="gap_dias_nao_explicados", fmt="decimal2"),
                table("t_cap", "Capacidade por consultor", "consultores",
                      [C_CONS, col("uteis_12m", "Úteis (MAT)", "int"), col("ausencia_12m", "Ausência", "decimal2"),
                       col("trabalhados_12m", "Trabalhados", "decimal2"), col("gap_dias_nao_explicados", "Gap", "decimal2")],
                      sort="gap_dias_nao_explicados", limit=80),
            ])},
        {"id": "sazon", "title": "Sazonalidade de Ausências", "page": _page(
            "Ausências e Capacidade", "ausencias", "Sazonalidade de Ausências", "aus_sazon",
            "Sazonalidade de Ausências", "Quando se concentram as ausências?",
            "Antecipar meses de menor capacidade.",
            [
                chart("c_sazon", "Ausência total por mês", "serie_ausencias", "bar", x="ym", series=[{"field": "ausencia", "label": "Dias de ausência"}]),
            ])},
    ]})

    # 7. ESPECIALIDADES E CADASTRO -------------------------------------------
    S.append({"id": "especialidades", "title": "Especialidades e Cadastro", "icon": "layers",
              "descricao": "Distribuição de especialidades e qualidade do cadastro de médicos.",
              "subsections": [
        {"id": "dist", "title": "Distribuição de Especialidades", "page": _page(
            "Especialidades e Cadastro", "especialidades", "Distribuição de Especialidades", "esp_dist",
            "Distribuição de Especialidades", "Em quais especialidades está o painel?",
            "Direcionar foco por especialidade.",
            [
                kpi("k_med", "Médicos no dashboard", "medicos", agg="count"),
                kpi("k_esp", "Especialidades distintas", "especialidades", agg="count"),
                ranking("r_esp", "Especialidades mais frequentes", "especialidades", "especialidade", "n_medicos"),
                chart("c_esp", "Top especialidades", "especialidades", "bar", label="especialidade", value="n_medicos"),
            ])},
        {"id": "catalogo", "title": "Catálogo de Médicos", "page": _page(
            "Especialidades e Cadastro", "especialidades", "Catálogo de Médicos", "esp_cat",
            "Catálogo de Médicos", "Quais médicos compõem o universo do dashboard?",
            "Base para saneamento cadastral.",
            [
                table("t_med", "Médicos", "medicos",
                      [col("mdm", "MDM"), col("nome", "Nome"), col("crm", "CRM"), col("especialidade", "Especialidade"), col("tipo", "Tipo")],
                      sort="nome", dir="asc", limit=200),
                export_block("e_med", "Exportar médicos", "medicos"),
            ])},
        {"id": "cadastro", "title": "Qualidade de Cadastro", "page": _page(
            "Especialidades e Cadastro", "especialidades", "Qualidade de Cadastro", "esp_cad",
            "Qualidade de Cadastro", "Há médicos sem classificação?",
            "Sanear cadastro.",
            [
                ranking("r_semclass", "Especialidades por volume (verifique 'Sem classificação')", "especialidades", "especialidade", "n_medicos"),
                methodology("m_esp", "Nota metodológica", [
                    "A especialidade vem do relatório de visitas/painel (ACC PRIMARY SPECIALTY).",
                    "O mapeamento estratégico Especialidade × Franquia exige uma base de configuração adicional, não presente nas fontes atuais.",
                ]),
            ])},
    ]})

    # 8. QUALIDADE DE EXECUÇÃO -----------------------------------------------
    S.append({"id": "qualidade", "title": "Qualidade de Execução", "icon": "check",
              "descricao": "Aderência ao plano e índices de produtividade.",
              "subsections": [
        {"id": "aderencia", "title": "Aderência ao Plano (MCCP)", "page": _page(
            "Qualidade de Execução", "qualidade", "Aderência ao Plano", "qual_ader",
            "Aderência ao Plano", "As visitas seguem o MCCP?",
            "Aumentar aderência.",
            [
                kpi("k_dentro", "% visitas dentro MCCP (média)", "consultores", agg="mean", field="pct_dentro_mccp", fmt="percent", benchmark="pct_dentro_mccp"),
                kpi("k_fora", "% visitas fora MCCP (média)", "consultores", agg="mean", field="pct_fora_mccp", fmt="percent"),
                ranking("r_dentro", "Menor aderência MCCP", "consultores", "consultor", "pct_dentro_mccp", fmt="percent", dir="asc", extra=[C_SF]),
            ])},
        {"id": "ipa", "title": "IPA — Aderência ao Plano", "page": _page(
            "Qualidade de Execução", "qualidade", "IPA", "qual_ipa",
            "IPA — Aderência ao Plano", "O quanto do plano individual é cumprido?",
            "Foco em quem está abaixo.",
            [
                kpi("k_ipa", "IPA (média)", "consultores", agg="mean", field="ipa_pct", fmt="percent", benchmark="ipa_pct"),
                ranking("r_ipa", "IPA por consultor", "consultores", "consultor", "ipa_pct", fmt="percent", dir="asc", extra=[C_SF]),
            ])},
        {"id": "ipt", "title": "IPT — Produtividade Territorial", "page": _page(
            "Qualidade de Execução", "qualidade", "IPT", "qual_ipt",
            "IPT — Produtividade Territorial", "Qual o índice de produtividade territorial?",
            "Calibrar produtividade vs território.",
            [
                kpi("k_ipt", "IPT (média)", "consultores", agg="mean", field="ipt", fmt="decimal2", benchmark="ipt"),
                ranking("r_ipt", "IPT por consultor", "consultores", "consultor", "ipt", fmt="decimal2", dir="asc", extra=[C_SF]),
            ])},
    ]})

    # 9. OVERLAP E CONFLITOS --------------------------------------------------
    S.append({"id": "overlap", "title": "Overlap e Conflitos", "icon": "link",
              "descricao": "Sobreposição de atuação, duplicidade e conflito.",
              "subsections": [
        {"id": "intra", "title": "Overlap Intra-Time", "page": _page(
            "Overlap e Conflitos", "overlap", "Overlap Intra-Time", "ov_intra",
            "Overlap Intra-Time", "Quanto de sobreposição interna existe?",
            "Reduzir overlap interno.",
            [
                kpi("k_intra", "Overlap intra (média %)", "kpis", field="overlap_intra_medio", fmt="percent"),
                ranking("r_intra", "Maior overlap intra por consultor", "consultores", "consultor", "pct_overlap_intra", fmt="percent", extra=[C_SF]),
            ])},
        {"id": "cross", "title": "Overlap Cross-Team", "page": _page(
            "Overlap e Conflitos", "overlap", "Overlap Cross-Team", "ov_cross",
            "Overlap Cross-Team", "Há sobreposição entre SFs diferentes?",
            "Coordenar times.",
            [
                table("t_pares", "Pares em overlap", "overlap_pares",
                      [col("consultor_a", "Consultor A"), col("consultor_b", "Consultor B"), col("tipo", "Tipo"),
                       col("shared", "Compart.", "int"), col("pct_min", "% mín.", "percent"), col("pct_mesmo_dia", "% mesmo dia", "percent")],
                      sort="shared", limit=100),
            ])},
        {"id": "pares", "title": "Pares Compartilhados", "page": _page(
            "Overlap e Conflitos", "overlap", "Pares Compartilhados", "ov_pares",
            "Pares Compartilhados", "Quais pares mais compartilham médicos?",
            "Definir dono quando fizer sentido.",
            [
                ranking("r_pares", "Top pares por médicos compartilhados", "overlap_pares", "consultor_a", "shared", extra=[col("consultor_b", "Consultor B")]),
                export_block("e_pares", "Exportar pares de overlap", "overlap_pares"),
            ])},
        {"id": "conflitos", "title": "Conflitos (mesmo dia)", "page": _page(
            "Overlap e Conflitos", "overlap", "Conflitos de Território", "ov_conf",
            "Conflitos (mesmo dia)", "Há atuação no mesmo médico no mesmo dia?",
            "Resolver conflitos operacionais.",
            [
                ranking("r_dia", "Pares com mais médicos no mesmo dia", "overlap_pares", "consultor_a", "medicos_mesmo_dia_n", extra=[col("consultor_b", "Consultor B")]),
            ])},
    ]})

    # 10. MULTICANAL ----------------------------------------------------------
    S.append({"id": "multicanal", "title": "Multicanal e Engajamento", "icon": "signal",
              "descricao": "Equilíbrio entre presencial (F2F) e multicanal.",
              "subsections": [
        {"id": "mix", "title": "F2F vs Multicanal", "page": _page(
            "Multicanal e Engajamento", "multicanal", "F2F vs Multicanal", "mc_mix",
            "F2F vs Multicanal", "Qual o ganho do multicanal sobre o F2F?",
            "Calibrar estratégia multicanal.",
            [
                kpi("k_f2f", "ICP-F2F (média)", "consultores", agg="mean", field="pctCoberturaF2F", fmt="percent", benchmark="pctCoberturaF2F"),
                kpi("k_multi", "ICP-Multi (média)", "consultores", agg="mean", field="pctCoberturaMulti", fmt="percent", benchmark="pctCoberturaMulti"),
                ranking("r_delta", "Maior cobertura multicanal", "consultores", "consultor", "pctCoberturaMulti", fmt="percent", extra=[C_SF]),
            ])},
        {"id": "alcance", "title": "Alcance Multicanal", "page": _page(
            "Multicanal e Engajamento", "multicanal", "Alcance Multicanal", "mc_alc",
            "Alcance Multicanal", "Quantos HCPs por qualquer canal?",
            "Ampliar alcance.",
            [
                kpi("k_cobmulti", "HCPs cobertos Multi (total)", "consultores", agg="sum", field="hcpsCobertosMulti"),
                ranking("r_multi", "ICP-Multi por consultor", "consultores", "consultor", "pctCoberturaMulti", fmt="percent", dir="asc", extra=[C_SF]),
            ])},
    ]})

    # 11. BENCHMARK E METAS ---------------------------------------------------
    S.append({"id": "benchmark", "title": "Benchmark e Metas", "icon": "award",
              "descricao": "Comparação entre forças, gerências e contra metas.",
              "subsections": [
        {"id": "sf", "title": "Benchmark entre SFs", "page": _page(
            "Benchmark e Metas", "benchmark", "Benchmark SF", "bm_sf",
            "Benchmark entre SFs", "Quais SFs lideram?",
            "Disseminar boas práticas.",
            [
                chart("c_sf_vdia", "Vis/dia por SF", "sales_forces", "bar", label="sales_force", value="vis_dia_media"),
                chart("c_sf_aus", "Ausência por SF", "sales_forces", "bar", label="sales_force", value="pct_ausencia_media"),
                table("t_sf", "Benchmark por SF", "sales_forces",
                      [C_SF, col("painel_medio", "Painel médio", "decimal2"), col("vis_dia_media", "Vis/dia", "decimal2"),
                       col("pct_ausencia_media", "Ausência", "percent"), col("freq_medico_mes_medio", "Freq/méd", "decimal2")], sort="vis_dia_media", limit=20),
            ])},
        {"id": "gd", "title": "Benchmark entre GDs", "page": _page(
            "Benchmark e Metas", "benchmark", "Benchmark GD", "bm_gd",
            "Benchmark entre GDs", "Quais GDs lideram?",
            "Nivelar gerências.",
            [
                chart("c_gd_vdia", "Vis/dia por GD", "gds", "bar", label="gd", value="vis_dia_media"),
                table("t_gd", "Benchmark por GD", "gds",
                      [C_GD, col("n_consultores", "Consultores", "int"), col("painel_medio", "Painel médio", "decimal2"),
                       col("vis_dia_media", "Vis/dia", "decimal2"), col("pct_ausencia_media", "Ausência", "percent")], sort="vis_dia_media", limit=20),
            ])},
        {"id": "metas", "title": "Metas vs Realizado", "page": _page(
            "Benchmark e Metas", "benchmark", "Metas vs Realizado", "bm_metas",
            "Metas vs Realizado", "O painel está próximo da meta?",
            "Acompanhar metas de painel.",
            [
                kpi("k_meta", "Meta de painel", "kpis", field="meta_painel"),
                kpi("k_medio", "Painel médio realizado", "kpis", field="painel_medio", fmt="decimal2"),
                ranking("r_painel", "Painel por consultor", "consultores", "consultor", "painel_size", extra=[C_SF]),
            ])},
    ]})

    # 12. SIMULADOR E PLANEJAMENTO -------------------------------------------
    S.append({"id": "simulador", "title": "Simulador e Planejamento", "icon": "sliders",
              "descricao": "Transformar diagnóstico em cenário futuro.",
              "subsections": [
        {"id": "capacidade", "title": "Simulador de Capacidade", "page": _page(
            "Simulador e Planejamento", "simulador", "Simulador de Capacidade", "sim_cap",
            "Simulador de Capacidade", "Quantos médicos é possível cobrir?",
            "Planejar metas factíveis.",
            [
                simulator("sim_capacidade", "Simulador de capacidade",
                          [{"id": "dias_uteis", "label": "Dias úteis/ano", "default": 252},
                           {"id": "pct_ausencia", "label": "% ausência esperada", "default": 23},
                           {"id": "visitas_dia", "label": "Visitas/dia alvo", "default": 6},
                           {"id": "freq_alvo", "label": "Frequência alvo/médico", "default": 4}],
                          [{"id": "dias_disp", "label": "Dias disponíveis", "formula": "dias_uteis*(1-pct_ausencia/100)"},
                           {"id": "visitas", "label": "Visitas possíveis/ano", "formula": "dias_uteis*(1-pct_ausencia/100)*visitas_dia"},
                           {"id": "cobertura", "label": "Médicos cobríveis", "formula": "dias_uteis*(1-pct_ausencia/100)*visitas_dia/freq_alvo"}]),
            ])},
        {"id": "planejamento", "title": "Planejamento de Cobertura", "page": _page(
            "Simulador e Planejamento", "simulador", "Planejamento de Cobertura", "sim_plano",
            "Planejamento de Cobertura", "Onde está o maior gap de capacidade?",
            "Definir metas individuais.",
            [
                table("t_plano", "Base para planejamento", "consultores",
                      [C_CONS, col("painel_size", "Painel", "int"), col("hcpsCobertosF2F", "Cobertos F2F", "int"),
                       col("pctCoberturaF2F", "ICP-F2F", "percent"), col("gap_capacidade_mes", "Gap capac./mês", "decimal2")],
                      sort="gap_capacidade_mes", limit=80),
            ])},
        {"id": "cenarios", "title": "Cenários Executivos", "page": _page(
            "Simulador e Planejamento", "simulador", "Cenários Executivos", "sim_cen",
            "Cenários Executivos", "Qual o impacto de mudar metas?",
            "Apoiar decisões de liderança.",
            [
                simulator("sim_cenario", "Cenário de cobertura",
                          [{"id": "painel_total", "label": "Painel total", "default": 2842},
                           {"id": "meta_cobertura", "label": "Meta cobertura (%)", "default": 80},
                           {"id": "freq_alvo", "label": "Frequência alvo", "default": 4}],
                          [{"id": "medicos", "label": "Médicos a cobrir", "formula": "painel_total*meta_cobertura/100"},
                           {"id": "visitas", "label": "Visitas necessárias", "formula": "painel_total*meta_cobertura/100*freq_alvo"}]),
            ])},
    ]})

    # 13. OPORTUNIDADES E PLANO DE AÇÃO --------------------------------------
    S.append({"id": "oportunidades", "title": "Oportunidades e Plano de Ação", "icon": "flag",
              "descricao": "Transformar diagnóstico em ação priorizada.",
              "subsections": [
        {"id": "prio", "title": "Oportunidades Prioritárias", "page": _page(
            "Oportunidades e Plano de Ação", "oportunidades", "Oportunidades Prioritárias", "op_prio",
            "Oportunidades Prioritárias", "Onde agir primeiro?",
            "Sequenciar por impacto.",
            [
                ranking("r_cob", "Menor cobertura F2F (agir)", "consultores", "consultor", "pctCoberturaF2F", fmt="percent", dir="asc", extra=[C_SF, col("painel_size", "Painel", "int")]),
                ranking("r_mccp", "Menor cumprimento MCCP (agir)", "consultores", "consultor", "mccp_pct_cumprido", fmt="percent", dir="asc", extra=[C_SF]),
                export_block("e_op", "Exportar oportunidades", "consultores"),
            ])},
        {"id": "plano_cons", "title": "Plano de Ação por Consultor", "page": _page(
            "Oportunidades e Plano de Ação", "oportunidades", "Plano por Consultor", "op_cons",
            "Plano de Ação por Consultor", "Qual ação por consultor?",
            "Atribuir ações individuais.",
            [
                table("t_plano", "Plano por consultor", "consultores",
                      [C_CONS, C_SF, col("pctCoberturaF2F", "ICP-F2F", "percent"), col("mccp_pct_cumprido", "MCCP", "percent"),
                       col("pct_ausencia", "Ausência", "percent"), col("gap_dias_nao_explicados", "Gap dias", "decimal2")],
                      sort="pctCoberturaF2F", dir="asc", limit=80),
            ])},
        {"id": "plano_sf", "title": "Plano de Ação por SF / GD", "page": _page(
            "Oportunidades e Plano de Ação", "oportunidades", "Plano por SF/GD", "op_sf",
            "Plano de Ação por SF / GD", "Onde concentrar esforço por força?",
            "Priorizar por força de vendas.",
            [
                chart("c_sf_cob", "Cobertura F2F por SF", "consultores", "bar", label="sales_force", value="pctCoberturaF2F"),
            ])},
        {"id": "backlog", "title": "Backlog Operacional", "page": _page(
            "Oportunidades e Plano de Ação", "oportunidades", "Backlog Operacional", "op_backlog",
            "Backlog Operacional", "Que correções operacionais estão pendentes?",
            "Organizar saneamento.",
            [
                ranking("r_gap", "Maior gap de dias não explicados", "consultores", "consultor", "gap_dias_nao_explicados", fmt="decimal2", extra=[C_SF]),
            ])},
    ]})

    # 14. SAÚDE DOS DADOS -----------------------------------------------------
    S.append({"id": "saude_dados", "title": "Saúde dos Dados", "icon": "database",
              "descricao": "Completude, exclusões e afastados.",
              "subsections": [
        {"id": "completude", "title": "Completude", "page": _page(
            "Saúde dos Dados", "saude_dados", "Completude", "sd_comp",
            "Completude", "O universo está completo?",
            "Confiar nos números.",
            [
                kpi("k_cons", "Consultores no payload", "consultores", agg="count"),
                kpi("k_sf", "Sales Forces", "kpis", field="n_sf"),
                kpi("k_gd", "GDs", "kpis", field="n_gd"),
                kpi("k_med", "Médicos no dashboard", "medicos", agg="count"),
            ])},
        {"id": "afastados", "title": "Afastados", "page": _page(
            "Saúde dos Dados", "saude_dados", "Afastados", "sd_afast",
            "Afastados", "Quem está afastado (excluído de médias/rankings)?",
            "Tratar afastados corretamente.",
            [
                table("t_afast", "Consultores afastados", "consultores",
                      [C_CONS, C_SF, col("afastado", "Afastado"), col("afastado_motivo", "Motivo"), col("afastado_periodo", "Período")],
                      sort="afastado", limit=80),
            ])},
        {"id": "exclusoes", "title": "Exclusões", "page": _page(
            "Saúde dos Dados", "saude_dados", "Exclusões", "sd_excl",
            "Exclusões", "Quais SFs foram excluídas do universo?",
            "Tornar exclusões explícitas.",
            [
                audit("a_excl", "SFs excluídas", "meta.sfs_excluidas"),
            ])},
    ]})

    # 15. GOVERNANÇA E AUDITORIA ---------------------------------------------
    S.append({"id": "governanca", "title": "Governança e Auditoria", "icon": "shield",
              "descricao": "Confiança nos dados, regras, exclusões e metodologia.",
              "subsections": [
        {"id": "fontes", "title": "Fontes e Período", "page": _page(
            "Governança e Auditoria", "governanca", "Fontes e Período", "gov_fontes",
            "Fontes e Período", "Quais bases e janela alimentam o portal?",
            "Rastrear origem dos números.",
            [
                audit("a_meta", "Metadados do processamento", "meta.real_meta"),
            ])},
        {"id": "metodologia", "title": "Metodologia dos Indicadores", "page": _page(
            "Governança e Auditoria", "governanca", "Metodologia", "gov_metod",
            "Metodologia dos Indicadores", "Como cada indicador é calculado?",
            "Padronizar leitura.",
            [
                methodology("m_kpi", "Fórmulas (processar.py)", [
                    "ICP-F2F = HCPs alvo com ≥1 interação F2F / HCPs alvo × 100.",
                    "ICP-Multi = HCPs alvo com ≥1 canal qualquer / HCPs alvo × 100.",
                    "HCP alvo = painel (snapshot ≤ mês fechado) ∩ MCCP (meta>0 no quarter).",
                    "MCCP % cumprido = realizado / meta do trimestre × 100.",
                    "Visitas/dia = visitas F2F submetidas / dias trabalhados.",
                    "% ausência = dias de ausência / dias úteis (TOT deduplicado).",
                    "IPT = índice de produtividade territorial; IPA = aderência ao plano individual.",
                    "Deduplicação e exclusões (SFs, afastados) seguem o processar.py original — não foram alteradas.",
                ]),
            ])},
        {"id": "glossario", "title": "Glossário", "page": _page(
            "Governança e Auditoria", "governanca", "Glossário", "gov_gloss",
            "Glossário", "O que cada sigla significa?",
            "Linguagem comum.",
            [
                methodology("m_gloss", "Glossário", [
                    "MCCP = plano de ciclo multicanal (meta de interações por médico/quarter).",
                    "F2F = face to face (visita presencial).",
                    "HCP = profissional de saúde (médico do painel).",
                    "ICP = índice de cobertura de painel.",
                    "MAT = moving annual total (12 meses móveis).",
                    "GD = gerente distrital; SF = sales force.",
                ]),
            ])},
        {"id": "qualidade", "title": "Qualidade e Completude", "page": _page(
            "Governança e Auditoria", "governanca", "Qualidade e Completude", "gov_qual",
            "Qualidade e Completude", "Qual o nível de confiança dos dados?",
            "Avaliar confiança geral.",
            [
                kpi("k_cons", "Consultores", "kpis", field="n_consultores"),
                kpi("k_painel", "Painel total", "kpis", field="painel_total_time"),
                export_block("e_audit", "Exportar consultores (auditoria)", "consultores"),
            ])},
    ]})

    return S
