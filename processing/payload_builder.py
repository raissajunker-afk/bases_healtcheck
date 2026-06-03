from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from config import SECTION_BLUEPRINTS, build_page_registry


def _default_page_payload() -> dict[str, Any]:
    return {
        "cards": [],
        "charts": [],
        "tables": [],
        "insights": [],
        "exports": [],
        "methodology": [],
    }


def _build_sections_skeleton() -> dict[str, Any]:
    sections: dict[str, Any] = {}
    for section in SECTION_BLUEPRINTS:
        pages: dict[str, Any] = {}
        for subsection in section.subsections:
            pages[subsection.id] = _default_page_payload()
        sections[section.id] = {
            "title": section.title,
            "description": section.description,
            "summary": {},
            "pages": pages,
        }
    return sections


def montar_payload(
    *,
    bases: dict[str, Any],
    painel: dict[str, Any],
    visitas: dict[str, Any],
    ausencias: dict[str, Any],
    cobertura: dict[str, Any],
    territorio: dict[str, Any],
    overlap: dict[str, Any],
    indices: dict[str, Any],
) -> dict[str, Any]:
    sections = _build_sections_skeleton()

    sections["executive_overview"]["summary"] = {
        "consultores_ativos": painel.get("kpis", {}).get("total_consultores_ativos", 0),
        "medicos_painel": painel.get("kpis", {}).get("total_medicos_painel", 0),
        "visitas_totais": visitas.get("resumo", {}).get("visitas_totais", 0),
        "cobertura_f2f": cobertura.get("summary", {}).get("pct_cobertura_f2f", 0.0),
    }
    sections["executive_overview"]["pages"]["snapshot_executivo"] = {
        "cards": [
            {
                "id": "total_consultores_ativos",
                "title": "Consultores Ativos",
                "value": painel.get("kpis", {}).get("total_consultores_ativos", 0),
                "format": "int",
            },
            {
                "id": "total_medicos_painel",
                "title": "Medicos no Painel",
                "value": painel.get("kpis", {}).get("total_medicos_painel", 0),
                "format": "int",
            },
            {
                "id": "visitas_totais",
                "title": "Visitas Totais",
                "value": visitas.get("resumo", {}).get("visitas_totais", 0),
                "format": "int",
            },
            {
                "id": "pct_cobertura_f2f",
                "title": "Cobertura F2F",
                "value": cobertura.get("summary", {}).get("pct_cobertura_f2f", 0.0),
                "format": "percent",
            },
        ],
        "charts": [
            {
                "id": "serie_mensal_visitas",
                "title": "Serie Mensal de Visitas",
                "type": "bar",
                "data": visitas.get("serie_mensal", []),
            }
        ],
        "tables": [
            {
                "id": "ranking_produtividade",
                "title": "Top Consultores por Volume de Visitas",
                "columns": ["consultor", "visitas"],
                "rows": visitas.get("ranking_consultor", [])[:15],
            }
        ],
        "insights": [
            {
                "kind": "oportunidade",
                "text": (
                    "Cobertura F2F abaixo de 70% sugere oportunidade de reforco imediato em medicos nao cobertos."
                    if cobertura.get("summary", {}).get("pct_cobertura_f2f", 0.0) < 70
                    else "Cobertura F2F em nivel saudavel para o periodo."
                ),
            }
        ],
        "exports": [{"label": "Exportar payload executivo (JSON)", "target": "output/payload.json"}],
        "methodology": [
            "Indicadores preservam logica atual de processamento e servem como base para expansao modular.",
        ],
    }

    sections["performance_comercial"]["summary"] = visitas.get("resumo", {})
    sections["performance_comercial"]["pages"]["produtividade_geral"] = {
        "cards": [
            {
                "id": "visitas_totais",
                "title": "Visitas Totais",
                "value": visitas.get("resumo", {}).get("visitas_totais", 0),
                "format": "int",
            },
            {
                "id": "visitas_f2f",
                "title": "Visitas F2F",
                "value": visitas.get("resumo", {}).get("visitas_f2f", 0),
                "format": "int",
            },
            {
                "id": "visitas_por_dia_media",
                "title": "Visitas por Dia (media)",
                "value": visitas.get("resumo", {}).get("visitas_por_dia_media", 0.0),
                "format": "float1",
            },
        ],
        "charts": [{"id": "serie_visitas", "title": "Tendencia de Visitas", "type": "line", "data": visitas.get("serie_mensal", [])}],
        "tables": [
            {
                "id": "ranking_consultor",
                "title": "Ranking de Consultores",
                "columns": ["consultor", "visitas"],
                "rows": visitas.get("ranking_consultor", [])[:30],
            }
        ],
        "insights": [{"kind": "tendencia", "text": "Use a serie mensal para validar aceleracao ou desaceleracao recente."}],
        "exports": [{"label": "Exportar ranking de produtividade (CSV)", "target": "performance_comercial/produtividade_geral"}],
        "methodology": ["Visitas por dia usam dias com atividade registrada nas bases de visitas."],
    }

    sections["cobertura_painel"]["summary"] = cobertura.get("summary", {})
    sections["cobertura_painel"]["pages"]["cobertura_mccp"] = {
        "cards": [
            {
                "id": "medicos_painel",
                "title": "HCPs no Painel",
                "value": cobertura.get("summary", {}).get("medicos_painel", 0),
                "format": "int",
            },
            {
                "id": "medicos_visitados",
                "title": "HCPs Cobertos",
                "value": cobertura.get("summary", {}).get("medicos_visitados", 0),
                "format": "int",
            },
            {
                "id": "pct_cobertura_f2f",
                "title": "% Cobertura F2F",
                "value": cobertura.get("summary", {}).get("pct_cobertura_f2f", 0.0),
                "format": "percent",
            },
        ],
        "charts": [],
        "tables": [
            {
                "id": "ranking_cobertura_consultor",
                "title": "Cobertura por Consultor",
                "columns": ["consultor", "medicos_painel", "medicos_visitados", "pct_cobertura_f2f"],
                "rows": cobertura.get("ranking_consultor", [])[:30],
            },
            {
                "id": "medicos_nao_cobertos",
                "title": "Medicos sem Cobertura",
                "columns": ["medico_id"],
                "rows": cobertura.get("medicos_nao_cobertos", [])[:50],
            },
        ],
        "insights": [
            {
                "kind": "alerta",
                "text": (
                    "Ha volume relevante de medicos sem cobertura: priorizar ativacao por consultor."
                    if cobertura.get("summary", {}).get("medicos_nao_cobertos", 0) > 0
                    else "Nao foram detectados medicos descobertos no recorte atual."
                ),
            }
        ],
        "exports": [{"label": "Exportar medicos descobertos", "target": "cobertura_painel/cobertura_mccp"}],
        "methodology": ["Cobertura calculada como medicos em painel com ao menos uma visita registrada."],
    }

    sections["eficiencia_territorial"]["summary"] = territorio.get("summary", {})
    sections["eficiencia_territorial"]["pages"]["score_territorio"] = {
        "cards": [
            {
                "id": "consultores_com_dados_territoriais",
                "title": "Consultores com Dados Territoriais",
                "value": territorio.get("summary", {}).get("consultores_com_dados_territoriais", 0),
                "format": "int",
            },
            {
                "id": "bricks_unicos",
                "title": "Bricks Unicos",
                "value": territorio.get("summary", {}).get("bricks_unicos", 0),
                "format": "int",
            },
        ],
        "charts": [],
        "tables": [
            {
                "id": "score_territorial",
                "title": "Score Territorial por Consultor",
                "columns": ["consultor", "score_territorial", "tipo_setor"],
                "rows": territorio.get("score_territorio", [])[:30],
            }
        ],
        "insights": [{"kind": "melhoria", "text": "Setores com dispersao elevada tendem a reduzir produtividade diaria."}],
        "exports": [{"label": "Exportar score territorial", "target": "eficiencia_territorial/score_territorio"}],
        "methodology": ["Score territorial e indice composto para orientacao inicial; pode ser refinado na fase 2."],
    }

    sections["ausencias_capacidade"]["summary"] = ausencias.get("resumo", {})
    sections["ausencias_capacidade"]["pages"]["ausencia_total"] = {
        "cards": [
            {
                "id": "dias_ausencia_total",
                "title": "Dias de Ausencia",
                "value": ausencias.get("resumo", {}).get("dias_ausencia_total", 0.0),
                "format": "float1",
            },
            {
                "id": "registros_ausencia",
                "title": "Registros de Ausencia",
                "value": ausencias.get("resumo", {}).get("registros_ausencia", 0),
                "format": "int",
            },
        ],
        "charts": [],
        "tables": [
            {
                "id": "ausencias_tipo",
                "title": "Ausencias por Tipo",
                "columns": ["tipo_ausencia", "dias"],
                "rows": ausencias.get("por_tipo", [])[:20],
            }
        ],
        "insights": [{"kind": "risco", "text": "Ausencias elevadas impactam diretamente capacidade de cobertura de painel."}],
        "exports": [{"label": "Exportar ausencias por tipo", "target": "ausencias_capacidade/ausencia_total"}],
        "methodology": ["Quando base nao possui coluna de dias, cada registro conta como 1 dia."],
    }

    sections["overlap_conflitos"]["summary"] = overlap.get("summary", {})
    sections["overlap_conflitos"]["pages"]["overlap_intra_time"] = {
        "cards": [
            {
                "id": "medicos_compartilhados",
                "title": "Medicos Compartilhados",
                "value": overlap.get("summary", {}).get("medicos_compartilhados", 0),
                "format": "int",
            },
            {
                "id": "pares_com_overlap",
                "title": "Pares com Overlap",
                "value": overlap.get("summary", {}).get("pares_com_overlap", 0),
                "format": "int",
            },
        ],
        "charts": [],
        "tables": [
            {
                "id": "pares_overlap",
                "title": "Top Pares com Sobreposicao",
                "columns": ["consultor_a", "consultor_b", "medicos_compartilhados"],
                "rows": overlap.get("pares_overlap", [])[:30],
            }
        ],
        "insights": [{"kind": "inconsistencia", "text": "Sobreposicao recorrente pode indicar conflito de ownership territorial."}],
        "exports": [{"label": "Exportar overlap", "target": "overlap_conflitos/overlap_intra_time"}],
        "methodology": ["Overlap considera medico visitado por mais de um consultor no recorte."],
    }

    sections["especialidades_franquias"]["summary"] = {
        "iaef": indices.get("iaef", 0.0),
        "icef": indices.get("icef", 0.0),
        "ifef": indices.get("ifef", 0.0),
        "idef": indices.get("idef", 0.0),
        "gap_estrategico_especialidade": indices.get("gap_estrategico_especialidade", 0.0),
    }
    sections["especialidades_franquias"]["pages"]["visao_geral"] = {
        "cards": [
            {"id": "iaef", "title": "IAEF", "value": indices.get("iaef", 0.0), "format": "float1"},
            {"id": "icef", "title": "ICEF", "value": indices.get("icef", 0.0), "format": "float1"},
            {"id": "ifef", "title": "IFEF", "value": indices.get("ifef", 0.0), "format": "float1"},
            {"id": "idef", "title": "IDEF", "value": indices.get("idef", 0.0), "format": "float1"},
            {
                "id": "gap_estrategico_especialidade",
                "title": "Gap Estrategico",
                "value": indices.get("gap_estrategico_especialidade", 0.0),
                "format": "float1",
            },
        ],
        "charts": [],
        "tables": [],
        "insights": [
            {
                "kind": "recomendacao",
                "text": "Use franquias_especialidades.csv para evoluir indicadores estrategicos sem hardcode.",
            }
        ],
        "exports": [{"label": "Exportar indices estrategicos", "target": "especialidades_franquias/visao_geral"}],
        "methodology": [
            "Indices IAEF/ICEF/IFEF/IDEF estao preparados para evolucao incremental na fase 3.",
        ],
    }

    sections["governanca_auditoria"]["summary"] = {
        "arquivos_carregados": len(bases.get("files", [])),
        "registros_deduplicados": 0,
        "medicos_sem_especialidade": painel.get("auditoria", {}).get("medicos_sem_especialidade", 0),
    }
    sections["governanca_auditoria"]["pages"]["fontes_dados"] = {
        "cards": [
            {
                "id": "arquivos_carregados",
                "title": "Arquivos Carregados",
                "value": len(bases.get("files", [])),
                "format": "int",
            },
            {
                "id": "medicos_sem_especialidade",
                "title": "Medicos sem Especialidade",
                "value": painel.get("auditoria", {}).get("medicos_sem_especialidade", 0),
                "format": "int",
            },
        ],
        "charts": [],
        "tables": [
            {
                "id": "fontes",
                "title": "Fontes Carregadas",
                "columns": ["file_name", "rows", "delimiter", "domain"],
                "rows": bases.get("files", []),
            }
        ],
        "insights": [{"kind": "auditoria", "text": "Use esta visao para rastrear origem e completude do processamento."}],
        "exports": [{"label": "Exportar auditoria", "target": "output/audit/"}],
        "methodology": ["Camada de governanca separada de simulador para manter confianca metodologica."],
    }

    payload = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "bases_dir": bases.get("bases_dir"),
            "version": "portal-modular-v1",
        },
        "dimensions": {
            "consultores": painel.get("consultores", []),
            "sales_forces": painel.get("sales_forces", []),
            "gds": painel.get("gds", []),
            "medicos": painel.get("medicos", []),
        },
        "sections": sections,
        "page_registry": build_page_registry(),
        "audit": {
            "files_loaded": bases.get("files", []),
            "domains_detected": bases.get("domains", {}),
            "notes": [
                "Primeira etapa focada em infraestrutura modular sem alterar formulas legadas de negocio.",
                "Pipeline preparada para evolucao incremental de calculos por dominio.",
            ],
        },
    }
    return payload


def salvar_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
