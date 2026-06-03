from __future__ import annotations

import json
from pathlib import Path

from frontend.page_registry import build_page_registry


def _build_css() -> str:
    return """
    :root {
      --bg: #f4f7fb;
      --surface: #ffffff;
      --surface-2: #eef3fb;
      --text: #152033;
      --muted: #5f6f8c;
      --primary: #1f5eff;
      --primary-soft: rgba(31, 94, 255, 0.12);
      --good: #1f9d65;
      --warn: #d08a00;
      --bad: #d92d20;
      --border: #d8e1ef;
      --shadow: 0 12px 28px rgba(16, 24, 40, 0.08);
      --radius: 16px;
      --max-width: 1440px;
      font-family: Arial, Helvetica, sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: linear-gradient(180deg, #f7f9fc 0%, #eef3fb 100%);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
    }
    a { color: inherit; text-decoration: none; }
    button, select {
      font: inherit;
    }
    .app-shell {
      max-width: var(--max-width);
      margin: 0 auto;
      padding: 24px;
    }
    .topbar {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
      background: rgba(255,255,255,0.9);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 20px 24px;
      box-shadow: var(--shadow);
      position: sticky;
      top: 12px;
      backdrop-filter: blur(12px);
      z-index: 20;
    }
    .brand h1 {
      margin: 0 0 6px;
      font-size: 24px;
    }
    .brand p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }
    .filter-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 160px;
    }
    .filter-group label {
      font-size: 12px;
      color: var(--muted);
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    select, .ghost-btn, .primary-btn {
      border-radius: 12px;
      padding: 10px 12px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
    }
    .primary-btn {
      background: var(--primary);
      border-color: var(--primary);
      color: #fff;
      font-weight: bold;
      cursor: pointer;
    }
    .ghost-btn {
      background: transparent;
      cursor: pointer;
    }
    .hero {
      margin-top: 24px;
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
    }
    .hero-card, .panel, .block-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .hero-card {
      padding: 24px;
    }
    .hero-card h2 {
      margin: 0 0 12px;
      font-size: 30px;
    }
    .hero-card p {
      margin: 0 0 12px;
      color: var(--muted);
      line-height: 1.5;
    }
    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 10px;
      border-radius: 999px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
      font-weight: bold;
    }
    .insight-stack {
      padding: 20px;
      display: grid;
      gap: 12px;
    }
    .insight-chip {
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: linear-gradient(180deg, #fff 0%, #f7faff 100%);
    }
    .insight-chip strong {
      display: block;
      margin-bottom: 4px;
    }
    .breadcrumbs {
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
    }
    .section-grid, .page-grid, .kpi-grid, .block-grid {
      display: grid;
      gap: 18px;
      margin-top: 20px;
    }
    .section-grid {
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    }
    .page-grid {
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
    .kpi-grid {
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
    .block-grid {
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    }
    .section-card, .page-card, .kpi-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 20px;
      transition: transform 0.18s ease, box-shadow 0.18s ease;
      cursor: pointer;
    }
    .section-card:hover, .page-card:hover, .kpi-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 18px 36px rgba(16, 24, 40, 0.12);
    }
    .section-card h3, .page-card h3, .kpi-card h3 {
      margin: 0 0 8px;
      font-size: 18px;
    }
    .section-card p, .page-card p, .kpi-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }
    .kpi-value {
      display: block;
      font-size: 34px;
      font-weight: bold;
      margin-top: 14px;
      color: var(--primary);
    }
    .page-header {
      margin-top: 20px;
      padding: 22px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .page-header h2 {
      margin: 0 0 8px;
      font-size: 28px;
    }
    .page-header p {
      margin: 6px 0;
      color: var(--muted);
      line-height: 1.5;
    }
    .block-card {
      padding: 18px;
      overflow: hidden;
    }
    .block-card h3 {
      margin: 0 0 14px;
      font-size: 18px;
    }
    .metric-caption {
      color: var(--muted);
      font-size: 13px;
    }
    .svg-chart {
      width: 100%;
      height: 260px;
      display: block;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid #ebf0f7;
      text-align: left;
      font-size: 13px;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      background: #f8faff;
      position: sticky;
      top: 0;
    }
    .table-wrap {
      max-height: 360px;
      overflow: auto;
      border: 1px solid #ebf0f7;
      border-radius: 12px;
    }
    .block-actions {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 10px;
    }
    .empty-state {
      padding: 24px;
      border: 1px dashed var(--border);
      border-radius: 14px;
      color: var(--muted);
      background: #fbfcff;
    }
    .footer-note {
      margin: 28px 0 12px;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
    }
    @media (max-width: 960px) {
      .hero {
        grid-template-columns: 1fr;
      }
      .app-shell {
        padding: 16px;
      }
      .topbar {
        position: static;
      }
      .block-grid {
        grid-template-columns: 1fr;
      }
    }
    """


def _build_js(payload: dict, registry: dict) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    registry_json = json.dumps(registry, ensure_ascii=False)
    template = """
    const APP_DATA = __PAYLOAD__;
    const PAGE_REGISTRY = __REGISTRY__;
    const STORAGE_KEY = "healthcheck-portal-state";
    const METHOD_TEXT = {
      executive: "Indicadores consolidados a partir do agregado por consultor e janela analitica. A camada executiva sintetiza score, cobertura, produtividade e alertas.",
      performance: "Produtividade baseada no agregado por consultor e janela. O portal combina visitas totais, dias com visita e visitas por dia.",
      coverage: "Cobertura baseada na relacao entre painel/MCCP e medicos efetivamente visitados, com leitura multicanal e F2F.",
      visitation: "Ritmo calculado com base em visitas, dias ativos e serie mensal consolidada.",
      territory: "Score territorial sintetico baseado em amplitude geografica e carga de execucao.",
      absence: "Ausencias consolidadas por consultor e janela, comparadas com dias uteis de referencia.",
      specialty: "A camada de especialidades utiliza a combinacao especialidade x franquia disponivel no painel para priorizacao futura.",
      quality: "Qualidade de execucao aproveita os mesmos agregados desta primeira entrega, preservando espaco para regras adicionais.",
      overlap: "Overlap medido por compartilhamento de medicos entre consultores na janela MAT 12m.",
      simulator: "O simulador desta etapa utiliza capacidade e cobertura agregadas para projetar gaps, sem alterar formulas originais futuras.",
      opportunities: "O backlog de oportunidades consolida gaps de cobertura e score por consultor.",
      governance: "A governanca expõe fontes, linhas, colunas, warnings e trilha de auditoria do pipeline.",
      channels: "Mix omnichannel derivado da distribuicao de canais identificados nas bases de visita.",
      master_data: "Master data mostra amostras de painel e qualidade estrutural das bases carregadas.",
      seasonality: "Tendencias e sazonalidade sao suportadas pela serie mensal consolidada de visitas."
    };

    const DEFAULT_STATE = {
      currentSection: null,
      currentPage: null,
      filters: {
        gd: "__all__",
        salesForce: "__all__",
        consultor: "__all__",
        window: "mat_12m"
      }
    };

    const APP_STATE = loadState();
    const sectionsById = Object.fromEntries(PAGE_REGISTRY.sections.map(section => [section.id, section]));

    function loadState() {
      try {
        const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
        return parsed ? { ...DEFAULT_STATE, ...parsed, filters: { ...DEFAULT_STATE.filters, ...(parsed.filters || {}) } } : structuredClone(DEFAULT_STATE);
      } catch (error) {
        return structuredClone(DEFAULT_STATE);
      }
    }

    function saveState() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(APP_STATE));
    }

    function formatValue(value, format) {
      const number = Number(value || 0);
      if (format === "percent") return `${number.toFixed(1)}%`;
      if (format === "integer") return `${Math.round(number)}`;
      return number.toFixed(1);
    }

    function safeDiv(numerator, denominator) {
      if (!denominator) return 0;
      return numerator / denominator;
    }

    function uniqueCount(rows, field) {
      return new Set(rows.map(row => String(row[field] || ""))).size;
    }

    function avg(rows, field) {
      if (!rows.length) return 0;
      return rows.reduce((total, row) => total + Number(row[field] || 0), 0) / rows.length;
    }

    function sum(rows, field) {
      return rows.reduce((total, row) => total + Number(row[field] || 0), 0);
    }

    function filterRows(rows) {
      return rows.filter(row => {
        if ((row.window || "") !== APP_STATE.filters.window) return false;
        if (APP_STATE.filters.gd !== "__all__" && String(row.gd || "") !== APP_STATE.filters.gd) return false;
        if (APP_STATE.filters.salesForce !== "__all__" && String(row.sales_force || "") !== APP_STATE.filters.salesForce) return false;
        if (APP_STATE.filters.consultor !== "__all__" && String(row.consultor || "") !== APP_STATE.filters.consultor) return false;
        return true;
      });
    }

    function filterGenericRows(rows) {
      return rows.filter(row => {
        if (APP_STATE.filters.gd !== "__all__" && String(row.gd || "") !== APP_STATE.filters.gd) return false;
        if (APP_STATE.filters.salesForce !== "__all__" && String(row.sales_force || "") !== APP_STATE.filters.salesForce) return false;
        if (APP_STATE.filters.consultor !== "__all__" && String(row.consultor || "") !== APP_STATE.filters.consultor) return false;
        return true;
      });
    }

    function computeAnalytics() {
      const rows = filterRows(APP_DATA.analytics.consultor_window || []);
      const overlapPairs = APP_DATA.analytics.overlap_pairs || [];
      const opportunityDoctors = filterGenericRows(APP_DATA.analytics.opportunity_doctors || []);
      const monthlySeries = APP_DATA.analytics.monthly_series || [];
      const specialtyFranchise = APP_DATA.analytics.specialty_franchise || [];

      const metrics = {
        score_geral: avg(rows, "score_geral"),
        visitas_total: sum(rows, "visitas_total"),
        visitas_f2f: sum(rows, "visitas_f2f"),
        dias_com_visita: sum(rows, "dias_com_visita"),
        medicos_visitados: sum(rows, "medicos_visitados"),
        medicos_painel: sum(rows, "medicos_painel"),
        medicos_mccp: sum(rows, "medicos_mccp"),
        medicos_cobertos_f2f: sum(rows, "medicos_cobertos_f2f"),
        medicos_cobertos_multi: sum(rows, "medicos_cobertos_multi"),
        medicos_mccp_cobertos_f2f: sum(rows, "medicos_mccp_cobertos_f2f"),
        visitas_por_dia: safeDiv(sum(rows, "visitas_total"), Math.max(sum(rows, "dias_com_visita"), 1)),
        pct_cobertura_f2f: safeDiv(sum(rows, "medicos_cobertos_f2f"), Math.max(sum(rows, "medicos_painel"), 1)) * 100,
        pct_cobertura_multi: safeDiv(sum(rows, "medicos_cobertos_multi"), Math.max(sum(rows, "medicos_painel"), 1)) * 100,
        pct_cobertura_mccp: safeDiv(sum(rows, "medicos_mccp_cobertos_f2f"), Math.max(sum(rows, "medicos_mccp"), 1)) * 100,
        dias_ausencia: sum(rows, "dias_ausencia"),
        pct_ausencia: safeDiv(sum(rows, "dias_ausencia"), Math.max(sum(rows, "dias_uteis_referencia"), 1)) * 100,
        score_territorial: avg(rows, "score_territorial"),
        pares_com_overlap: overlapPairs.length,
        medicos_compartilhados: overlapPairs.reduce((total, row) => total + Number(row.medicos_compartilhados || 0), 0),
        files_loaded: Number(APP_DATA.meta.files_loaded || 0),
        warnings_count: (APP_DATA.meta.warnings || []).length,
        specialty_count: (APP_DATA.analytics.top_specialties || []).length,
        pct_visitas_f2f: safeDiv(sum(rows, "visitas_f2f"), Math.max(sum(rows, "visitas_total"), 1)) * 100,
        capacidade_disponivel: Math.max(Math.round(sum(rows, "dias_uteis_referencia") - sum(rows, "dias_ausencia")), 0),
        gap_capacidade: Math.max(Math.round(sum(rows, "medicos_painel") - sum(rows, "medicos_cobertos_multi")), 0),
        medicos_sem_cobertura: opportunityDoctors.length,
        consultores_ativos: uniqueCount(rows, "consultor")
      };

      return {
        rows,
        metrics,
        overlapPairs,
        opportunityDoctors,
        monthlySeries,
        specialtyFranchise
      };
    }

    function sortRows(rows, metric, direction = "desc") {
      const multiplier = direction === "desc" ? -1 : 1;
      return [...rows].sort((a, b) => {
        const left = Number(a[metric] || 0);
        const right = Number(b[metric] || 0);
        return (left - right) * multiplier;
      });
    }

    function buildTableData(tableId, analytics) {
      const rows = analytics.rows;
      if (tableId === "consultor_ranking") {
        return {
          columns: ["consultor", "sales_force", "gd", "score_geral", "visitas_total", "pct_cobertura_mccp"],
          rows: sortRows(rows, "score_geral").slice(0, 100)
        };
      }
      if (tableId === "consultor_productivity") {
        return {
          columns: ["consultor", "sales_force", "gd", "visitas_total", "dias_com_visita", "visitas_por_dia"],
          rows: sortRows(rows, "visitas_por_dia").slice(0, 100)
        };
      }
      if (tableId === "consultor_coverage") {
        return {
          columns: ["consultor", "sales_force", "gd", "medicos_painel", "medicos_cobertos_multi", "pct_cobertura_mccp"],
          rows: sortRows(rows, "pct_cobertura_mccp").slice(0, 100)
        };
      }
      if (tableId === "consultor_territory") {
        return {
          columns: ["consultor", "sales_force", "gd", "cidades_visitadas", "ufs_visitadas", "score_territorial"],
          rows: sortRows(rows, "score_territorial").slice(0, 100)
        };
      }
      if (tableId === "consultor_capacity") {
        return {
          columns: ["consultor", "sales_force", "gd", "dias_ausencia", "pct_ausencia", "score_capacidade"],
          rows: sortRows(rows, "score_capacidade").slice(0, 100)
        };
      }
      if (tableId === "opportunity_doctors") {
        return {
          columns: ["consultor", "sales_force", "gd", "doctor_id", "doctor_name", "specialty_primary", "franchise"],
          rows: analytics.opportunityDoctors.slice(0, 200)
        };
      }
      if (tableId === "overlap_pairs") {
        return {
          columns: ["consultor_a", "consultor_b", "medicos_compartilhados"],
          rows: analytics.overlapPairs.slice(0, 100)
        };
      }
      if (tableId === "file_catalog") {
        return {
          columns: ["name", "kind", "rows", "separator", "encoding", "path"],
          rows: APP_DATA.analytics.file_catalog || []
        };
      }
      if (tableId === "audit_summary") {
        const rows = [];
        Object.entries(APP_DATA.audit || {}).forEach(([domain, values]) => {
          Object.entries(values || {}).forEach(([key, value]) => {
            rows.push({ domain, campo: key, valor: typeof value === "object" ? JSON.stringify(value) : String(value) });
          });
        });
        (APP_DATA.meta.warnings || []).forEach((warning, index) => rows.push({ domain: "warning", campo: `warning_${index + 1}`, valor: warning }));
        return {
          columns: ["domain", "campo", "valor"],
          rows
        };
      }
      if (tableId === "visit_sample") {
        return {
          columns: ["consultor", "sales_force", "gd", "doctor_id", "doctor_name", "visit_date", "channel"],
          rows: filterGenericRows(APP_DATA.analytics.visit_sample || []).slice(0, 200)
        };
      }
      if (tableId === "panel_sample") {
        return {
          columns: ["consultor", "sales_force", "gd", "doctor_id", "doctor_name", "specialty_primary", "franchise"],
          rows: filterGenericRows(APP_DATA.analytics.panel_sample || []).slice(0, 200)
        };
      }
      if (tableId === "absence_sample") {
        return {
          columns: ["consultor", "sales_force", "gd", "absence_date", "absence_type"],
          rows: filterGenericRows(APP_DATA.analytics.absence_sample || []).slice(0, 200)
        };
      }
      if (tableId === "specialty_franchise") {
        return {
          columns: ["franchise", "specialty_primary", "medicos_painel", "medicos_cobertos", "pct_cobertura"],
          rows: APP_DATA.analytics.specialty_franchise || []
        };
      }
      return { columns: [], rows: [] };
    }

    function labelForRow(row) {
      if (row.month) return row.month;
      if (row.label) return row.label;
      if (row.consultor) return row.consultor;
      if (row.consultor_a) return `${row.consultor_a} x ${row.consultor_b}`;
      if (row.name) return row.name;
      if (row.franchise) return `${row.franchise} / ${row.specialty_primary}`;
      return "Item";
    }

    function buildChartData(chartId, analytics) {
      if (chartId === "monthly_visits") {
        return (analytics.monthlySeries || []).map(row => ({ label: row.month, value: Number(row.visitas_total || 0) }));
      }
      if (chartId === "top_channels") {
        return (APP_DATA.analytics.top_channels || []).map(row => ({ label: row.label, value: Number(row.value || 0) }));
      }
      if (chartId === "top_specialties") {
        return (APP_DATA.analytics.top_specialties || []).map(row => ({ label: row.label, value: Number(row.value || 0) }));
      }
      if (chartId === "ranking_scores") {
        return sortRows(analytics.rows, "score_geral").slice(0, 8).map(row => ({ label: row.consultor, value: Number(row.score_geral || 0) }));
      }
      if (chartId === "coverage_distribution") {
        return sortRows(analytics.rows, "pct_cobertura_mccp").slice(0, 8).map(row => ({ label: row.consultor, value: Number(row.pct_cobertura_mccp || 0) }));
      }
      if (chartId === "territory_distribution") {
        return sortRows(analytics.rows, "ufs_visitadas").slice(0, 8).map(row => ({ label: row.consultor, value: Number(row.ufs_visitadas || 0) }));
      }
      if (chartId === "territory_scores") {
        return sortRows(analytics.rows, "score_territorial").slice(0, 8).map(row => ({ label: row.consultor, value: Number(row.score_territorial || 0) }));
      }
      if (chartId === "absence_distribution") {
        return sortRows(analytics.rows, "dias_ausencia").slice(0, 8).map(row => ({ label: row.consultor, value: Number(row.dias_ausencia || 0) }));
      }
      if (chartId === "overlap_pairs") {
        return (analytics.overlapPairs || []).slice(0, 8).map(row => ({ label: `${row.consultor_a} x ${row.consultor_b}`, value: Number(row.medicos_compartilhados || 0) }));
      }
      if (chartId === "specialty_franchise") {
        return (analytics.specialtyFranchise || []).slice(0, 8).map(row => ({ label: `${row.franchise} / ${row.specialty_primary}`, value: Number(row.pct_cobertura || 0) }));
      }
      if (chartId === "opportunity_distribution") {
        const counts = {};
        analytics.opportunityDoctors.forEach(row => {
          counts[row.consultor] = (counts[row.consultor] || 0) + 1;
        });
        return Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, 8);
      }
      if (chartId === "capacity_scenario") {
        return sortRows(analytics.rows, "score_capacidade").slice(0, 8).map(row => ({ label: row.consultor, value: Number(row.score_capacidade || 0) }));
      }
      if (chartId === "file_sizes") {
        return (APP_DATA.analytics.file_catalog || []).slice(0, 8).map(row => ({ label: row.name, value: Number(row.rows || 0) }));
      }
      if (chartId === "top_columns") {
        return (APP_DATA.analytics.file_catalog || []).slice(0, 8).map(row => ({ label: row.name, value: (row.columns || []).length }));
      }
      return [];
    }

    function renderBarChart(items) {
      if (!items.length) return `<div class="empty-state">Sem dados disponiveis para este grafico no filtro atual.</div>`;
      const width = 620;
      const height = 240;
      const leftPad = 56;
      const bottomPad = 34;
      const chartHeight = height - 30;
      const innerWidth = width - leftPad - 16;
      const maxValue = Math.max(...items.map(item => Number(item.value || 0)), 1);
      const barWidth = innerWidth / items.length;

      const bars = items.map((item, index) => {
        const value = Number(item.value || 0);
        const scaled = (value / maxValue) * (chartHeight - bottomPad);
        const x = leftPad + index * barWidth + 6;
        const y = chartHeight - scaled;
        const safeLabel = String(item.label || "").slice(0, 18);
        return `
          <rect x="${x}" y="${y}" width="${Math.max(barWidth - 12, 12)}" height="${scaled}" rx="6" fill="#1f5eff"></rect>
          <text x="${x + (Math.max(barWidth - 12, 12) / 2)}" y="${Math.min(y - 6, 16)}" text-anchor="middle" font-size="11" fill="#5f6f8c">${value.toFixed(0)}</text>
          <text x="${x + (Math.max(barWidth - 12, 12) / 2)}" y="${height - 10}" text-anchor="middle" font-size="10" fill="#5f6f8c">${safeLabel}</text>
        `;
      }).join("");

      return `
        <svg class="svg-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
          <line x1="${leftPad}" y1="${chartHeight}" x2="${width - 10}" y2="${chartHeight}" stroke="#d8e1ef" />
          <line x1="${leftPad}" y1="10" x2="${leftPad}" y2="${chartHeight}" stroke="#d8e1ef" />
          ${bars}
        </svg>
      `;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function exportRowsAsCsv(filename, rows, columns) {
      const header = columns.join(";");
      const body = rows.map(row => columns.map(column => `"${String(row[column] ?? "").replaceAll('"', '""')}"`).join(";")).join("\\n");
      const blob = new Blob([`${header}\\n${body}`], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    }

    function renderTable(block, analytics) {
      const table = buildTableData(block.table, analytics);
      if (!table.rows.length) {
        return `<div class="block-card"><h3>${block.title}</h3><div class="empty-state">Nenhum registro disponivel para esta tabela no filtro atual.</div></div>`;
      }
      const tableId = `table_${block.table}_${Math.random().toString(36).slice(2)}`;
      const header = table.columns.map(column => `<th>${escapeHtml(column)}</th>`).join("");
      const body = table.rows.map(row => `<tr>${table.columns.map(column => `<td>${escapeHtml(row[column])}</td>`).join("")}</tr>`).join("");
      setTimeout(() => {
        const button = document.querySelector(`[data-export-id="${tableId}"]`);
        if (button) {
          button.onclick = () => exportRowsAsCsv(`${block.table}.csv`, table.rows, table.columns);
        }
      }, 0);
      return `
        <div class="block-card">
          <div class="block-actions">
            <button class="ghost-btn" data-export-id="${tableId}">Exportar CSV</button>
          </div>
          <h3>${block.title}</h3>
          <div class="table-wrap">
            <table>
              <thead><tr>${header}</tr></thead>
              <tbody>${body}</tbody>
            </table>
          </div>
        </div>
      `;
    }

    function renderKpi(block, analytics) {
      return `
        <div class="kpi-card">
          <h3>${block.title}</h3>
          <p class="metric-caption">Filtro atual aplicado globalmente.</p>
          <span class="kpi-value">${formatValue(analytics.metrics[block.metric], block.format)}</span>
        </div>
      `;
    }

    function renderChart(block, analytics) {
      const items = buildChartData(block.chart, analytics);
      return `
        <div class="block-card">
          <h3>${block.title}</h3>
          ${renderBarChart(items)}
        </div>
      `;
    }

    function buildInsight(block, analytics) {
      const metrics = analytics.metrics;
      const snippets = [];
      if (metrics.pct_cobertura_mccp < 60) snippets.push("Cobertura MCCP abaixo de 60%, indicando prioridade de reforco.");
      if (metrics.pct_ausencia > 8) snippets.push("Ausencias acima do patamar de atencao na janela atual.");
      if (metrics.visitas_por_dia >= 8) snippets.push("Produtividade diaria em nivel forte para o filtro atual.");
      if (!snippets.length) snippets.push("Sem alertas criticos no recorte atual; use o ranking para priorizacao fina.");
      const reusable = (APP_DATA.analytics.insights || []).map(item => `<li><strong>${item.title}:</strong> ${item.message}</li>`).join("");
      return `
        <div class="block-card">
          <h3>${block.title}</h3>
          <div class="insight-chip">
            <strong>Leitura do recorte atual</strong>
            <div>${snippets.join(" ")}</div>
          </div>
          <ul>${reusable}</ul>
        </div>
      `;
    }

    function renderMethodology(block, page) {
      return `
        <div class="block-card">
          <h3>${block.title}</h3>
          <p>${METHOD_TEXT[block.domain] || "Metodologia em evolucao incremental."}</p>
          <p><strong>Pergunta de negocio:</strong> ${page.businessQuestion}</p>
          <p><strong>Decisao suportada:</strong> ${page.decisionSupported}</p>
          <p><strong>Janela ativa:</strong> ${APP_STATE.filters.window}</p>
        </div>
      `;
    }

    function renderHome(analytics) {
      const sectionCards = PAGE_REGISTRY.sections.map(section => `
        <div class="section-card" onclick="goToSection('${section.id}')">
          <div class="tag">${section.pages.length} paginas</div>
          <h3>${section.title}</h3>
          <p>${section.description}</p>
        </div>
      `).join("");

      const insightCards = (APP_DATA.analytics.insights || []).slice(0, 4).map(insight => `
        <div class="insight-chip">
          <strong>${insight.title}</strong>
          <div>${insight.message}</div>
        </div>
      `).join("");

      return `
        <div class="hero">
          <div class="hero-card">
            <h2>Portal Analitico Healthcheck</h2>
            <p>Estrutura offline, modular e escalavel para transformar CSVs locais em um portal analitico navegavel com Home, macrosecoes, subsecoes e paginas de decisao.</p>
            <p>Esta primeira versao ja roda com <strong>python main.py</strong>, gera <strong>payload.json</strong> e entrega um <strong>HTML self-contained</strong> pronto para compartilhar.</p>
            <div class="hero-meta">
              <span class="tag">${APP_DATA.meta.files_loaded} arquivos carregados</span>
              <span class="tag">${analytics.metrics.consultores_ativos} consultores no filtro</span>
              <span class="tag">Janela: ${APP_STATE.filters.window}</span>
              <span class="tag">Gerado em ${new Date(APP_DATA.meta.generated_at).toLocaleString()}</span>
            </div>
          </div>
          <div class="panel insight-stack">
            ${insightCards}
          </div>
        </div>

        <div class="kpi-grid">
          ${renderKpi({ title: "Score geral", metric: "score_geral", format: "number" }, analytics)}
          ${renderKpi({ title: "Cobertura MCCP", metric: "pct_cobertura_mccp", format: "percent" }, analytics)}
          ${renderKpi({ title: "Visitas totais", metric: "visitas_total", format: "integer" }, analytics)}
          ${renderKpi({ title: "Dias de ausencia", metric: "dias_ausencia", format: "integer" }, analytics)}
        </div>

        <div class="section-grid">${sectionCards}</div>
      `;
    }

    function renderSection(sectionId) {
      const section = sectionsById[sectionId];
      if (!section) return `<div class="empty-state">Secao nao encontrada.</div>`;
      const cards = section.pages.map(page => `
        <div class="page-card" onclick="goToPage('${page.pageId}')">
          <div class="tag">Subsecao</div>
          <h3>${page.title}</h3>
          <p>${page.businessQuestion}</p>
        </div>
      `).join("");
      return `
        <div class="page-header">
          <h2>${section.title}</h2>
          <p>${section.description}</p>
          <p><strong>Navegacao:</strong> Home &gt; ${section.title}</p>
        </div>
        <div class="page-grid">${cards}</div>
      `;
    }

    function renderPage(pageId, analytics) {
      const page = PAGE_REGISTRY.pages[pageId];
      if (!page) return `<div class="empty-state">Pagina nao encontrada.</div>`;
      const kpis = page.blocks.filter(block => block.type === "kpi").map(block => renderKpi(block, analytics)).join("");
      const blocks = page.blocks.filter(block => block.type !== "kpi").map(block => {
        if (block.type === "chart") return renderChart(block, analytics);
        if (block.type === "table") return renderTable(block, analytics);
        if (block.type === "insight") return buildInsight(block, analytics);
        if (block.type === "methodology") return renderMethodology(block, page);
        return "";
      }).join("");
      return `
        <div class="page-header">
          <h2>${page.title}</h2>
          <p><strong>Pergunta:</strong> ${page.businessQuestion}</p>
          <p><strong>Decisao suportada:</strong> ${page.decisionSupported}</p>
        </div>
        <div class="kpi-grid">${kpis}</div>
        <div class="block-grid">${blocks}</div>
      `;
    }

    function currentBreadcrumb() {
      if (APP_STATE.currentPage) {
        const page = PAGE_REGISTRY.pages[APP_STATE.currentPage];
        return `Home &gt; ${page.section} &gt; ${page.subsection}`;
      }
      if (APP_STATE.currentSection) {
        const section = sectionsById[APP_STATE.currentSection];
        return `Home &gt; ${section.title}`;
      }
      return "Home";
    }

    function buildOptionList(items, selected, label) {
      const options = [`<option value="__all__">${label}</option>`];
      items.forEach(item => {
        options.push(`<option value="${escapeHtml(item)}" ${item === selected ? "selected" : ""}>${escapeHtml(item)}</option>`);
      });
      return options.join("");
    }

    function render() {
      saveState();
      const analytics = computeAnalytics();

      document.getElementById("breadcrumb").innerHTML = currentBreadcrumb();
      document.getElementById("filter-gd").innerHTML = buildOptionList(APP_DATA.dimensions.gds || [], APP_STATE.filters.gd, "Todos os GDs");
      document.getElementById("filter-sales-force").innerHTML = buildOptionList(APP_DATA.dimensions.sales_forces || [], APP_STATE.filters.salesForce, "Todas as Sales Forces");
      document.getElementById("filter-consultor").innerHTML = buildOptionList(APP_DATA.dimensions.consultores || [], APP_STATE.filters.consultor, "Todos os consultores");
      document.getElementById("filter-window").innerHTML = (APP_DATA.dimensions.windows || []).map(item => `<option value="${item.id}" ${item.id === APP_STATE.filters.window ? "selected" : ""}>${item.label}</option>`).join("");

      const content = document.getElementById("content");
      if (APP_STATE.currentPage) {
        content.innerHTML = renderPage(APP_STATE.currentPage, analytics);
      } else if (APP_STATE.currentSection) {
        content.innerHTML = renderSection(APP_STATE.currentSection);
      } else {
        content.innerHTML = renderHome(analytics);
      }
    }

    function goToHome() {
      APP_STATE.currentSection = null;
      APP_STATE.currentPage = null;
      render();
      location.hash = "#home";
    }

    function goToSection(sectionId) {
      APP_STATE.currentSection = sectionId;
      APP_STATE.currentPage = null;
      render();
      location.hash = `#section/${sectionId}`;
    }

    function goToPage(pageId) {
      const page = PAGE_REGISTRY.pages[pageId];
      APP_STATE.currentSection = page.sectionId;
      APP_STATE.currentPage = pageId;
      render();
      location.hash = `#page/${pageId}`;
    }

    function applyRoute() {
      const hash = location.hash.replace(/^#/, "");
      if (!hash || hash === "home") {
        APP_STATE.currentSection = null;
        APP_STATE.currentPage = null;
      } else if (hash.startsWith("section/")) {
        APP_STATE.currentSection = hash.split("/")[1] || null;
        APP_STATE.currentPage = null;
      } else if (hash.startsWith("page/")) {
        const pageId = hash.split("/")[1] || null;
        const page = PAGE_REGISTRY.pages[pageId];
        APP_STATE.currentPage = pageId;
        APP_STATE.currentSection = page ? page.sectionId : null;
      }
      render();
    }

    function resetFilters() {
      APP_STATE.filters = { ...DEFAULT_STATE.filters };
      render();
    }

    function bindEvents() {
      document.getElementById("filter-gd").addEventListener("change", event => {
        APP_STATE.filters.gd = event.target.value;
        render();
      });
      document.getElementById("filter-sales-force").addEventListener("change", event => {
        APP_STATE.filters.salesForce = event.target.value;
        render();
      });
      document.getElementById("filter-consultor").addEventListener("change", event => {
        APP_STATE.filters.consultor = event.target.value;
        render();
      });
      document.getElementById("filter-window").addEventListener("change", event => {
        APP_STATE.filters.window = event.target.value;
        render();
      });
      document.getElementById("go-home").addEventListener("click", goToHome);
      document.getElementById("reset-filters").addEventListener("click", resetFilters);
      document.getElementById("download-payload").addEventListener("click", () => {
        const blob = new Blob([JSON.stringify(APP_DATA, null, 2)], { type: "application/json;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "payload.json";
        anchor.click();
        URL.revokeObjectURL(url);
      });
      window.addEventListener("hashchange", applyRoute);
    }

    window.goToHome = goToHome;
    window.goToSection = goToSection;
    window.goToPage = goToPage;

    bindEvents();
    applyRoute();
    """
    return template.replace("__PAYLOAD__", payload_json).replace("__REGISTRY__", registry_json)


def gerar_html(payload: dict, output_path: Path) -> Path:
    registry = build_page_registry()
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portal Analitico - Healthcheck Operacional</title>
  <style>{_build_css()}</style>
</head>
<body>
  <div class="app-shell">
    <div class="topbar">
      <div class="brand">
        <h1>Portal Analitico Healthcheck</h1>
        <p>HTML self-contained para rodar offline a partir das bases CSV locais.</p>
      </div>
      <div class="toolbar">
        <div class="filter-group">
          <label>GD</label>
          <select id="filter-gd"></select>
        </div>
        <div class="filter-group">
          <label>Sales Force</label>
          <select id="filter-sales-force"></select>
        </div>
        <div class="filter-group">
          <label>Consultor</label>
          <select id="filter-consultor"></select>
        </div>
        <div class="filter-group">
          <label>Janela</label>
          <select id="filter-window"></select>
        </div>
        <button class="ghost-btn" id="go-home">Home</button>
        <button class="ghost-btn" id="reset-filters">Resetar filtros</button>
        <button class="primary-btn" id="download-payload">Baixar payload</button>
      </div>
    </div>

    <div class="breadcrumbs" id="breadcrumb"></div>
    <main id="content"></main>
    <div class="footer-note">Portal gerado offline em arquivo unico. Estrutura pronta para expansao incremental para novas paginas e indicadores.</div>
  </div>

  <script>{_build_js(payload, registry)}</script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
