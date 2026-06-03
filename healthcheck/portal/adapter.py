"""Adapter: payload real do `processar.py` -> payload modular do portal.

NÃO recalcula regra de negócio. Apenas reorganiza o contrato real (consultores,
kpis, séries, overlap, mccp, médicos) nos `datasets`/`summaries`/`dimensions`
que o frontend modular consome, e anexa o `registry` de navegação.

Assim preservamos 100% das fórmulas do processar.py e ganhamos o portal.
"""

from __future__ import annotations

import config
from portal import registry as registry_mod


def _distinct(rows, field):
    return sorted({(r.get(field) or "").strip() for r in rows if (r.get(field) or "").strip()})


def construir_portal_payload(real: dict) -> dict:
    consultores_raw = real.get("consultores", [])
    kpis = real.get("kpis", {})
    meta_real = real.get("meta", {})

    # ---- consultores: normaliza campos de filtro/label ----
    isid_to_nome = {}
    isid_to_sf = {}
    isid_to_gd = {}
    consultores = []
    for c in consultores_raw:
        cc = dict(c)
        cc["consultor"] = c.get("nome") or c.get("ISID")
        cc["gd"] = c.get("gd_name") or ""
        cc["sales_force"] = c.get("sales_force") or ""
        consultores.append(cc)
        isid_to_nome[c.get("ISID")] = cc["consultor"]
        isid_to_sf[c.get("ISID")] = cc["sales_force"]
        isid_to_gd[c.get("ISID")] = cc["gd"]

    # ---- sales forces / gds ----
    sales_forces = [dict(s) for s in real.get("sales_forces", [])]
    gds = []
    for g in real.get("gds", []):
        gg = dict(g)
        gg["gd"] = g.get("gd_name") or g.get("gd_code") or ""
        gds.append(gg)

    # ---- overlap ----
    overlap = []
    for p in real.get("pares_overlap", []):
        overlap.append({
            "consultor_a": p.get("A_nome") or p.get("A"),
            "consultor_b": p.get("B_nome") or p.get("B"),
            "sales_force": p.get("A_sf", ""),
            "sf_b": p.get("B_sf", ""),
            "gd": p.get("A_gd", ""),
            "tipo": p.get("tipo", ""),
            "cross_team": "cross" in (p.get("tipo") or "").lower(),
            "shared": p.get("shared", 0),
            "pct_min": p.get("pct_min", 0),
            "medicos_mesmo_dia_n": p.get("medicos_mesmo_dia_n", 0),
            "pct_mesmo_dia": p.get("pct_mesmo_dia", 0),
        })

    # ---- médicos (catálogo) + especialidades ----
    medicos = []
    esp_count: dict[str, int] = {}
    for mdm, m in (real.get("medicos_meta", {}) or {}).items():
        esp = (m.get("especialidade") or "Sem classificação").replace("_BR", "").replace("_", " ").strip()
        medicos.append({
            "mdm": mdm,
            "nome": m.get("nome", ""),
            "crm": m.get("crm", ""),
            "especialidade": esp,
            "tipo": m.get("tipo", ""),
        })
        esp_count[esp] = esp_count.get(esp, 0) + 1
    especialidades = [{"especialidade": k, "n_medicos": v} for k, v in
                      sorted(esp_count.items(), key=lambda x: -x[1])]

    # ---- séries temporais ----
    st = real.get("series_team", {})
    serie_visitas = st.get("visitas", [])
    serie_ausencias = st.get("ausencia", [])
    serie_painel = st.get("painel", [])
    serie_pv = real.get("serie_painel_visitas_time", [])

    # ---- mccp histórico ----
    mccp_hist = []
    for r in real.get("mccp_historico", []):
        isid = r.get("ISID")
        mccp_hist.append({
            "consultor": isid_to_nome.get(isid, isid),
            "sales_force": isid_to_sf.get(isid, ""),
            "gd": isid_to_gd.get(isid, ""),
            "ISID": isid,
            "ciclo": r.get("ciclo", ""),
            "panel": r.get("panel", 0),
            "target_tri": r.get("target_tri", 0),
            "realizado": r.get("realizado", 0),
            "pct_cumprido": r.get("pct_cumprido", 0),
            "freq_tri": r.get("freq_tri", 0),
        })

    datasets = {
        "consultores": consultores,
        "sales_forces": sales_forces,
        "gds": gds,
        "overlap_pares": overlap,
        "medicos": medicos,
        "especialidades": especialidades,
        "serie_visitas": serie_visitas,
        "serie_ausencias": serie_ausencias,
        "serie_painel": serie_painel,
        "serie_pv": serie_pv,
        "mccp_hist": mccp_hist,
        "freq_dist_mccp": [{"faixa": k, "n": v} for k, v in (real.get("freq_dist_mccp", {}) or {}).items()],
    }

    summaries = {
        "kpis": kpis,
        "meta_real": meta_real,
    }

    dimensions = {
        "gd": _distinct(consultores, "gd"),
        "sales_force": _distinct(consultores, "sales_force"),
        "consultor": _distinct(consultores, "consultor"),
        "janelas": [{"id": k, "label": v["label"]} for k, v in config.JANELAS.items()],
        "janela_padrao": config.JANELA_PADRAO,
    }
    janela_sufixos = {k: v["sufixo"] for k, v in config.JANELAS.items()}

    meta = {
        "titulo": f"Healthcheck Operacional — {meta_real.get('bu_filtro') or meta_real.get('bu') or 'BU'}",
        "bu": meta_real.get("bu_filtro") or meta_real.get("bu", ""),
        "gerado_em": meta_real.get("gerado_em", ""),
        "snapshot_painel": meta_real.get("snapshot_painel", ""),
        "ciclo_mccp": meta_real.get("ciclo_mccp", ""),
        "janela_label": kpis.get("janela_label", ""),
        "sfs_excluidas": meta_real.get("sfs_excluidas", []),
        "benchmarks": config.BENCHMARKS,
        "janela_sufixos": janela_sufixos,
        "observacoes": meta_real.get("observacoes", ""),
        "real_meta": meta_real,
    }

    return {
        "meta": meta,
        "dimensions": dimensions,
        "datasets": datasets,
        "summaries": summaries,
        "registry": registry_mod.build_registry(),
    }
