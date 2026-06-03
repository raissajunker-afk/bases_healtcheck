"""Registry central do portal analítico.

Declara a hierarquia completa: Macro Seção -> Sub Seção -> Página -> Blocos.
Esta é a ÚNICA fonte de verdade da navegação. O frontend (router/registry.js)
consome esta estrutura serializada em JSON e renderiza cada página montando
componentes reutilizáveis a partir da configuração de cada bloco.

Adicionar uma nova página = adicionar um dicionário aqui. Não é preciso
escrever JS novo: os blocos são resolvidos por configuração contra os
`datasets` do payload.

Tipos de bloco suportados pelo motor de renderização:
  kpi        - cartão de indicador (agg sobre um dataset)
  table      - tabela detalhada (colunas + ordenação + limite)
  ranking    - tabela com barra proporcional em um campo
  chart      - gráfico SVG (line | bar | donut | heatmap)
  insight    - insight automático (regras avaliadas no cliente)
  export     - botão de exportação CSV de um dataset
  methodology- cartão metodológico/glossário
  alert      - faixa de alerta condicional
  empty      - placeholder "em construção / sem dado"
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# Construtores de bloco (reduzem repetição e padronizam o schema)
# --------------------------------------------------------------------------
def kpi(id, title, dataset, *, agg="sum", field=None, num=None, den=None,
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


def empty(id, title, msg="Bloco previsto pela infraestrutura — será habilitado quando a base correspondente estiver disponível."):
    return {"type": "empty", "id": id, "title": title, "message": msg}


def col(field, label, fmt="text"):
    return {"field": field, "label": label, "format": fmt}


# Atalhos de colunas comuns
C_CONSULTOR = col("consultor", "Consultor")
C_SF = col("sales_force", "Sales Force")
C_GD = col("gd", "GD")


def _page(section, section_id, subsection, page_id, title, question, decision, blocks):
    return {
        "id": page_id,
        "section": section,
        "sectionId": section_id,
        "subsection": subsection,
        "title": title,
        "businessQuestion": question,
        "decisionSupported": decision,
        "blocks": blocks,
    }


# --------------------------------------------------------------------------
# Definição das 15 macro seções
# --------------------------------------------------------------------------
def build_registry() -> list[dict]:
    secoes: list[dict] = []

    # ===================================================================
    # 1. EXECUTIVE OVERVIEW
    # ===================================================================
    secoes.append({
        "id": "executive", "title": "Executive Overview", "icon": "compass",
        "descricao": "Leitura rápida para liderança com os principais sinais do negócio.",
        "subsections": [
            {"id": "snapshot", "title": "Snapshot Executivo", "page": _page(
                "Executive Overview", "executive", "Snapshot Executivo", "exec_snapshot",
                "Snapshot Executivo", "Qual é a fotografia atual da operação comercial?",
                "Leitura rápida dos principais sinais e onde olhar primeiro.",
                [
                    kpi("k_consultores", "Consultores ativos", "consultores", agg="count"),
                    kpi("k_painel", "Médicos no painel", "consultores", agg="sum", field="painel"),
                    kpi("k_painel_medio", "Painel médio/consultor", "consultores", agg="mean", field="painel"),
                    kpi("k_vdia", "Visitas/dia média", "consultores", agg="ratio", num="visitas", den="dias_com_visita", fmt="decimal2", benchmark="visitas_dia"),
                    kpi("k_cobf2f", "Cobertura F2F", "consultores", agg="ratio", num="hcp_coberto_f2f", den="hcp_alvo", fmt="percent", benchmark="pct_cobertura_f2f"),
                    kpi("k_mccp", "Visitas dentro do MCCP", "consultores", agg="mean", field="pct_dentro_mccp", fmt="percent", benchmark="pct_dentro_mccp"),
                    chart("c_evolucao", "Evolução de visitas (mensal)", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Visitas"}, {"field": "visitas_f2f", "label": "F2F"}]),
                    insight("i_exec", "Insight executivo", [
                        {"if": {"field": "k_cobf2f", "op": "<", "value": 60}, "level": "risco", "text": "Cobertura F2F global abaixo de 60%. Priorizar reforço de cobertura."},
                        {"if": {"field": "k_cobf2f", "op": ">=", "value": 80}, "level": "oportunidade", "text": "Cobertura F2F saudável. Foco em frequência e qualidade de execução."},
                    ]),
                ])},
            {"id": "alertas", "title": "Alertas Prioritários", "page": _page(
                "Executive Overview", "executive", "Alertas Prioritários", "exec_alertas",
                "Alertas Prioritários", "Onde estão os maiores riscos agora?",
                "Direcionar atenção da liderança para os consultores em situação crítica.",
                [
                    ranking("r_prioridade", "Top consultores por prioridade de ação", "consultores", "consultor", "score_prioridade", fmt="decimal2", extra=[C_SF, col("pct_cobertura_f2f", "Cob. F2F", "percent")]),
                    ranking("r_baixa_cob", "Menor cobertura F2F", "consultores", "consultor", "pct_cobertura_f2f", fmt="percent", dir="asc", extra=[C_SF, col("painel", "Painel", "int")]),
                    export_block("e_alertas", "Exportar consultores priorizados", "consultores"),
                ])},
            {"id": "evolucao", "title": "Evolução Geral", "page": _page(
                "Executive Overview", "executive", "Evolução Geral", "exec_evolucao",
                "Evolução Geral", "Como o volume de atividade vem evoluindo?",
                "Identificar tendências e quedas de ritmo ao longo do tempo.",
                [
                    chart("c_serie", "Visitas por mês", "serie_visitas", "bar", x="ym", series=[{"field": "visitas", "label": "Visitas"}]),
                    chart("c_medicos", "Médicos únicos por mês", "serie_visitas", "line", x="ym", series=[{"field": "medicos_unicos", "label": "Médicos únicos"}]),
                    chart("c_ausencias", "Dias de ausência por mês", "serie_ausencias", "bar", x="ym", series=[{"field": "dias_ausencia", "label": "Dias de ausência"}]),
                ])},
            {"id": "por_sf", "title": "Resumo por Sales Force", "page": _page(
                "Executive Overview", "executive", "Resumo por Sales Force", "exec_sf",
                "Resumo por Sales Force", "Como cada Sales Force se compara?",
                "Comparar performance e cobertura entre forças de vendas.",
                [
                    table("t_sf", "Indicadores por Sales Force", "consultores",
                          [C_SF, col("visitas", "Visitas", "int"), col("pct_cobertura_f2f", "Cob. F2F", "percent"), col("pct_dentro_mccp", "Dentro MCCP", "percent")],
                          sort="visitas", limit=30),
                    chart("c_sf", "Cobertura F2F por Sales Force", "consultores", "bar", label="sales_force", value="pct_cobertura_f2f"),
                ])},
            {"id": "por_gd", "title": "Resumo por GD", "page": _page(
                "Executive Overview", "executive", "Resumo por GD", "exec_gd",
                "Resumo por GD", "Como cada GD se compara?",
                "Comparar performance entre gerências distritais.",
                [
                    table("t_gd", "Indicadores por GD", "consultores",
                          [C_GD, col("visitas", "Visitas", "int"), col("pct_cobertura_f2f", "Cob. F2F", "percent"), col("pct_ausencia", "Ausência", "percent")],
                          sort="visitas", limit=30),
                    chart("c_gd", "Visitas por GD", "consultores", "bar", label="gd", value="visitas"),
                ])},
        ],
    })

    # ===================================================================
    # 2. PERFORMANCE COMERCIAL
    # ===================================================================
    secoes.append({
        "id": "performance", "title": "Performance Comercial", "icon": "trend",
        "descricao": "Produtividade comercial e execução do time.",
        "subsections": [
            {"id": "produtividade", "title": "Produtividade Geral", "page": _page(
                "Performance Comercial", "performance", "Produtividade Geral", "perf_prod",
                "Produtividade Geral", "O time está com bom ritmo de execução?",
                "Avaliar volume e ritmo de visitas do time.",
                [
                    kpi("k_vis", "Visitas totais", "consultores", agg="sum", field="visitas"),
                    kpi("k_f2f", "Visitas F2F", "consultores", agg="sum", field="visitas_f2f"),
                    kpi("k_vdia", "Visitas/dia média", "consultores", agg="ratio", num="visitas", den="dias_com_visita", fmt="decimal2", benchmark="visitas_dia"),
                    kpi("k_dias", "Dias com visita", "consultores", agg="sum", field="dias_com_visita"),
                    chart("c_dist", "Distribuição de visitas/dia", "consultores", "bar", label="consultor", value="visitas_dia"),
                    chart("c_serie", "Série de visitas", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Visitas"}]),
                    insight("i_prod", "Insight de produtividade", [
                        {"if": {"field": "k_vdia", "op": "<", "value": 5}, "level": "alerta", "text": "Visitas/dia abaixo do benchmark (5). Verificar agenda e capacidade."},
                    ]),
                ])},
            {"id": "por_consultor", "title": "Performance por Consultor", "page": _page(
                "Performance Comercial", "performance", "Performance por Consultor", "perf_consultor",
                "Performance por Consultor", "Quem está performando e quem precisa de apoio?",
                "Identificar consultores para reconhecimento e para suporte.",
                [
                    table("t_cons", "Performance por consultor", "consultores",
                          [C_CONSULTOR, C_SF, col("visitas", "Visitas", "int"), col("visitas_dia", "Vis/dia", "decimal2"), col("medicos_visitados", "Médicos", "int"), col("pct_cobertura_f2f", "Cob. F2F", "percent")],
                          sort="visitas", limit=100),
                    export_block("e_cons", "Exportar base de consultores", "consultores"),
                ])},
            {"id": "alta_perf", "title": "Ranking de Alta Performance", "page": _page(
                "Performance Comercial", "performance", "Ranking de Alta Performance", "perf_alta",
                "Ranking de Alta Performance", "Quem são os destaques do time?",
                "Reconhecer e estudar boas práticas dos melhores.",
                [
                    ranking("r_top_vis", "Top por visitas", "consultores", "consultor", "visitas", extra=[C_SF]),
                    ranking("r_top_cob", "Top por cobertura F2F", "consultores", "consultor", "pct_cobertura_f2f", fmt="percent", extra=[C_SF]),
                ])},
            {"id": "baixa_perf", "title": "Ranking de Baixa Performance", "page": _page(
                "Performance Comercial", "performance", "Ranking de Baixa Performance", "perf_baixa",
                "Ranking de Baixa Performance", "Quem precisa de atenção imediata?",
                "Direcionar apoio para os consultores com menor execução.",
                [
                    ranking("r_low_vis", "Menor volume de visitas", "consultores", "consultor", "visitas", dir="asc", extra=[C_SF]),
                    ranking("r_low_cob", "Menor cobertura F2F", "consultores", "consultor", "pct_cobertura_f2f", fmt="percent", dir="asc", extra=[C_SF]),
                    export_block("e_low", "Exportar para plano de apoio", "consultores"),
                ])},
            {"id": "comparativo", "title": "Comparativo MAT vs Recente", "page": _page(
                "Performance Comercial", "performance", "Comparativo MAT vs Recente", "perf_comp",
                "Comparativo MAT vs Recente", "O ritmo recente está acima ou abaixo do histórico?",
                "Detectar aceleração ou desaceleração recente.",
                [
                    chart("c_comp", "Visitas por mês (use o filtro de janela)", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Visitas"}, {"field": "visitas_f2f", "label": "F2F"}]),
                    methodology("m_janela", "Como ler este comparativo", [
                        "Use o filtro de janela no topo para alternar entre MAT 12m, últimos 3m e mês fechado.",
                        "A série mensal é recortada conforme a janela selecionada.",
                    ]),
                ])},
        ],
    })

    # ===================================================================
    # 3. COBERTURA E PAINEL
    # ===================================================================
    secoes.append({
        "id": "cobertura", "title": "Cobertura e Painel", "icon": "target",
        "descricao": "Estamos cobrindo os médicos certos?",
        "subsections": [
            {"id": "mccp", "title": "Cobertura MCCP", "page": _page(
                "Cobertura e Painel", "cobertura", "Cobertura MCCP", "cob_mccp",
                "Cobertura MCCP", "Estamos cobrindo os HCPs que estão no plano?",
                "Priorizar reforço de cobertura e identificar médicos descobertos.",
                [
                    kpi("k_mccp_alvo", "HCPs alvo MCCP", "consultores", agg="sum", field="hcp_mccp"),
                    kpi("k_cob_mccp", "Cobertura MCCP F2F", "consultores", agg="ratio", num="hcp_coberto_f2f", den="hcp_mccp", fmt="percent", benchmark="pct_cobertura_mccp"),
                    kpi("k_dentro_mccp", "Visitas dentro do MCCP", "consultores", agg="mean", field="pct_dentro_mccp", fmt="percent", benchmark="pct_dentro_mccp"),
                    ranking("r_cons_mccp", "Cobertura MCCP por consultor", "consultores", "consultor", "pct_cobertura_mccp", fmt="percent", dir="asc", extra=[C_SF]),
                    table("t_mccp_desc", "Médicos MCCP sem F2F", "medicos",
                          [col("nome_medico", "Médico"), col("crm", "CRM"), col("especialidade", "Especialidade"), C_CONSULTOR, col("ultima_visita", "Última visita")],
                          sort="visitas", dir="asc", limit=100),
                    insight("i_mccp", "Insight de cobertura", [
                        {"if": {"field": "k_cob_mccp", "op": "<", "value": 60}, "level": "risco", "text": "Cobertura MCCP abaixo de 60%: risco de não atingir o plano."},
                    ]),
                    export_block("e_mccp", "Exportar médicos MCCP descobertos", "medicos"),
                    methodology("m_mccp", "Metodologia", [
                        "MCCP = médicos marcados no plano de cobertura.",
                        "Cobertura MCCP F2F = médicos MCCP com ao menos 1 visita presencial / total MCCP.",
                    ]),
                ])},
            {"id": "f2f", "title": "Cobertura F2F", "page": _page(
                "Cobertura e Painel", "cobertura", "Cobertura F2F", "cob_f2f",
                "Cobertura F2F", "Quantos médicos do painel recebem visita presencial?",
                "Medir alcance presencial e priorizar gaps.",
                [
                    kpi("k_alvo", "HCPs alvo", "consultores", agg="sum", field="hcp_alvo"),
                    kpi("k_cob", "Cobertura F2F", "consultores", agg="ratio", num="hcp_coberto_f2f", den="hcp_alvo", fmt="percent", benchmark="pct_cobertura_f2f"),
                    kpi("k_multi", "Cobertura multicanal", "consultores", agg="ratio", num="hcp_coberto_f2f", den="hcp_alvo", fmt="percent", benchmark="pct_cobertura_multi"),
                    chart("c_cob_sf", "Cobertura F2F por SF", "consultores", "bar", label="sales_force", value="pct_cobertura_f2f"),
                    ranking("r_cob", "Ranking de cobertura por consultor", "consultores", "consultor", "pct_cobertura_f2f", fmt="percent", extra=[C_SF]),
                ])},
            {"id": "fora_painel", "title": "Fora de Painel", "page": _page(
                "Cobertura e Painel", "cobertura", "Fora de Painel", "cob_fora",
                "Fora de Painel", "Quanta energia vai para médicos fora do painel?",
                "Reduzir esforço fora do alvo e sanear o painel.",
                [
                    kpi("k_dentro", "Visitas dentro do painel", "consultores", agg="mean", field="pct_dentro_painel", fmt="percent", benchmark="pct_dentro_painel"),
                    ranking("r_fora", "Maior % fora do painel", "consultores", "consultor", "pct_dentro_painel", fmt="percent", dir="asc", extra=[C_SF]),
                ])},
            {"id": "turnover", "title": "Turnover de Painel", "page": _page(
                "Cobertura e Painel", "cobertura", "Turnover de Painel", "cob_turnover",
                "Turnover de Painel", "O painel está estável ou muda demais?",
                "Avaliar estabilidade do painel ao longo do tempo.",
                [
                    empty("e_turnover", "Turnover de painel", "Requer dois snapshots de painel em datas distintas. Disponibilize bases de painel datadas para habilitar."),
                ])},
            {"id": "parados", "title": "Médicos Parados / Não Visitados", "page": _page(
                "Cobertura e Painel", "cobertura", "Médicos Parados", "cob_parados",
                "Médicos Parados", "Quais médicos do painel não são visitados?",
                "Reativar médicos sem visita recente.",
                [
                    kpi("k_nao_cob", "Médicos não cobertos", "consultores", agg="sum", field="hcp_nao_coberto"),
                    table("t_parados", "Médicos sem visita", "medicos",
                          [col("nome_medico", "Médico"), col("crm", "CRM"), col("especialidade", "Especialidade"), C_CONSULTOR, col("visitas", "Visitas", "int")],
                          sort="visitas", dir="asc", limit=150),
                    export_block("e_parados", "Exportar médicos parados", "medicos"),
                ])},
        ],
    })

    # ===================================================================
    # 4. VISITAÇÃO E FREQUÊNCIA
    # ===================================================================
    secoes.append({
        "id": "visitacao", "title": "Visitação e Frequência", "icon": "calendar",
        "descricao": "Ritmo, cadência e consistência de visitação.",
        "subsections": [
            {"id": "frequencia", "title": "Frequência Real", "page": _page(
                "Visitação e Frequência", "visitacao", "Frequência Real", "vis_freq",
                "Frequência Real", "Com que frequência os médicos são visitados?",
                "Ajustar cadência por médico.",
                [
                    kpi("k_freq", "Frequência média/médico", "freq_medico", agg="mean", field="frequencia", fmt="decimal2", benchmark="freq_media_medico"),
                    kpi("k_medicos", "Médicos visitados", "freq_medico", agg="count"),
                    ranking("r_freq", "Médicos mais visitados", "freq_medico", "nome_medico", "frequencia", extra=[C_CONSULTOR]),
                    table("t_freq", "Frequência por médico", "freq_medico",
                          [col("nome_medico", "Médico"), col("especialidade", "Especialidade"), C_CONSULTOR, col("frequencia", "Frequência", "int"), col("visitas", "Visitas", "int")],
                          sort="frequencia", limit=100),
                ])},
            {"id": "consistencia", "title": "Consistência Mensal", "page": _page(
                "Visitação e Frequência", "visitacao", "Consistência Mensal", "vis_consist",
                "Consistência Mensal", "O ritmo é constante mês a mês?",
                "Detectar meses fracos e sazonalidade.",
                [
                    chart("c_mes", "Visitas por mês", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Visitas"}]),
                ])},
            {"id": "vis_dia", "title": "Visitas por Dia", "page": _page(
                "Visitação e Frequência", "visitacao", "Visitas por Dia", "vis_dia",
                "Visitas por Dia", "A produtividade diária está adequada?",
                "Otimizar agenda diária.",
                [
                    kpi("k_vdia", "Visitas/dia média", "consultores", agg="ratio", num="visitas", den="dias_com_visita", fmt="decimal2", benchmark="visitas_dia"),
                    ranking("r_vdia", "Visitas/dia por consultor", "consultores", "consultor", "visitas_dia", fmt="decimal2", extra=[C_SF]),
                ])},
            {"id": "sazonalidade", "title": "Sazonalidade", "page": _page(
                "Visitação e Frequência", "visitacao", "Sazonalidade", "vis_sazon",
                "Sazonalidade", "Há padrões sazonais de visitação?",
                "Planejar picos e vales de atividade.",
                [
                    chart("c_sazon", "Médicos únicos por mês", "serie_visitas", "bar", x="ym", series=[{"field": "medicos_unicos", "label": "Médicos únicos"}]),
                ])},
            {"id": "medico_freq", "title": "Médico × Frequência", "page": _page(
                "Visitação e Frequência", "visitacao", "Médico × Frequência", "vis_medico",
                "Médico × Frequência", "Quem é visitado uma única vez ou em excesso?",
                "Reequilibrar cadência entre médicos.",
                [
                    table("t_unica", "Médicos visitados uma única vez", "freq_medico",
                          [col("nome_medico", "Médico"), col("especialidade", "Especialidade"), C_CONSULTOR, col("frequencia", "Frequência", "int")],
                          sort="frequencia", dir="asc", limit=100),
                    export_block("e_freq", "Exportar frequência por médico", "freq_medico"),
                ])},
        ],
    })

    # ===================================================================
    # 5. EFICIÊNCIA TERRITORIAL
    # ===================================================================
    secoes.append({
        "id": "territorio", "title": "Eficiência Territorial", "icon": "map",
        "descricao": "O território está bem desenhado e bem executado?",
        "subsections": [
            {"id": "perfil", "title": "Perfil de Setor", "page": _page(
                "Eficiência Territorial", "territorio", "Perfil de Setor", "ter_perfil",
                "Perfil de Setor", "Como se distribui o perfil dos setores?",
                "Calibrar expectativas por tipo de território.",
                [
                    chart("c_perfil", "Consultores por perfil de deslocamento", "consultores", "donut", label="perfil_deslocamento", value="consultor_key"),
                    table("t_perfil", "Perfil territorial por consultor", "consultores",
                          [C_CONSULTOR, col("uf_sede", "UF Sede"), col("tipo_setor", "Tipo Setor"), col("perfil_deslocamento", "Deslocamento")],
                          sort="cidades_visitadas", limit=100),
                ])},
            {"id": "deslocamento", "title": "Deslocamento", "page": _page(
                "Eficiência Territorial", "territorio", "Deslocamento", "ter_desloc",
                "Deslocamento", "Quanto o time se desloca para fora da sede?",
                "Avaliar custo e eficiência de deslocamento.",
                [
                    kpi("k_uf_sede", "% visitas na UF sede", "consultores", agg="mean", field="pct_visitas_uf_sede", fmt="percent"),
                    ranking("r_ufs", "Mais UFs visitadas", "consultores", "consultor", "ufs_visitadas", extra=[C_SF]),
                ])},
            {"id": "brickagem", "title": "Brickagem", "page": _page(
                "Eficiência Territorial", "territorio", "Brickagem", "ter_brick",
                "Brickagem", "A cobertura de bricks está adequada?",
                "Identificar bricks pouco trabalhados.",
                [
                    ranking("r_bricks", "Bricks visitados por consultor", "consultores", "consultor", "bricks_visitados", extra=[C_SF]),
                ])},
            {"id": "geografica", "title": "Cobertura Geográfica", "page": _page(
                "Eficiência Territorial", "territorio", "Cobertura Geográfica", "ter_geo",
                "Cobertura Geográfica", "Quantas cidades e UFs cada consultor cobre?",
                "Dimensionar a amplitude geográfica.",
                [
                    table("t_geo", "Amplitude geográfica", "consultores",
                          [C_CONSULTOR, col("cidades_visitadas", "Cidades", "int"), col("ufs_visitadas", "UFs", "int"), col("pct_visitas_uf_sede", "% UF sede", "percent")],
                          sort="cidades_visitadas", limit=100),
                ])},
            {"id": "score", "title": "Score de Território", "page": _page(
                "Eficiência Territorial", "territorio", "Score de Território", "ter_score",
                "Score de Território", "Quais territórios estão mais eficientes?",
                "Priorizar redesenho territorial.",
                [
                    ranking("r_score", "Score territorial", "consultores", "consultor", "score_territorio", fmt="decimal2", extra=[C_SF]),
                    insight("i_ter", "Insight de carga territorial", [
                        {"if": {"field": "k_uf_sede", "op": "<", "value": 50}, "level": "alerta", "text": "Menos da metade das visitas ocorre na UF sede — alta carga de deslocamento."},
                    ]),
                ])},
        ],
    })

    # ===================================================================
    # 6. AUSÊNCIAS E CAPACIDADE
    # ===================================================================
    secoes.append({
        "id": "ausencias", "title": "Ausências e Capacidade", "icon": "clock",
        "descricao": "Perda de capacidade, ausências e dias não explicados.",
        "subsections": [
            {"id": "total", "title": "Ausência Total", "page": _page(
                "Ausências e Capacidade", "ausencias", "Ausência Total", "aus_total",
                "Ausência Total", "Quanto da capacidade é perdida em ausências?",
                "Dimensionar impacto das ausências na capacidade.",
                [
                    kpi("k_dias_aus", "Dias de ausência (total)", "consultores", agg="sum", field="dias_ausencia"),
                    kpi("k_pct_aus", "% ausência médio", "consultores", agg="mean", field="pct_ausencia", fmt="percent", benchmark="pct_ausencia"),
                    kpi("k_capacidade", "Capacidade disponível (dias)", "consultores", agg="sum", field="capacidade_disponivel"),
                    ranking("r_aus", "Maior % de ausência", "consultores", "consultor", "pct_ausencia", fmt="percent", extra=[C_SF]),
                    chart("c_aus", "Ausências por mês", "serie_ausencias", "bar", x="ym", series=[{"field": "dias_ausencia", "label": "Dias"}]),
                ])},
            {"id": "produtiva", "title": "Ausência Produtiva", "page": _page(
                "Ausências e Capacidade", "ausencias", "Ausência Produtiva", "aus_prod",
                "Ausência Produtiva", "Quanto é ausência produtiva (treino, reunião)?",
                "Separar ausência produtiva de perda real.",
                [
                    kpi("k_prod", "Dias produtivos (ausência)", "consultores", agg="sum", field="dias_produtiva"),
                    ranking("r_prod", "Ausência produtiva por consultor", "consultores", "consultor", "dias_produtiva", fmt="decimal2", extra=[C_SF]),
                ])},
            {"id": "pessoal", "title": "Ausência Pessoal", "page": _page(
                "Ausências e Capacidade", "ausencias", "Ausência Pessoal", "aus_pessoal",
                "Ausência Pessoal", "Quanto é ausência pessoal (férias, atestado)?",
                "Planejar coberturas e backups.",
                [
                    kpi("k_pessoal", "Dias pessoais (ausência)", "consultores", agg="sum", field="dias_pessoal"),
                    ranking("r_pessoal", "Ausência pessoal por consultor", "consultores", "consultor", "dias_pessoal", fmt="decimal2", extra=[C_SF]),
                ])},
            {"id": "capacidade", "title": "Capacidade Disponível", "page": _page(
                "Ausências e Capacidade", "ausencias", "Capacidade Disponível", "aus_cap",
                "Capacidade Disponível", "Qual a capacidade real disponível?",
                "Planejar metas realistas de visitação.",
                [
                    kpi("k_uteis", "Dias úteis no período", "consultores", agg="mean", field="dias_uteis"),
                    kpi("k_cap", "Capacidade disponível (dias)", "consultores", agg="sum", field="capacidade_disponivel"),
                    kpi("k_gap", "Gap não explicado (dias)", "consultores", agg="sum", field="gap_nao_explicado"),
                    table("t_cap", "Capacidade por consultor", "consultores",
                          [C_CONSULTOR, col("dias_uteis", "Úteis", "int"), col("dias_ausencia", "Ausência", "decimal2"), col("dias_com_visita", "Com visita", "int"), col("gap_nao_explicado", "Gap", "int")],
                          sort="gap_nao_explicado", limit=100),
                ])},
            {"id": "sazon_aus", "title": "Sazonalidade de Ausências", "page": _page(
                "Ausências e Capacidade", "ausencias", "Sazonalidade de Ausências", "aus_sazon",
                "Sazonalidade de Ausências", "Quando se concentram as ausências?",
                "Antecipar meses de menor capacidade.",
                [
                    chart("c_sazon_aus", "Ausências por mês", "serie_ausencias", "line", x="ym", series=[{"field": "dias_ausencia", "label": "Dias de ausência"}]),
                ])},
        ],
    })

    # ===================================================================
    # 7. ESPECIALIDADES E FRANQUIAS (estratégico)
    # ===================================================================
    secoes.append({
        "id": "especialidades", "title": "Especialidades e Franquias", "icon": "layers",
        "descricao": "O esforço está concentrado nas especialidades certas de cada franquia?",
        "subsections": [
            {"id": "visao", "title": "Visão Geral Especialidades × Franquias", "page": _page(
                "Especialidades e Franquias", "especialidades", "Visão Geral", "esp_visao",
                "Visão Geral Especialidades × Franquias", "O esforço do time está concentrado nas especialidades certas?",
                "Direcionar foco estratégico por franquia.",
                [
                    kpi("k_total", "Médicos c/ especialidade", "esp_matriz", agg="sum", field="no_painel"),
                    kpi("k_iaef", "IAEF (aderência)", "esp_franquias", agg="value", field="iaef_global", fmt="percent", benchmark="iaef"),
                    kpi("k_icef", "ICEF (cobertura)", "esp_franquias", agg="value", field="icef_global", fmt="percent", benchmark="icef"),
                    kpi("k_idef", "IDEF (dispersão)", "esp_franquias", agg="value", field="idef_global", fmt="percent", benchmark="idef"),
                    ranking("r_esp", "Especialidades mais visitadas", "esp_matriz", "especialidade", "visitados", extra=[col("franquia", "Franquia")]),
                    ranking("r_franq_gap", "Franquias com maior gap", "esp_franquias", "franquia", "gap"),
                    insight("i_esp", "Insight executivo", [
                        {"if": {"field": "k_iaef", "op": "<", "value": 50}, "level": "risco", "text": "Menos de 50% das visitas em especialidades relevantes."},
                    ]),
                    export_block("e_matriz", "Exportar matriz", "esp_matriz"),
                ])},
            {"id": "matriz", "title": "Matriz Especialidade × Franquia", "page": _page(
                "Especialidades e Franquias", "especialidades", "Matriz", "esp_matriz",
                "Matriz Especialidade × Franquia", "Quais combinações têm maior cobertura ou maior gap?",
                "Priorizar combinações críticas.",
                [
                    chart("c_heat", "Heatmap cobertura F2F (Especialidade × Franquia)", "esp_matriz", "heatmap", label="especialidade", value="cobertura_f2f"),
                    table("t_matriz", "Matriz detalhada", "esp_matriz",
                          [col("franquia", "Franquia"), col("especialidade", "Especialidade"), col("no_painel", "Painel", "int"), col("no_mccp", "MCCP", "int"), col("visitados", "Visitados", "int"), col("cobertura_f2f", "Cob. F2F", "percent"), col("freq_media", "Freq.", "decimal2"), col("status", "Status", "status")],
                          sort="no_painel", limit=200),
                    export_block("e_matriz2", "Exportar matriz completa", "esp_matriz"),
                ])},
            {"id": "estrategica", "title": "Cobertura Estratégica por Franquia", "page": _page(
                "Especialidades e Franquias", "especialidades", "Cobertura por Franquia", "esp_franquia",
                "Cobertura Estratégica por Franquia", "Os médicos relevantes de cada franquia estão cobertos?",
                "Priorizar franquias subcobertas.",
                [
                    table("t_franq", "Indicadores por franquia", "esp_franquias",
                          [col("franquia", "Franquia"), col("medicos_relevantes", "Relevantes", "int"), col("medicos_mccp", "MCCP", "int"), col("medicos_visitados", "Visitados", "int"), col("icef", "ICEF", "percent"), col("ifef", "IFEF", "percent"), col("gap", "Gap", "int")],
                          sort="gap", limit=100),
                    chart("c_franq", "ICEF por franquia", "esp_franquias", "bar", label="franquia", value="icef"),
                ])},
            {"id": "gaps", "title": "Gaps por Consultor / SF / GD", "page": _page(
                "Especialidades e Franquias", "especialidades", "Gaps Estratégicos", "esp_gaps",
                "Gaps por Consultor / SF / GD", "Quem tem maior oportunidade de correção estratégica?",
                "Direcionar plano de ação por responsável.",
                [
                    ranking("r_gap_cons", "Maior gap estratégico (consultor)", "esp_consultores", "consultor", "gap_estrategico", extra=[C_SF]),
                    table("t_gap", "Consultor × gap estratégico", "esp_consultores",
                          [C_CONSULTOR, C_SF, col("relevantes", "Relevantes", "int"), col("cobertos_f2f", "Cobertos", "int"), col("mccp_sem_f2f", "MCCP s/ F2F", "int"), col("gap_estrategico", "Gap", "int")],
                          sort="gap_estrategico", limit=100),
                    export_block("e_gap", "Exportar para plano de ação", "esp_consultores"),
                ])},
            {"id": "prioritarios", "title": "Médicos Prioritários sem Cobertura", "page": _page(
                "Especialidades e Franquias", "especialidades", "Médicos Prioritários", "esp_prioritarios",
                "Médicos Prioritários sem Cobertura", "Quais médicos relevantes precisam entrar no plano de ação?",
                "Ativar médicos relevantes descobertos.",
                [
                    table("t_prio", "Médicos prioritários sem cobertura", "esp_oportunidade",
                          [col("mdm", "MDM"), col("nome_medico", "Médico"), col("crm", "CRM"), col("especialidade", "Especialidade"), col("franquia", "Franquia"), C_CONSULTOR, col("ultima_visita", "Última visita")],
                          sort="visitas", dir="asc", limit=200),
                    export_block("e_prio", "Exportar médicos prioritários", "esp_oportunidade"),
                ])},
        ],
    })

    # ===================================================================
    # 8. QUALIDADE DE EXECUÇÃO
    # ===================================================================
    secoes.append({
        "id": "qualidade", "title": "Qualidade de Execução", "icon": "check",
        "descricao": "Aderência ao plano, mix de canais e qualidade cadastral.",
        "subsections": [
            {"id": "aderencia", "title": "Aderência ao Plano", "page": _page(
                "Qualidade de Execução", "qualidade", "Aderência ao Plano", "qual_aderencia",
                "Aderência ao Plano", "As visitas seguem o plano (painel/MCCP)?",
                "Aumentar aderência ao plano.",
                [
                    kpi("k_painel", "% dentro do painel", "consultores", agg="mean", field="pct_dentro_painel", fmt="percent", benchmark="pct_dentro_painel"),
                    kpi("k_mccp", "% dentro do MCCP", "consultores", agg="mean", field="pct_dentro_mccp", fmt="percent", benchmark="pct_dentro_mccp"),
                    kpi("k_plan", "% visitas planejadas", "consultores", agg="mean", field="pct_planejadas", fmt="percent"),
                    ranking("r_aderencia", "Aderência ao MCCP por consultor", "consultores", "consultor", "pct_dentro_mccp", fmt="percent", dir="asc", extra=[C_SF]),
                ])},
            {"id": "canal", "title": "Execução por Canal", "page": _page(
                "Qualidade de Execução", "qualidade", "Execução por Canal", "qual_canal",
                "Execução por Canal", "Como está o mix de canais?",
                "Equilibrar presencial e digital.",
                [
                    kpi("k_f2f", "Visitas F2F", "consultores", agg="sum", field="visitas_f2f"),
                    kpi("k_tot", "Visitas totais", "consultores", agg="sum", field="visitas"),
                    chart("c_canal", "F2F vs total por mês", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Total"}, {"field": "visitas_f2f", "label": "F2F"}]),
                ])},
            {"id": "segmentacao", "title": "Segmentação", "page": _page(
                "Qualidade de Execução", "qualidade", "Segmentação", "qual_seg",
                "Segmentação", "A cobertura respeita a segmentação?",
                "Priorizar segmentos de maior valor.",
                [
                    empty("e_seg", "Cobertura por segmento", "Requer coluna de segmento/tier do médico na base de painel."),
                ])},
            {"id": "espec_op", "title": "Especialidade Operacional", "page": _page(
                "Qualidade de Execução", "qualidade", "Especialidade Operacional", "qual_espec",
                "Especialidade Operacional", "Como se distribuem as visitas por especialidade?",
                "Atributo operacional (a análise estratégica fica na seção 7).",
                [
                    ranking("r_espec", "Visitas por especialidade", "esp_matriz", "especialidade", "visitados"),
                ])},
            {"id": "cadastro", "title": "Qualidade de Cadastro", "page": _page(
                "Qualidade de Execução", "qualidade", "Qualidade de Cadastro", "qual_cad",
                "Qualidade de Cadastro", "Há médicos sem especialidade ou duplicidades?",
                "Sanear cadastro e reduzir ruído.",
                [
                    kpi("k_sem", "Médicos sem classificação", "esp_franquias", agg="value", field="sem_classificacao", fmt="int"),
                    kpi("k_pct_sem", "% sem classificação", "esp_franquias", agg="value", field="pct_sem_classificacao", fmt="percent"),
                    export_block("e_cad", "Exportar para saneamento", "medicos"),
                ])},
        ],
    })

    # ===================================================================
    # 9. OVERLAP E CONFLITOS
    # ===================================================================
    secoes.append({
        "id": "overlap", "title": "Overlap e Conflitos", "icon": "link",
        "descricao": "Sobreposição de atuação, duplicidade e conflito.",
        "subsections": [
            {"id": "intra", "title": "Overlap Intra-Time", "page": _page(
                "Overlap e Conflitos", "overlap", "Overlap Intra-Time", "ov_intra",
                "Overlap Intra-Time", "Há médicos compartilhados dentro da mesma SF?",
                "Reduzir sobreposição interna.",
                [
                    kpi("k_compart", "Médicos compartilhados", "overlap_resumo", agg="value", field="medicos_compartilhados", fmt="int"),
                    kpi("k_pares", "Pares em overlap", "overlap_resumo", agg="value", field="pares_em_overlap", fmt="int"),
                    table("t_pares", "Pares com médicos compartilhados", "overlap_pares",
                          [col("consultor_a", "Consultor A"), col("consultor_b", "Consultor B"), col("medicos_compartilhados", "Compart.", "int"), col("mesmo_dia", "Mesmo dia", "int")],
                          sort="medicos_compartilhados", limit=100),
                ])},
            {"id": "cross", "title": "Overlap Cross-Team", "page": _page(
                "Overlap e Conflitos", "overlap", "Overlap Cross-Team", "ov_cross",
                "Overlap Cross-Team", "Há sobreposição entre SFs diferentes?",
                "Coordenar atuação entre times.",
                [
                    kpi("k_cross", "Pares cross-team", "overlap_resumo", agg="value", field="pares_cross_team", fmt="int"),
                    ranking("r_cross", "Maiores pares em overlap", "overlap_pares", "consultor_a", "medicos_compartilhados", extra=[col("consultor_b", "Consultor B")]),
                ])},
            {"id": "compartilhados", "title": "Médicos Compartilhados", "page": _page(
                "Overlap e Conflitos", "overlap", "Médicos Compartilhados", "ov_med",
                "Médicos Compartilhados", "Quantos médicos têm mais de um consultor?",
                "Definir dono único quando fizer sentido.",
                [
                    export_block("e_pares", "Exportar pares de overlap", "overlap_pares"),
                    table("t_med", "Pares detalhados", "overlap_pares",
                          [col("consultor_a", "Consultor A"), col("consultor_b", "Consultor B"), col("sf_a", "SF A"), col("sf_b", "SF B"), col("medicos_compartilhados", "Compart.", "int")],
                          sort="medicos_compartilhados", limit=100),
                ])},
            {"id": "conflitos", "title": "Conflitos de Território", "page": _page(
                "Overlap e Conflitos", "overlap", "Conflitos de Território", "ov_conf",
                "Conflitos de Território", "Há conflito de atuação no mesmo dia?",
                "Resolver conflitos operacionais.",
                [
                    ranking("r_mesmo_dia", "Pares com visitas no mesmo dia", "overlap_pares", "consultor_a", "mesmo_dia", extra=[col("consultor_b", "Consultor B")]),
                ])},
            {"id": "redistribuicao", "title": "Oportunidade de Redistribuição", "page": _page(
                "Overlap e Conflitos", "overlap", "Redistribuição", "ov_redist",
                "Oportunidade de Redistribuição", "Onde redistribuir painel reduz overlap?",
                "Planejar redistribuição de painel.",
                [
                    insight("i_ov", "Insight de sobreposição", [
                        {"if": {"field": "k_compart", "op": ">", "value": 0}, "level": "alerta", "text": "Existem médicos compartilhados — avaliar redistribuição de painel."},
                    ]),
                ])},
        ],
    })

    # ===================================================================
    # 10. MULTICANAL E ENGAJAMENTO DIGITAL (nova - 13ª no prompt vira 10ª)
    # ===================================================================
    secoes.append({
        "id": "multicanal", "title": "Multicanal e Engajamento Digital", "icon": "signal",
        "descricao": "Equilíbrio entre presencial e canais remotos/digitais.",
        "subsections": [
            {"id": "mix", "title": "Mix de Canais", "page": _page(
                "Multicanal e Engajamento Digital", "multicanal", "Mix de Canais", "mc_mix",
                "Mix de Canais", "Qual o equilíbrio entre F2F e demais canais?",
                "Calibrar estratégia multicanal.",
                [
                    kpi("k_f2f", "Visitas F2F", "consultores", agg="sum", field="visitas_f2f"),
                    kpi("k_tot", "Interações totais", "consultores", agg="sum", field="visitas"),
                    kpi("k_pct_f2f", "% F2F", "consultores", agg="ratio", num="visitas_f2f", den="visitas", fmt="percent"),
                    chart("c_mix", "F2F vs total", "serie_visitas", "line", x="ym", series=[{"field": "visitas", "label": "Total"}, {"field": "visitas_f2f", "label": "F2F"}]),
                ])},
            {"id": "alcance", "title": "Alcance Multicanal", "page": _page(
                "Multicanal e Engajamento Digital", "multicanal", "Alcance Multicanal", "mc_alcance",
                "Alcance Multicanal", "Quantos médicos são alcançados por algum canal?",
                "Ampliar alcance combinando canais.",
                [
                    kpi("k_multi", "Cobertura multicanal", "consultores", agg="ratio", num="hcp_coberto_f2f", den="hcp_alvo", fmt="percent", benchmark="pct_cobertura_multi"),
                    ranking("r_multi", "Cobertura multicanal por consultor", "consultores", "consultor", "pct_cobertura_multi", fmt="percent", extra=[C_SF]),
                ])},
            {"id": "digital", "title": "Engajamento Digital", "page": _page(
                "Multicanal e Engajamento Digital", "multicanal", "Engajamento Digital", "mc_digital",
                "Engajamento Digital", "Qual a contribuição dos canais digitais?",
                "Avaliar maturidade digital.",
                [
                    empty("e_digital", "Engajamento digital", "Requer base de interações digitais (e-mail, remoto, eventos online) com canal classificado."),
                ])},
        ],
    })

    # ===================================================================
    # 11. BENCHMARK E METAS (nova)
    # ===================================================================
    secoes.append({
        "id": "benchmark", "title": "Benchmark e Metas", "icon": "award",
        "descricao": "Comparação entre forças, gerências e contra metas.",
        "subsections": [
            {"id": "vs_sf", "title": "Benchmark entre Sales Forces", "page": _page(
                "Benchmark e Metas", "benchmark", "Benchmark SF", "bm_sf",
                "Benchmark entre Sales Forces", "Quais SFs estão acima/abaixo da média?",
                "Disseminar boas práticas entre forças.",
                [
                    chart("c_sf_cob", "Cobertura F2F por SF", "consultores", "bar", label="sales_force", value="pct_cobertura_f2f"),
                    chart("c_sf_vis", "Visitas/dia por SF", "consultores", "bar", label="sales_force", value="visitas_dia"),
                    table("t_sf", "Benchmark por SF", "consultores",
                          [C_SF, col("visitas_dia", "Vis/dia", "decimal2"), col("pct_cobertura_f2f", "Cob. F2F", "percent"), col("pct_dentro_mccp", "MCCP", "percent"), col("pct_ausencia", "Ausência", "percent")],
                          sort="pct_cobertura_f2f", limit=50),
                ])},
            {"id": "vs_gd", "title": "Benchmark entre GDs", "page": _page(
                "Benchmark e Metas", "benchmark", "Benchmark GD", "bm_gd",
                "Benchmark entre GDs", "Quais GDs lideram nos indicadores?",
                "Reconhecer e nivelar gerências.",
                [
                    chart("c_gd_cob", "Cobertura F2F por GD", "consultores", "bar", label="gd", value="pct_cobertura_f2f"),
                    table("t_gd", "Benchmark por GD", "consultores",
                          [C_GD, col("visitas_dia", "Vis/dia", "decimal2"), col("pct_cobertura_f2f", "Cob. F2F", "percent"), col("score_territorio", "Score Ter.", "decimal2")],
                          sort="pct_cobertura_f2f", limit=50),
                ])},
            {"id": "metas", "title": "Metas vs Realizado", "page": _page(
                "Benchmark e Metas", "benchmark", "Metas vs Realizado", "bm_metas",
                "Metas vs Realizado", "O painel realizado está próximo da meta?",
                "Acompanhar atingimento de metas de painel.",
                [
                    table("t_meta", "Painel realizado vs meta", "consultores",
                          [C_CONSULTOR, col("painel_meta", "Meta", "int"), col("painel", "Realizado", "int")],
                          sort="painel", limit=100),
                ])},
        ],
    })

    # ===================================================================
    # 12. SIMULADOR E PLANEJAMENTO
    # ===================================================================
    secoes.append({
        "id": "simulador", "title": "Simulador e Planejamento", "icon": "sliders",
        "descricao": "Transformar diagnóstico em cenário futuro.",
        "subsections": [
            {"id": "capacidade", "title": "Simulador de Capacidade", "page": _page(
                "Simulador e Planejamento", "simulador", "Simulador de Capacidade", "sim_cap",
                "Simulador de Capacidade", "Quantos médicos é possível cobrir com a capacidade atual?",
                "Planejar metas factíveis de cobertura.",
                [
                    {"type": "simulator", "id": "sim_capacidade", "title": "Simulador de capacidade",
                     "inputs": [
                         {"id": "dias_uteis", "label": "Dias úteis no período", "default": 252},
                         {"id": "pct_ausencia", "label": "% ausência esperada", "default": 10},
                         {"id": "visitas_dia", "label": "Visitas/dia alvo", "default": 7},
                         {"id": "freq_alvo", "label": "Frequência alvo/médico", "default": 4},
                     ],
                     "outputs": [
                         {"id": "dias_disponiveis", "label": "Dias disponíveis", "formula": "dias_uteis*(1-pct_ausencia/100)"},
                         {"id": "visitas_possiveis", "label": "Visitas possíveis", "formula": "dias_uteis*(1-pct_ausencia/100)*visitas_dia"},
                         {"id": "cobertura_possivel", "label": "Médicos cobríveis", "formula": "dias_uteis*(1-pct_ausencia/100)*visitas_dia/freq_alvo"},
                     ]},
                ])},
            {"id": "perfil", "title": "Simulador por Perfil Territorial", "page": _page(
                "Simulador e Planejamento", "simulador", "Simulador por Perfil", "sim_perfil",
                "Simulador por Perfil Territorial", "Como o perfil territorial afeta a capacidade?",
                "Ajustar metas por tipo de setor.",
                [
                    {"type": "simulator", "id": "sim_perfil", "title": "Capacidade por perfil",
                     "inputs": [
                         {"id": "dias_uteis", "label": "Dias úteis", "default": 252},
                         {"id": "fator_deslocamento", "label": "Fator de deslocamento (%)", "default": 15},
                         {"id": "visitas_dia", "label": "Visitas/dia base", "default": 7},
                     ],
                     "outputs": [
                         {"id": "visitas_dia_ajustada", "label": "Vis/dia ajustada", "formula": "visitas_dia*(1-fator_deslocamento/100)"},
                         {"id": "visitas_possiveis", "label": "Visitas possíveis", "formula": "dias_uteis*visitas_dia*(1-fator_deslocamento/100)"},
                     ]},
                ])},
            {"id": "plano_cob", "title": "Planejamento de Cobertura", "page": _page(
                "Simulador e Planejamento", "simulador", "Planejamento de Cobertura", "sim_plano",
                "Planejamento de Cobertura", "Qual a meta de cobertura por consultor?",
                "Definir metas individuais.",
                [
                    table("t_plano", "Base para planejamento", "consultores",
                          [C_CONSULTOR, col("painel", "Painel", "int"), col("hcp_coberto_f2f", "Cobertos", "int"), col("hcp_nao_coberto", "Gap", "int"), col("capacidade_disponivel", "Capacidade", "int")],
                          sort="hcp_nao_coberto", limit=100),
                ])},
            {"id": "redistribuicao", "title": "Redistribuição de Painel", "page": _page(
                "Simulador e Planejamento", "simulador", "Redistribuição de Painel", "sim_redist",
                "Redistribuição de Painel", "Onde o painel está sobrecarregado?",
                "Reequilibrar carga entre consultores.",
                [
                    ranking("r_sobrecarga", "Maiores painéis", "consultores", "consultor", "painel", extra=[C_SF, col("pct_cobertura_f2f", "Cob. F2F", "percent")]),
                ])},
            {"id": "cenarios", "title": "Cenários Executivos", "page": _page(
                "Simulador e Planejamento", "simulador", "Cenários Executivos", "sim_cenarios",
                "Cenários Executivos", "Qual o impacto de mudar metas?",
                "Apoiar decisões de liderança.",
                [
                    {"type": "simulator", "id": "sim_cenario", "title": "Cenário de cobertura",
                     "inputs": [
                         {"id": "painel_total", "label": "Painel total", "default": 1000},
                         {"id": "meta_cobertura", "label": "Meta de cobertura (%)", "default": 80},
                         {"id": "freq_alvo", "label": "Frequência alvo", "default": 4},
                     ],
                     "outputs": [
                         {"id": "medicos_meta", "label": "Médicos a cobrir", "formula": "painel_total*meta_cobertura/100"},
                         {"id": "visitas_necessarias", "label": "Visitas necessárias", "formula": "painel_total*meta_cobertura/100*freq_alvo"},
                     ]},
                ])},
        ],
    })

    # ===================================================================
    # 13. OPORTUNIDADES E PLANO DE AÇÃO
    # ===================================================================
    secoes.append({
        "id": "oportunidades", "title": "Oportunidades e Plano de Ação", "icon": "flag",
        "descricao": "Transformar diagnóstico em ação priorizada.",
        "subsections": [
            {"id": "prioritarias", "title": "Oportunidades Prioritárias", "page": _page(
                "Oportunidades e Plano de Ação", "oportunidades", "Oportunidades Prioritárias", "op_prio",
                "Oportunidades Prioritárias", "Onde o time deve agir primeiro?",
                "Sequenciar ações por impacto.",
                [
                    ranking("r_prio", "Consultores por prioridade", "consultores", "consultor", "score_prioridade", fmt="decimal2", extra=[C_SF, col("pct_cobertura_f2f", "Cob. F2F", "percent"), col("gap_estrategico", "Gap estr.", "int")]),
                    export_block("e_prio", "Exportar oportunidades", "consultores"),
                ])},
            {"id": "plano_consultor", "title": "Plano de Ação por Consultor", "page": _page(
                "Oportunidades e Plano de Ação", "oportunidades", "Plano por Consultor", "op_consultor",
                "Plano de Ação por Consultor", "Qual a ação recomendada por consultor?",
                "Atribuir ações individuais.",
                [
                    table("t_plano", "Plano por consultor", "consultores",
                          [C_CONSULTOR, C_SF, col("hcp_nao_coberto", "Médicos descobertos", "int"), col("gap_estrategico", "Gap estratégico", "int"), col("pct_ausencia", "Ausência", "percent"), col("score_prioridade", "Prioridade", "decimal2")],
                          sort="score_prioridade", limit=100),
                ])},
            {"id": "plano_sf", "title": "Plano de Ação por SF / GD", "page": _page(
                "Oportunidades e Plano de Ação", "oportunidades", "Plano por SF/GD", "op_sf",
                "Plano de Ação por SF / GD", "Onde concentrar esforço por força/gerência?",
                "Priorizar por força de vendas.",
                [
                    chart("c_sf_prio", "Prioridade média por SF", "consultores", "bar", label="sales_force", value="score_prioridade"),
                ])},
            {"id": "ativacao", "title": "Médicos Prioritários para Ativação", "page": _page(
                "Oportunidades e Plano de Ação", "oportunidades", "Médicos para Ativação", "op_ativacao",
                "Médicos Prioritários para Ativação", "Quais médicos ativar primeiro?",
                "Lista acionável de médicos.",
                [
                    table("t_ativ", "Médicos relevantes sem cobertura", "esp_oportunidade",
                          [col("nome_medico", "Médico"), col("especialidade", "Especialidade"), col("franquia", "Franquia"), C_CONSULTOR, col("ultima_visita", "Última visita")],
                          sort="visitas", dir="asc", limit=200),
                    export_block("e_ativ", "Exportar lista de ativação", "esp_oportunidade"),
                ])},
            {"id": "backlog", "title": "Backlog de Correções Operacionais", "page": _page(
                "Oportunidades e Plano de Ação", "oportunidades", "Backlog Operacional", "op_backlog",
                "Backlog de Correções Operacionais", "Quais correções operacionais estão pendentes?",
                "Organizar saneamento operacional.",
                [
                    table("t_backlog", "Consultores com gap não explicado", "consultores",
                          [C_CONSULTOR, col("gap_nao_explicado", "Gap não explicado", "int"), col("pct_dentro_painel", "Dentro painel", "percent")],
                          sort="gap_nao_explicado", limit=100),
                ])},
        ],
    })

    # ===================================================================
    # 14. SAÚDE DOS DADOS (nova)
    # ===================================================================
    secoes.append({
        "id": "saude_dados", "title": "Saúde dos Dados", "icon": "database",
        "descricao": "Completude, consistência e anomalias das bases.",
        "subsections": [
            {"id": "completude", "title": "Completude", "page": _page(
                "Saúde dos Dados", "saude_dados", "Completude", "sd_completude",
                "Completude", "As bases estão completas e consistentes?",
                "Confiar nos números antes de decidir.",
                [
                    kpi("k_vis", "Visitas válidas", "audit_kv", agg="value", field="visitas_validas", fmt="int"),
                    kpi("k_dedup", "Removidas na dedup", "audit_kv", agg="value", field="removidas_dedup", fmt="int"),
                    kpi("k_semdata", "Visitas sem data", "audit_kv", agg="value", field="sem_data", fmt="int"),
                    kpi("k_semesp", "Médicos sem especialidade", "audit_kv", agg="value", field="medicos_sem_classificacao", fmt="int"),
                ])},
            {"id": "anomalias", "title": "Anomalias", "page": _page(
                "Saúde dos Dados", "saude_dados", "Anomalias", "sd_anomalias",
                "Anomalias", "Há valores fora do esperado?",
                "Detectar erros de base.",
                [
                    ranking("r_anom", "Visitas/dia improváveis (>20)", "consultores", "consultor", "visitas_dia", fmt="decimal2", extra=[C_SF]),
                ])},
            {"id": "cobertura_dados", "title": "Cobertura de Cadastro", "page": _page(
                "Saúde dos Dados", "saude_dados", "Cobertura de Cadastro", "sd_cad",
                "Cobertura de Cadastro", "Quantos médicos têm cadastro completo?",
                "Priorizar saneamento cadastral.",
                [
                    kpi("k_pct_sem", "% sem classificação", "esp_franquias", agg="value", field="pct_sem_classificacao", fmt="percent"),
                    export_block("e_san", "Exportar base de médicos", "medicos"),
                ])},
        ],
    })

    # ===================================================================
    # 15. GOVERNANÇA E AUDITORIA
    # ===================================================================
    secoes.append({
        "id": "governanca", "title": "Governança e Auditoria", "icon": "shield",
        "descricao": "Confiança nos dados, regras, exclusões e metodologia.",
        "subsections": [
            {"id": "fontes", "title": "Fontes de Dados", "page": _page(
                "Governança e Auditoria", "governanca", "Fontes de Dados", "gov_fontes",
                "Fontes de Dados", "Quais bases foram carregadas?",
                "Rastrear a origem dos números.",
                [
                    {"type": "audit", "id": "a_fontes", "title": "Arquivos carregados", "path": "meta.fontes"},
                ])},
            {"id": "exclusoes", "title": "Regras de Exclusão", "page": _page(
                "Governança e Auditoria", "governanca", "Regras de Exclusão", "gov_exclusoes",
                "Regras de Exclusão", "O que foi excluído do diagnóstico?",
                "Tornar exclusões explícitas.",
                [
                    methodology("m_excl", "Regras de exclusão aplicadas", [
                        "Sales Forces excluídas: configuráveis em config.SALES_FORCES_EXCLUIDAS.",
                        "Consultores afastados: marcados como inativos via coluna 'ativo' da estrutura.",
                        "Visitas sem consultor são descartadas.",
                    ]),
                ])},
            {"id": "dedup", "title": "Deduplicação", "page": _page(
                "Governança e Auditoria", "governanca", "Deduplicação", "gov_dedup",
                "Deduplicação", "Como as duplicidades foram tratadas?",
                "Garantir contagem correta.",
                [
                    {"type": "audit", "id": "a_dedup", "title": "Deduplicação", "path": "meta.auditoria"},
                    methodology("m_dedup", "Critério de deduplicação", [
                        "Visita única por (consultor, médico, data, canal).",
                        "Ausência única por (consultor, início, fim, tipo).",
                    ]),
                ])},
            {"id": "metodologia", "title": "Metodologia dos Indicadores", "page": _page(
                "Governança e Auditoria", "governanca", "Metodologia", "gov_metodologia",
                "Metodologia dos Indicadores", "Como cada indicador é calculado?",
                "Padronizar a leitura dos KPIs.",
                [
                    methodology("m_kpi", "Fórmulas dos principais indicadores", [
                        "Cobertura F2F = médicos do painel com ≥1 visita presencial / painel.",
                        "Cobertura MCCP = médicos MCCP com ≥1 visita F2F / médicos MCCP.",
                        "Visitas/dia = visitas / dias com visita.",
                        "% ausência = dias de ausência / dias úteis do período.",
                        "IAEF = % de visitas em especialidades relevantes.",
                        "ICEF = % de médicos relevantes cobertos F2F.",
                        "IFEF = frequência média normalizada pela frequência esperada.",
                        "IDEF = dispersão do esforço entre especialidades.",
                    ]),
                ])},
            {"id": "qualidade", "title": "Qualidade e Completude", "page": _page(
                "Governança e Auditoria", "governanca", "Qualidade e Completude", "gov_qualidade",
                "Qualidade e Completude", "Qual o nível de completude das bases?",
                "Avaliar confiança geral.",
                [
                    {"type": "audit", "id": "a_qual", "title": "Resumo de qualidade", "path": "meta.auditoria"},
                    export_block("e_audit", "Exportar auditoria (consultores)", "consultores"),
                ])},
        ],
    })

    return secoes
