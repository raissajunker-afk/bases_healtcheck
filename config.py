from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os


DEFAULT_WINDOWS_BASES_DIR = (
    r"C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
)

DEFAULT_BLOCKS = [
    "kpi_principal",
    "kpi_secundario",
    "chart_tendencia",
    "chart_distribuicao",
    "ranking_principal",
    "tabela_detalhada",
    "insight_automatico",
    "export_metodologia",
]


@dataclass(frozen=True)
class SubsectionBlueprint:
    id: str
    title: str
    business_question: str
    decision_supported: str
    blocks: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKS))


@dataclass(frozen=True)
class SectionBlueprint:
    id: str
    title: str
    description: str
    subsections: list[SubsectionBlueprint]


SECTION_BLUEPRINTS: list[SectionBlueprint] = [
    SectionBlueprint(
        id="executive_overview",
        title="1. Executive Overview",
        description="Leitura executiva rapida com principais sinais do negocio.",
        subsections=[
            SubsectionBlueprint(
                id="snapshot_executivo",
                title="Snapshot Executivo",
                business_question="Quais os principais sinais do negocio no periodo?",
                decision_supported="Priorizar temas criticos de lideranca para acao imediata.",
            ),
            SubsectionBlueprint(
                id="alertas_prioritarios",
                title="Alertas Prioritarios",
                business_question="Onde estao os maiores riscos operacionais e comerciais?",
                decision_supported="Direcionar acao rapida em riscos de cobertura e produtividade.",
            ),
            SubsectionBlueprint(
                id="evolucao_geral",
                title="Evolucao Geral",
                business_question="A performance geral esta melhorando ou piorando?",
                decision_supported="Calibrar prioridades taticas por tendencia.",
            ),
            SubsectionBlueprint(
                id="resumo_sales_force",
                title="Resumo por Sales Force",
                business_question="Quais sales forces estao acima ou abaixo do esperado?",
                decision_supported="Ajustar suporte por forca de vendas.",
            ),
            SubsectionBlueprint(
                id="resumo_gd",
                title="Resumo por GD",
                business_question="Quais GDs concentram oportunidades e riscos?",
                decision_supported="Apoiar gestao distrital com foco em acao.",
            ),
        ],
    ),
    SectionBlueprint(
        id="performance_comercial",
        title="2. Performance Comercial",
        description="Produtividade e execucao do time por diferentes cortes.",
        subsections=[
            SubsectionBlueprint(
                id="produtividade_geral",
                title="Produtividade Geral",
                business_question="Qual o volume e o ritmo de execucao comercial?",
                decision_supported="Definir metas operacionais realistas por capacidade.",
            ),
            SubsectionBlueprint(
                id="performance_consultor",
                title="Performance por Consultor",
                business_question="Quais consultores entregam acima ou abaixo da media?",
                decision_supported="Planejar coaching e acompanhamento individual.",
            ),
            SubsectionBlueprint(
                id="ranking_alta",
                title="Ranking de Alta Performance",
                business_question="Quem representa melhores praticas no periodo?",
                decision_supported="Replicar comportamento de alta performance.",
            ),
            SubsectionBlueprint(
                id="ranking_baixa",
                title="Ranking de Baixa Performance",
                business_question="Onde estao os maiores gaps de execucao?",
                decision_supported="Atuar com plano de recuperacao direcionado.",
            ),
            SubsectionBlueprint(
                id="comparativo_mat_recente",
                title="Comparativo MAT vs Recente",
                business_question="A performance recente confirma a tendencia de longo prazo?",
                decision_supported="Antecipar deterioracao ou consolidacao de resultados.",
            ),
        ],
    ),
    SectionBlueprint(
        id="cobertura_painel",
        title="3. Cobertura e Painel",
        description="Avaliacao da cobertura dos HCPs certos no plano.",
        subsections=[
            SubsectionBlueprint(
                id="cobertura_mccp",
                title="Cobertura MCCP",
                business_question="Estamos cobrindo os HCPs alvo MCCP?",
                decision_supported="Identificar consultores e areas com maior gap de cobertura.",
            ),
            SubsectionBlueprint(
                id="cobertura_f2f",
                title="Cobertura F2F",
                business_question="A cobertura face-to-face esta adequada?",
                decision_supported="Ajustar cadencia de visitas presenciais.",
            ),
            SubsectionBlueprint(
                id="fora_painel",
                title="Fora de Painel",
                business_question="Quanto esforco esta indo para medicos fora do plano?",
                decision_supported="Reduzir dispersao e melhorar aderencia ao painel.",
            ),
            SubsectionBlueprint(
                id="turnover_painel",
                title="Turnover de Painel",
                business_question="Como mudou a composicao do painel no periodo?",
                decision_supported="Reavaliar estabilidade e continuidade de cobertura.",
            ),
            SubsectionBlueprint(
                id="medicos_parados",
                title="Medicos Parados",
                business_question="Quais medicos em painel ficaram sem visita recente?",
                decision_supported="Priorizar ativacao de medicos sem cobertura.",
            ),
        ],
    ),
    SectionBlueprint(
        id="visitacao_frequencia",
        title="4. Visitacao e Frequencia",
        description="Cadencia, consistencia e distribuicao de visitas.",
        subsections=[
            SubsectionBlueprint(
                id="frequencia_real",
                title="Frequencia Real",
                business_question="Qual a frequencia real de contato por medico?",
                decision_supported="Ajustar planos de contato para grupos prioritarios.",
            ),
            SubsectionBlueprint(
                id="consistencia_mensal",
                title="Consistencia Mensal",
                business_question="A execucao se manteve consistente mes a mes?",
                decision_supported="Mitigar sazonalidades e rupturas de ritmo.",
            ),
            SubsectionBlueprint(
                id="visitas_por_dia",
                title="Visitas por Dia",
                business_question="Quantas visitas por dia estao sendo executadas?",
                decision_supported="Rebalancear metas de produtividade diaria.",
            ),
            SubsectionBlueprint(
                id="sazonalidade",
                title="Sazonalidade",
                business_question="Existe padrao sazonal relevante no historico?",
                decision_supported="Antecipar quedas e reforcar periodos criticos.",
            ),
            SubsectionBlueprint(
                id="medico_vs_frequencia",
                title="Medico x Frequencia",
                business_question="Quais medicos recebem frequencia abaixo do esperado?",
                decision_supported="Priorizar carteira de alto potencial subatendida.",
            ),
        ],
    ),
    SectionBlueprint(
        id="eficiencia_territorial",
        title="5. Eficiencia Territorial",
        description="Leitura de desenho e execucao territorial.",
        subsections=[
            SubsectionBlueprint(
                id="perfil_setor",
                title="Perfil de Setor",
                business_question="Qual o perfil operacional dos setores?",
                decision_supported="Ajustar distribuicao de carga territorial.",
            ),
            SubsectionBlueprint(
                id="deslocamento",
                title="Deslocamento",
                business_question="A malha de deslocamento esta eficiente?",
                decision_supported="Reduzir perda de capacidade por deslocamento.",
            ),
            SubsectionBlueprint(
                id="brickagem",
                title="Brickagem",
                business_question="Os bricks estao cobertos de forma equilibrada?",
                decision_supported="Corrigir vazios e sobrecargas territoriais.",
            ),
            SubsectionBlueprint(
                id="cobertura_geografica",
                title="Cobertura Geografica",
                business_question="Qual a amplitude geografica real de execucao?",
                decision_supported="Priorizar cobertura em geografias criticas.",
            ),
            SubsectionBlueprint(
                id="score_territorio",
                title="Score de Territorio",
                business_question="Quais territorios apresentam melhor equilibrio operacional?",
                decision_supported="Direcionar revisoes de desenho territorial.",
            ),
        ],
    ),
    SectionBlueprint(
        id="ausencias_capacidade",
        title="6. Ausencias e Capacidade",
        description="Perda de capacidade por ausencia e dias nao explicados.",
        subsections=[
            SubsectionBlueprint(
                id="ausencia_total",
                title="Ausencia Total",
                business_question="Qual o impacto total de ausencia no periodo?",
                decision_supported="Planejar cobertura de capacidade indisponivel.",
            ),
            SubsectionBlueprint(
                id="ausencia_produtiva",
                title="Ausencia Produtiva",
                business_question="Quanto da ausencia e ligada a atividades produtivas?",
                decision_supported="Separar ausencia operacional de atividade de negocio.",
            ),
            SubsectionBlueprint(
                id="ausencia_pessoal",
                title="Ausencia Pessoal",
                business_question="Qual a contribuicao de ausencias pessoais?",
                decision_supported="Ajustar previsao de capacidade por equipe.",
            ),
            SubsectionBlueprint(
                id="capacidade_disponivel",
                title="Capacidade Disponivel",
                business_question="Qual a capacidade real disponivel para visitas?",
                decision_supported="Revisar metas conforme capacidade efetiva.",
            ),
            SubsectionBlueprint(
                id="sazonalidade_ausencias",
                title="Sazonalidade de Ausencias",
                business_question="A ausencia segue padrao temporal previsivel?",
                decision_supported="Antecipar planejamento em meses mais criticos.",
            ),
        ],
    ),
    SectionBlueprint(
        id="especialidades_franquias",
        title="7. Especialidades e Franquias",
        description="Camada estrategica para aderencia especialidade-franquia.",
        subsections=[
            SubsectionBlueprint(
                id="visao_geral",
                title="Visao Geral Especialidades x Franquias",
                business_question="O esforco esta concentrado nas especialidades certas?",
                decision_supported="Corrigir foco de execucao por estrategia de franquia.",
            ),
            SubsectionBlueprint(
                id="matriz_especialidade_franquia",
                title="Matriz Especialidade x Franquia",
                business_question="Quais combinacoes concentram cobertura e gap?",
                decision_supported="Priorizar combinacoes com maior criticidade.",
            ),
            SubsectionBlueprint(
                id="cobertura_estrategica_franquia",
                title="Cobertura Estrategica por Franquia",
                business_question="As franquias cobrem medicos relevantes?",
                decision_supported="Definir reforco por franquia e especialidade.",
            ),
            SubsectionBlueprint(
                id="gaps_consultor_sf_gd",
                title="Gaps por Consultor / SF / GD",
                business_question="Quem tem maior gap estrategico por especialidade?",
                decision_supported="Direcionar plano de acao tatico por camada.",
            ),
            SubsectionBlueprint(
                id="medicos_prioritarios_sem_cobertura",
                title="Medicos Prioritarios sem Cobertura",
                business_question="Quais medicos relevantes precisam de ativacao imediata?",
                decision_supported="Montar backlog de alta prioridade orientado por impacto.",
            ),
        ],
    ),
    SectionBlueprint(
        id="qualidade_execucao",
        title="8. Qualidade de Execucao",
        description="Aderencia ao plano, mix de canais e qualidade cadastral.",
        subsections=[
            SubsectionBlueprint(
                id="aderencia_plano",
                title="Aderencia ao Plano",
                business_question="As visitas seguem o planejamento esperado?",
                decision_supported="Corrigir desalinhamentos de execucao contra o plano.",
            ),
            SubsectionBlueprint(
                id="execucao_canal",
                title="Execucao por Canal",
                business_question="O mix de canais esta adequado ao objetivo?",
                decision_supported="Ajustar estrategia omnicanal de contato.",
            ),
            SubsectionBlueprint(
                id="segmentacao",
                title="Segmentacao",
                business_question="A segmentacao esta refletida na execucao?",
                decision_supported="Direcionar esforco por segmento de maior retorno.",
            ),
            SubsectionBlueprint(
                id="especialidade_operacional",
                title="Especialidade Operacional",
                business_question="Especialidades operacionais estao bem cobertas?",
                decision_supported="Ajustar foco operacional sem perder estrategia.",
            ),
            SubsectionBlueprint(
                id="qualidade_cadastro",
                title="Qualidade de Cadastro",
                business_question="Existem lacunas cadastrais que afetam analise?",
                decision_supported="Priorizar saneamento de dados essenciais.",
            ),
        ],
    ),
    SectionBlueprint(
        id="overlap_conflitos",
        title="9. Overlap e Conflitos",
        description="Sobreposicao de atuacao entre consultores, SFs e territorios.",
        subsections=[
            SubsectionBlueprint(
                id="overlap_intra_time",
                title="Overlap Intra-Time",
                business_question="Ha compartilhamento excessivo dentro do mesmo time?",
                decision_supported="Reduzir redundancia e ganho marginal baixo.",
            ),
            SubsectionBlueprint(
                id="overlap_cross_team",
                title="Overlap Cross-Team",
                business_question="Existe sobreposicao entre times distintos?",
                decision_supported="Clarificar ownership entre times e franquias.",
            ),
            SubsectionBlueprint(
                id="medicos_compartilhados",
                title="Medicos Compartilhados",
                business_question="Quais medicos recebem visitas de varios consultores?",
                decision_supported="Definir estrategia de contato coordenada.",
            ),
            SubsectionBlueprint(
                id="conflitos_territorio",
                title="Conflitos de Territorio",
                business_question="Quais territorios mostram conflito de atuacao?",
                decision_supported="Ajustar desenho territorial e regras de posse.",
            ),
            SubsectionBlueprint(
                id="redistribuicao_oportunidade",
                title="Oportunidade de Redistribuicao",
                business_question="Onde redistribuir para maior eficiencia?",
                decision_supported="Executar rebalanceamento de carteira e territorio.",
            ),
        ],
    ),
    SectionBlueprint(
        id="simulador_planejamento",
        title="10. Simulador e Planejamento",
        description="Transforma diagnostico em cenarios futuros.",
        subsections=[
            SubsectionBlueprint(
                id="simulador_capacidade",
                title="Simulador de Capacidade",
                business_question="Com a capacidade atual, qual cobertura e viavel?",
                decision_supported="Projetar metas factiveis por periodo.",
            ),
            SubsectionBlueprint(
                id="simulador_perfil_territorial",
                title="Simulador por Perfil Territorial",
                business_question="Como o perfil territorial altera capacidade de execucao?",
                decision_supported="Definir alocacao por perfil de setor.",
            ),
            SubsectionBlueprint(
                id="planejamento_cobertura",
                title="Planejamento de Cobertura",
                business_question="Qual plano de cobertura maximiza resultado?",
                decision_supported="Escolher estrategia de cobertura de maior impacto.",
            ),
            SubsectionBlueprint(
                id="redistribuicao_painel",
                title="Redistribuicao de Painel",
                business_question="Como redistribuir painel para reduzir gargalos?",
                decision_supported="Equilibrar carteira para ganho de performance.",
            ),
            SubsectionBlueprint(
                id="cenarios_executivos",
                title="Cenarios Executivos",
                business_question="Quais cenarios executivos sao mais provaveis?",
                decision_supported="Apoiar decisao de lideranca com cenarios comparados.",
            ),
        ],
    ),
    SectionBlueprint(
        id="oportunidades_plano_acao",
        title="11. Oportunidades e Plano de Acao",
        description="Consolidacao de gaps em backlog priorizado de acao.",
        subsections=[
            SubsectionBlueprint(
                id="oportunidades_prioritarias",
                title="Oportunidades Prioritarias",
                business_question="Onde agir primeiro para maior retorno?",
                decision_supported="Criar fila de prioridades unica e objetiva.",
            ),
            SubsectionBlueprint(
                id="plano_acao_consultor",
                title="Plano de Acao por Consultor",
                business_question="Que plano individual e recomendado por consultor?",
                decision_supported="Guiar acompanhamento tatico individual.",
            ),
            SubsectionBlueprint(
                id="plano_acao_sf_gd",
                title="Plano de Acao por SF / GD",
                business_question="Quais temas priorizar por camada de gestao?",
                decision_supported="Apoiar governanca por SF e GD.",
            ),
            SubsectionBlueprint(
                id="medicos_prioritarios_ativacao",
                title="Medicos Prioritarios para Ativacao",
                business_question="Quais medicos devem entrar imediatamente no plano?",
                decision_supported="Acionar cobertura em medicos de maior relevancia.",
            ),
            SubsectionBlueprint(
                id="backlog_correcoes_operacionais",
                title="Backlog de Correcoes Operacionais",
                business_question="Quais correcoes de base e processo sao mais urgentes?",
                decision_supported="Reduzir friccao operacional com backlog estruturado.",
            ),
        ],
    ),
    SectionBlueprint(
        id="governanca_auditoria",
        title="12. Governanca e Auditoria",
        description="Confianca metodologica, regras e rastreabilidade.",
        subsections=[
            SubsectionBlueprint(
                id="fontes_dados",
                title="Fontes de Dados",
                business_question="Quais arquivos e periodos alimentaram a visao atual?",
                decision_supported="Garantir transparencia de origem dos dados.",
            ),
            SubsectionBlueprint(
                id="regras_exclusao",
                title="Regras de Exclusao",
                business_question="Quais regras removeram registros do escopo?",
                decision_supported="Evitar leituras equivocadas de cobertura e volume.",
            ),
            SubsectionBlueprint(
                id="deduplicacao",
                title="Deduplicacao",
                business_question="Qual o impacto da deduplicacao nos resultados?",
                decision_supported="Validar estabilidade de indicadores apos limpeza.",
            ),
            SubsectionBlueprint(
                id="metodologia_indicadores",
                title="Metodologia dos Indicadores",
                business_question="Como cada indicador foi calculado?",
                decision_supported="Assegurar consistencia interpretativa e auditoria.",
            ),
            SubsectionBlueprint(
                id="qualidade_completude",
                title="Qualidade e Completude",
                business_question="Quais lacunas ainda afetam qualidade analitica?",
                decision_supported="Direcionar saneamento de dados e processos.",
            ),
        ],
    ),
    SectionBlueprint(
        id="inteligencia_mercado",
        title="13. Inteligencia de Mercado",
        description="Contextualiza execucao com sinais de mercado e competencia.",
        subsections=[
            SubsectionBlueprint(
                id="sinais_mercado",
                title="Sinais de Mercado",
                business_question="Que sinais externos impactam a estrategia comercial?",
                decision_supported="Ajustar foco de execucao por contexto de mercado.",
            ),
            SubsectionBlueprint(
                id="benchmark_regional",
                title="Benchmark Regional",
                business_question="Quais regioes performam acima da referencia interna?",
                decision_supported="Replicar praticas de regioes de melhor resultado.",
            ),
            SubsectionBlueprint(
                id="tendencias_demanda",
                title="Tendencias de Demanda",
                business_question="Existe mudanca de demanda por especialidade?",
                decision_supported="Reorientar cobertura para tendencia emergente.",
            ),
            SubsectionBlueprint(
                id="sinais_concorrencia",
                title="Sinais de Concorrencia",
                business_question="Onde a pressao competitiva parece maior?",
                decision_supported="Definir respostas comerciais por territorio.",
            ),
            SubsectionBlueprint(
                id="oportunidades_regionais",
                title="Oportunidades Regionais",
                business_question="Quais regioes concentram maior oportunidade?",
                decision_supported="Priorizar alocacao de capacidade por potencial.",
            ),
        ],
    ),
    SectionBlueprint(
        id="experiencia_omnicanal",
        title="14. Experiencia Omnicanal",
        description="Equilibrio e consistencia da jornada de contato com HCP.",
        subsections=[
            SubsectionBlueprint(
                id="mix_canais",
                title="Mix de Canais",
                business_question="O mix de canais esta aderente ao publico alvo?",
                decision_supported="Rebalancear estrategia de contato por canal.",
            ),
            SubsectionBlueprint(
                id="sequencia_contato",
                title="Sequencia de Contato",
                business_question="A sequencia de contatos favorece continuidade?",
                decision_supported="Melhorar cadencia e conversao da jornada.",
            ),
            SubsectionBlueprint(
                id="resposta_hcp",
                title="Resposta do HCP",
                business_question="Quais padroes sugerem melhor resposta do HCP?",
                decision_supported="Priorizar combinacoes de canal mais efetivas.",
            ),
            SubsectionBlueprint(
                id="consistencia_omni",
                title="Consistencia Omnichannel",
                business_question="A experiencia de contato e consistente ao longo do tempo?",
                decision_supported="Corrigir quebras na jornada de relacionamento.",
            ),
            SubsectionBlueprint(
                id="oportunidades_canal",
                title="Oportunidades por Canal",
                business_question="Quais canais mostram maior oportunidade incremental?",
                decision_supported="Aumentar retorno do mix de canais com foco.",
            ),
        ],
    ),
    SectionBlueprint(
        id="sustentacao_operacional",
        title="15. Sustentacao Operacional",
        description="Estabilidade de dados, processos e execucao continua.",
        subsections=[
            SubsectionBlueprint(
                id="saude_pipeline",
                title="Saude da Pipeline",
                business_question="O pipeline de dados esta estavel e rastreavel?",
                decision_supported="Garantir confiabilidade de atualizacoes periodicas.",
            ),
            SubsectionBlueprint(
                id="qualidade_entrada",
                title="Qualidade de Entrada",
                business_question="As bases de origem chegam com qualidade esperada?",
                decision_supported="Atuar preventivamente em falhas de origem.",
            ),
            SubsectionBlueprint(
                id="monitoramento_regras",
                title="Monitoramento de Regras",
                business_question="As regras operacionais continuam coerentes no tempo?",
                decision_supported="Evitar regressao metodologica silenciosa.",
            ),
            SubsectionBlueprint(
                id="observabilidade_execucao",
                title="Observabilidade de Execucao",
                business_question="Quais etapas da execucao exigem reforco de monitoramento?",
                decision_supported="Melhorar suporte operacional e tempo de resposta.",
            ),
            SubsectionBlueprint(
                id="backlog_tecnico",
                title="Backlog Tecnico",
                business_question="Quais melhorias tecnicas sustentam escala futura?",
                decision_supported="Priorizar evolucao de arquitetura com menor risco.",
            ),
        ],
    ),
]


def build_page_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for section in SECTION_BLUEPRINTS:
        for subsection in section.subsections:
            page_id = f"{section.id}__{subsection.id}"
            registry[page_id] = {
                "section": section.title,
                "sectionId": section.id,
                "subsection": subsection.title,
                "pageId": page_id,
                "title": subsection.title,
                "businessQuestion": subsection.business_question,
                "decisionSupported": subsection.decision_supported,
                "dataPath": f"sections.{section.id}.pages.{subsection.id}",
                "blocks": subsection.blocks,
            }
    return registry


@dataclass
class AppConfig:
    project_root: Path
    bases_dir: Path
    output_dir: Path
    payload_path: Path
    html_output_path: Path
    audit_dir: Path


def resolve_bases_dir(project_root: Path, override: str | None = None) -> Path:
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    env_path = os.getenv("HEALTHCHECK_BASES_DIR")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(DEFAULT_WINDOWS_BASES_DIR))
    candidates.append(project_root / "bases")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return project_root / "bases"


def build_config(project_root: Path, bases_dir_override: str | None = None) -> AppConfig:
    bases_dir = resolve_bases_dir(project_root, bases_dir_override)
    output_dir = project_root / "output"
    payload_path = output_dir / "payload.json"
    html_output_path = output_dir / "Healthcheck_BU.html"
    audit_dir = output_dir / "audit"
    return AppConfig(
        project_root=project_root,
        bases_dir=bases_dir,
        output_dir=output_dir,
        payload_path=payload_path,
        html_output_path=html_output_path,
        audit_dir=audit_dir,
    )
