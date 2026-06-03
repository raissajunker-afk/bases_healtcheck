from __future__ import annotations

import importlib.util
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from config import (
    AUDIT_DIR,
    DEFAULT_BASES_DIR,
    LEGACY_ARCHIVE_PATH,
    LEGACY_OUTPUT_DIR,
    LEGACY_PROJECT_DIR,
    PAYLOAD_PATH,
    WINDOWS,
)
from processing.payload_builder import SECTION_TITLES
from processing.utils import clamp, clean_dimension_value, safe_div

try:
    import py7zr
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Este projeto precisa de py7zr para ler o arquivo .7z legado.") from exc


WINDOW_SPECS = {
    "mat_12m": {
        "label": WINDOWS["mat_12m"],
        "visits_field": "visitas_12m",
        "visits_per_day_field": "vis_dia_media",
        "doctor_field": "medicos_visit_12m",
        "days_field": "trabalhados_12m",
        "days_factor": 1,
        "absence_field": "ausencia_12m",
        "absence_factor": 1,
        "workdays_field": "uteis_12m",
        "workdays_factor": 1,
        "coverage_f2f_field": "pctCoberturaF2F_mat",
        "coverage_multi_field": "pctCoberturaMulti_mat",
        "covered_f2f_field": "hcpsCobertosF2F_mat",
        "covered_multi_field": "hcpsCobertosMulti_mat",
        "covered_mccp_field": "hcpsCobertosF2F_mat",
        "panel_field": "painel_size",
    },
    "last_3m": {
        "label": WINDOWS["last_3m"],
        "visits_field": "visitas_3m",
        "visits_per_day_field": "vis_dia_3m",
        "doctor_field": "mdms_visitados_3m",
        "days_field": "trabalhados_mes_3m",
        "days_factor": 3,
        "absence_field": "ausencia_mes_3m",
        "absence_factor": 3,
        "workdays_field": "uteis_mes_comum_3m",
        "workdays_factor": 3,
        "coverage_f2f_field": "pctCoberturaF2F_3m",
        "coverage_multi_field": "pctCoberturaMulti_3m",
        "covered_f2f_field": "hcpsCobertosF2F_3m",
        "covered_multi_field": "hcpsCobertosMulti_3m",
        "covered_mccp_field": "hcpsCobertosF2F_3m",
        "panel_field": "painel_mensal",
    },
    "last_closed_month": {
        "label": WINDOWS["last_closed_month"],
        "visits_field": "visitas_1m",
        "visits_per_day_field": "vis_dia_1m",
        "doctor_field": "mdms_visitados_1m",
        "days_field": "trabalhados_mes_1m",
        "days_factor": 1,
        "absence_field": "ausencia_mes_1m",
        "absence_factor": 1,
        "workdays_field": "uteis_mes_comum_1m",
        "workdays_factor": 1,
        "coverage_f2f_field": "pctCoberturaF2F_1m",
        "coverage_multi_field": "pctCoberturaMulti_1m",
        "covered_f2f_field": "hcpsCobertosF2F_1m",
        "covered_multi_field": "hcpsCobertosMulti_1m",
        "covered_mccp_field": "hcpsCobertosF2F_1m",
        "panel_field": "painel_mensal",
    },
    "current_month_partial": {
        "label": WINDOWS["current_month_partial"],
        "visits_field": "visitas_parcial",
        "visits_per_day_field": "vis_dia_parcial",
        "doctor_field": "mdms_visitados_parcial",
        "days_field": "trabalhados_mes_parcial",
        "days_factor": 1,
        "absence_field": "ausencia_mes_parcial",
        "absence_factor": 1,
        "workdays_field": "uteis_mes_comum_parcial",
        "workdays_factor": 1,
        "coverage_f2f_field": "pctCoberturaF2F_parcial",
        "coverage_multi_field": "pctCoberturaMulti_parcial",
        "covered_f2f_field": "hcpsCobertosF2F_parcial",
        "covered_multi_field": "hcpsCobertosMulti_parcial",
        "covered_mccp_field": "hcpsCobertosF2F_parcial",
        "panel_field": "painel_mensal",
    },
}


def _as_number(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _legacy_kind(file_name: str) -> str:
    name = file_name.lower()
    if "visita" in name:
        return "visitas"
    if "ausencia" in name:
        return "ausencias"
    if "mccp" in name:
        return "mccp"
    if "painel" in name:
        return "painel"
    if name.endswith(".xlsx"):
        return "excel"
    return "geral"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nao foi possivel carregar o modulo {module_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_legacy_project(
    project_dir: Path = LEGACY_PROJECT_DIR,
    archive_path: Path = LEGACY_ARCHIVE_PATH,
) -> Path:
    if (project_dir / "processar.py").exists():
        return project_dir

    if not archive_path.exists():
        raise FileNotFoundError(
            f"Arquivo legado nao encontrado em {archive_path}. "
            "Mantenha o .7z no repositorio ou informe um projeto legado extraido."
        )

    project_dir.parent.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extractall(path=project_dir.parent)

    if not (project_dir / "processar.py").exists():
        raise FileNotFoundError(
            f"O arquivo legado foi extraido, mas {project_dir / 'processar.py'} nao foi encontrado."
        )
    return project_dir


def _resolve_legacy_bases_dir(project_dir: Path, custom_bases_dir: Path | None = None) -> Path:
    if custom_bases_dir and custom_bases_dir.exists():
        return custom_bases_dir
    if DEFAULT_BASES_DIR.exists():
        return DEFAULT_BASES_DIR
    bundled = project_dir / "bases"
    if bundled.exists():
        return bundled
    if custom_bases_dir:
        return custom_bases_dir
    raise FileNotFoundError(
        "Nao foi possivel localizar uma pasta de bases para o fluxo legado."
    )


def run_legacy_processar(
    project_dir: Path,
    custom_bases_dir: Path | None = None,
    output_dir: Path = LEGACY_OUTPUT_DIR,
) -> tuple[dict, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    bases_dir = _resolve_legacy_bases_dir(project_dir, custom_bases_dir)

    module = _load_module(project_dir / "processar.py", "legacy_processar_runtime")
    module.BASES_DIR = str(bases_dir)
    module.OUT_DIR = str(output_dir)

    print(f"[legacy] Bases reais: {bases_dir}")
    print(f"[legacy] Output legado: {output_dir}")
    payload = module.main()

    payload_path = output_dir / "payload.json"
    if not payload_path.exists():
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    raw_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    return raw_payload, payload_path, bases_dir


def _scan_file_catalog(bases_dir: Path) -> list[dict]:
    catalog: list[dict] = []
    for path in sorted(bases_dir.glob("*")):
        if not path.is_file():
            continue
        row_count = 0
        if path.suffix.lower() == ".csv":
            try:
                with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
                    row_count = max(sum(1 for _ in handle) - 1, 0)
            except OSError:
                row_count = 0
        catalog.append(
            {
                "name": path.name,
                "kind": _legacy_kind(path.name),
                "rows": row_count,
                "separator": ";",
                "encoding": "auto",
                "path": str(path),
                "columns": [],
            }
        )
    return catalog


def _build_consultor_window_rows(legacy_payload: dict) -> list[dict]:
    rows: list[dict] = []
    consultores = legacy_payload.get("consultores", [])
    meta = legacy_payload.get("meta", {})
    default_visits_day = _as_number(meta.get("meta_visitas_dia_default"), 6.0) or 6.0

    for consultor in consultores:
        for window_id, spec in WINDOW_SPECS.items():
            visitas_total = _as_number(consultor.get(spec["visits_field"]))
            visitas_por_dia = _as_number(
                consultor.get(spec["visits_per_day_field"], consultor.get("vis_dia_media"))
            )
            dias_com_visita = _as_number(consultor.get(spec["days_field"])) * spec["days_factor"]
            dias_ausencia = _as_number(consultor.get(spec["absence_field"])) * spec["absence_factor"]
            dias_uteis = _as_number(consultor.get(spec["workdays_field"])) * spec["workdays_factor"]
            pct_ausencia = (
                _as_number(consultor.get("pct_ausencia"))
                if window_id == "mat_12m"
                else safe_div(dias_ausencia, dias_uteis) * 100.0
            )
            pct_cob_f2f = _as_number(
                consultor.get(spec["coverage_f2f_field"], consultor.get("pctCoberturaF2F", 0.0))
            )
            pct_cob_multi = _as_number(
                consultor.get(spec["coverage_multi_field"], consultor.get("pctCoberturaMulti", 0.0))
            )
            score_produtividade = clamp((visitas_por_dia / default_visits_day) * 100.0)
            score_capacidade = clamp(100.0 - pct_ausencia)
            score_territorial = clamp(_as_number(consultor.get("score_territorio")))
            score_geral = round(
                (score_produtividade + pct_cob_f2f + score_capacidade + score_territorial) / 4.0,
                2,
            )

            rows.append(
                {
                    "consultor": clean_dimension_value(consultor.get("nome")),
                    "consultor_id": clean_dimension_value(consultor.get("ISID")),
                    "sales_force": clean_dimension_value(consultor.get("sales_force")),
                    "gd": clean_dimension_value(consultor.get("gd_name")),
                    "gd_code": clean_dimension_value(consultor.get("gd_code")),
                    "territorio": clean_dimension_value(consultor.get("territorio")),
                    "window": window_id,
                    "visitas_total": round(visitas_total, 2),
                    "visitas_f2f": round(visitas_total, 2),
                    "dias_com_visita": round(dias_com_visita, 2),
                    "medicos_visitados": _as_number(
                        consultor.get(spec["doctor_field"], consultor.get("medicos_visit_12m"))
                    ),
                    "medicos_painel": _as_number(
                        consultor.get(spec["panel_field"], consultor.get("painel_size"))
                    ),
                    "medicos_mccp": _as_number(
                        consultor.get("hcpsAlvoTotal", consultor.get("mccp_panel"))
                    ),
                    "medicos_cobertos_multi": _as_number(
                        consultor.get(spec["covered_multi_field"], consultor.get("hcpsCobertosMulti"))
                    ),
                    "medicos_cobertos_f2f": _as_number(
                        consultor.get(spec["covered_f2f_field"], consultor.get("hcpsCobertosF2F"))
                    ),
                    "medicos_mccp_cobertos_f2f": _as_number(
                        consultor.get(spec["covered_mccp_field"], consultor.get("hcpsCobertosF2F"))
                    ),
                    "visitas_por_dia": round(visitas_por_dia, 2),
                    "pct_cobertura_multi": round(pct_cob_multi, 2),
                    "pct_cobertura_f2f": round(pct_cob_f2f, 2),
                    "pct_cobertura_mccp": round(pct_cob_f2f, 2),
                    "dias_ausencia": round(dias_ausencia, 2),
                    "dias_uteis_referencia": round(dias_uteis, 2),
                    "pct_ausencia": round(pct_ausencia, 2),
                    "cidades_visitadas": _as_number(consultor.get("n_cidades_visitadas")),
                    "ufs_visitadas": _as_number(consultor.get("n_ufs_visitadas")),
                    "bricks_visitados": _as_number(consultor.get("cidades_visitadas_n")),
                    "score_territorial": round(score_territorial, 2),
                    "score_produtividade": round(score_produtividade, 2),
                    "score_capacidade": round(score_capacidade, 2),
                    "score_geral": score_geral,
                }
            )
    return rows


def _build_monthly_series(legacy_payload: dict) -> list[dict]:
    monthly_rows = []
    for row in legacy_payload.get("series_team", {}).get("visitas", []):
        monthly_rows.append(
            {
                "month": row.get("ym"),
                "visitas_total": row.get("visitas", 0),
                "medicos_visitados": row.get("medicos_unicos_time", 0),
                "consultores_ativos": row.get("consultores_ativos", 0),
            }
        )
    return monthly_rows


def _build_overlap_pairs(legacy_payload: dict) -> list[dict]:
    pairs = []
    for row in legacy_payload.get("pares_overlap", []):
        pairs.append(
            {
                "consultor_a": clean_dimension_value(row.get("A_nome", row.get("A"))),
                "consultor_b": clean_dimension_value(row.get("B_nome", row.get("B"))),
                "medicos_compartilhados": row.get("shared", 0),
                "pct_min": row.get("pct_min", 0),
                "tipo": row.get("tipo", "Nao classificado"),
            }
        )
    return pairs


def _build_opportunity_doctors(legacy_payload: dict) -> list[dict]:
    medicos_meta = legacy_payload.get("medicos_meta", {})
    opportunities: list[dict] = []

    for consultor in legacy_payload.get("consultores", []):
        alvo = {str(item) for item in _as_list(consultor.get("mdmsAlvo")) if item}
        cobertos = {
            str(item)
            for item in _as_list(
                consultor.get("mdmsCobertosMulti_mat", consultor.get("mdmsCobertosMulti"))
            )
            if item
        }
        for mdm in sorted(alvo - cobertos):
            doctor_meta = medicos_meta.get(mdm, {})
            opportunities.append(
                {
                    "consultor": clean_dimension_value(consultor.get("nome")),
                    "consultor_id": clean_dimension_value(consultor.get("ISID")),
                    "sales_force": clean_dimension_value(consultor.get("sales_force")),
                    "gd": clean_dimension_value(consultor.get("gd_name")),
                    "doctor_id": mdm,
                    "doctor_name": clean_dimension_value(doctor_meta.get("nome")),
                    "specialty_primary": clean_dimension_value(
                        doctor_meta.get("especialidade"),
                        fallback="sem_classificacao",
                    ),
                    "franchise": clean_dimension_value(consultor.get("sales_force")),
                }
            )
    return opportunities[:2500]


def _build_specialty_franchise(legacy_payload: dict) -> list[dict]:
    medicos_meta = legacy_payload.get("medicos_meta", {})
    stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "medicos_painel": 0,
            "medicos_cobertos": 0,
            "medicos_f2f": 0,
            "medicos_mccp": 0,
        }
    )

    for consultor in legacy_payload.get("consultores", []):
        franchise = clean_dimension_value(consultor.get("sales_force"))
        alvo = {str(item) for item in _as_list(consultor.get("mdmsAlvo")) if item}
        cobertos_multi = {
            str(item)
            for item in _as_list(
                consultor.get("mdmsCobertosMulti_mat", consultor.get("mdmsCobertosMulti"))
            )
            if item
        }
        cobertos_f2f = {
            str(item)
            for item in _as_list(
                consultor.get("mdmsCobertosF2F_mat", consultor.get("mdmsCobertosF2F"))
            )
            if item
        }
        for mdm in alvo:
            specialty = clean_dimension_value(
                medicos_meta.get(mdm, {}).get("especialidade"),
                fallback="sem_classificacao",
            )
            key = (franchise, specialty)
            stats[key]["medicos_painel"] += 1
            stats[key]["medicos_mccp"] += 1
            if mdm in cobertos_multi:
                stats[key]["medicos_cobertos"] += 1
            if mdm in cobertos_f2f:
                stats[key]["medicos_f2f"] += 1

    rows = []
    for (franchise, specialty), values in stats.items():
        medicos_painel = values["medicos_painel"]
        rows.append(
            {
                "franchise": franchise,
                "specialty_primary": specialty,
                "medicos_painel": medicos_painel,
                "medicos_cobertos": values["medicos_cobertos"],
                "medicos_f2f": values["medicos_f2f"],
                "medicos_mccp": values["medicos_mccp"],
                "pct_cobertura": round(
                    safe_div(values["medicos_cobertos"], medicos_painel) * 100.0, 2
                ),
            }
        )
    rows.sort(key=lambda item: (-item["medicos_painel"], item["franchise"], item["specialty_primary"]))
    return rows[:500]


def _build_top_specialties(legacy_payload: dict) -> list[dict]:
    counts = Counter()
    for values in legacy_payload.get("medicos_meta", {}).values():
        specialty = clean_dimension_value(values.get("especialidade"), fallback="sem_classificacao")
        counts[specialty] += 1
    return [{"label": key, "value": value} for key, value in counts.most_common(12)]


def _build_panel_sample(legacy_payload: dict) -> list[dict]:
    rows = []
    for consultor in legacy_payload.get("consultores", [])[:200]:
        rows.append(
            {
                "consultor": clean_dimension_value(consultor.get("nome")),
                "sales_force": clean_dimension_value(consultor.get("sales_force")),
                "gd": clean_dimension_value(consultor.get("gd_name")),
                "doctor_id": clean_dimension_value(consultor.get("ISID")),
                "doctor_name": clean_dimension_value(consultor.get("nome")),
                "specialty_primary": clean_dimension_value(
                    consultor.get("tipo_setor"),
                    fallback="Nao informado",
                ),
                "franchise": clean_dimension_value(consultor.get("sales_force")),
            }
        )
    return rows


def _build_visit_sample(legacy_payload: dict) -> list[dict]:
    consultor_lookup = {
        row.get("ISID"): row for row in legacy_payload.get("consultores", [])
    }
    rows = []
    for row in legacy_payload.get("series_consultor", [])[:250]:
        consultor = consultor_lookup.get(row.get("ISID"), {})
        rows.append(
            {
                "consultor": clean_dimension_value(consultor.get("nome", row.get("ISID"))),
                "sales_force": clean_dimension_value(consultor.get("sales_force")),
                "gd": clean_dimension_value(consultor.get("gd_name")),
                "doctor_id": clean_dimension_value(row.get("ISID")),
                "doctor_name": clean_dimension_value(consultor.get("nome")),
                "visit_date": row.get("ym"),
                "channel": "Agregado mensal",
            }
        )
    return rows


def _build_absence_sample(legacy_payload: dict) -> list[dict]:
    consultor_lookup = {
        row.get("ISID"): row for row in legacy_payload.get("consultores", [])
    }
    rows = []
    for row in legacy_payload.get("series_consultor", []):
        if _as_number(row.get("ausencia")) <= 0:
            continue
        consultor = consultor_lookup.get(row.get("ISID"), {})
        rows.append(
            {
                "consultor": clean_dimension_value(consultor.get("nome", row.get("ISID"))),
                "sales_force": clean_dimension_value(consultor.get("sales_force")),
                "gd": clean_dimension_value(consultor.get("gd_name")),
                "absence_date": row.get("ym"),
                "absence_type": "Agregado mensal",
            }
        )
        if len(rows) >= 250:
            break
    return rows


def _build_insights(legacy_payload: dict, opportunity_doctors: list[dict]) -> list[dict]:
    kpis = legacy_payload.get("kpis", {})
    insights = []

    coverage = _as_number(kpis.get("mccp_pct_cumprido_team"))
    if coverage < 50:
        insights.append(
            {
                "type": "alerta",
                "title": "Cobertura MCCP abaixo de 50%",
                "message": "Use as paginas de Cobertura, Oportunidades e Plano de Acao para atacar os consultores com maior gap.",
            }
        )

    vis_day = _as_number(kpis.get("vis_dia_media"))
    if vis_day < 5:
        insights.append(
            {
                "type": "risco",
                "title": "Produtividade diaria abaixo da referencia",
                "message": "A media do time esta abaixo de 5 visitas por dia, sugerindo revisao de rotina e capacidade.",
            }
        )

    if len(opportunity_doctors) > 0:
        insights.append(
            {
                "type": "oportunidade",
                "title": "Medicos alvo ainda sem cobertura",
                "message": f"Foram identificadas {len(opportunity_doctors)} oportunidades de cobertura a partir do payload legado.",
            }
        )

    if not insights:
        insights.append(
            {
                "type": "info",
                "title": "Leitura executiva sem alertas criticos",
                "message": "O portal foi montado sobre o payload real e esta pronto para expansao incremental por secao.",
            }
        )
    return insights


def _build_sections(legacy_payload: dict) -> dict:
    kpis = legacy_payload.get("kpis", {})
    summary = {
        "score_geral": round(
            (
                _as_number(kpis.get("vis_dia_media")) * 10.0
                + _as_number(kpis.get("mccp_pct_cumprido_team"))
                + clamp(100.0 - _as_number(kpis.get("pct_ausencia_media")))
            )
            / 3.0,
            2,
        ),
        "consultores": int(_as_number(kpis.get("n_consultores"))),
        "medicos": int(_as_number(kpis.get("painel_total_time"))),
    }
    return {
        section_id: {"title": title, "summary": summary}
        for section_id, title in SECTION_TITLES.items()
    }


def legacy_payload_to_portal_payload(
    legacy_payload: dict,
    project_dir: Path,
    bases_dir: Path,
) -> dict:
    generated_at = legacy_payload.get("meta", {}).get("gerado_em")
    try:
        generated_iso = datetime.strptime(generated_at, "%d/%m/%Y %H:%M").isoformat()
    except (TypeError, ValueError):
        generated_iso = datetime.now().isoformat()

    consultor_window = _build_consultor_window_rows(legacy_payload)
    opportunity_doctors = _build_opportunity_doctors(legacy_payload)
    file_catalog = _scan_file_catalog(bases_dir)

    payload = {
        "meta": {
            "title": "Portal Analitico - Healthcheck Operacional",
            "generated_at": generated_iso,
            "base_dir": str(bases_dir),
            "files_loaded": len(file_catalog),
            "warnings": [],
            "source_mode": "legacy",
            "legacy_project_dir": str(project_dir),
            "legacy_snapshot": legacy_payload.get("meta", {}).get("snapshot_painel"),
            "legacy_cycle": legacy_payload.get("meta", {}).get("ciclo_mccp"),
        },
        "dimensions": {
            "consultores": sorted(
                {row["consultor"] for row in consultor_window if row["consultor"]}
            ),
            "sales_forces": sorted(
                {row["sales_force"] for row in consultor_window if row["sales_force"]}
            ),
            "gds": sorted({row["gd"] for row in consultor_window if row["gd"]}),
            "windows": [{"id": key, "label": value} for key, value in WINDOWS.items()],
        },
        "analytics": {
            "consultor_window": consultor_window,
            "monthly_series": _build_monthly_series(legacy_payload),
            "overlap_pairs": _build_overlap_pairs(legacy_payload),
            "opportunity_doctors": opportunity_doctors,
            "specialty_franchise": _build_specialty_franchise(legacy_payload),
            "top_specialties": _build_top_specialties(legacy_payload),
            "top_channels": [],
            "file_catalog": file_catalog,
            "visit_sample": _build_visit_sample(legacy_payload),
            "panel_sample": _build_panel_sample(legacy_payload),
            "absence_sample": _build_absence_sample(legacy_payload),
            "insights": _build_insights(legacy_payload, opportunity_doctors),
        },
        "sections": _build_sections(legacy_payload),
        "audit": {
            "legacy_meta": legacy_payload.get("meta", {}),
            "legacy_kpis": legacy_payload.get("kpis", {}),
            "legacy_counts": {
                "consultores": len(legacy_payload.get("consultores", [])),
                "sales_forces": len(legacy_payload.get("sales_forces", [])),
                "gds": len(legacy_payload.get("gds", [])),
                "pares_overlap": len(legacy_payload.get("pares_overlap", [])),
            },
        },
    }
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def rodar_processamento_legado(
    custom_bases_dir: Path | None = None,
    project_dir: Path = LEGACY_PROJECT_DIR,
    archive_path: Path = LEGACY_ARCHIVE_PATH,
) -> tuple[dict, dict]:
    project_dir = ensure_legacy_project(project_dir=project_dir, archive_path=archive_path)
    legacy_payload, legacy_payload_path, bases_dir = run_legacy_processar(
        project_dir=project_dir,
        custom_bases_dir=custom_bases_dir,
        output_dir=LEGACY_OUTPUT_DIR,
    )
    portal_payload = legacy_payload_to_portal_payload(
        legacy_payload=legacy_payload,
        project_dir=project_dir,
        bases_dir=bases_dir,
    )

    PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOAD_PATH.write_text(
        json.dumps(portal_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (AUDIT_DIR / "legacy_payload_raw.json").write_text(
        json.dumps(legacy_payload, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    runtime = {
        "source_mode": "legacy",
        "project_dir": str(project_dir),
        "bases_dir": str(bases_dir),
        "legacy_payload_path": str(legacy_payload_path),
    }
    return portal_payload, runtime
