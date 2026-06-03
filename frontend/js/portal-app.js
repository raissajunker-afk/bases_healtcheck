/* Portal Healthcheck — self-contained, offline. Dados em PAYLOAD_B64 (gzip). */
(function () {
  "use strict";

  const SECTIONS = __SECTIONS_JSON__;
  let PAYLOAD = null;

  const APP_STATE = {
    view: "home",
    sectionId: null,
    pageId: null,
    filters: { gd: "__all__", salesForce: "__all__", consultor: "__all__", janela: "mat" },
  };

  async function decompressPayload(b64) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const stream = new Response(
      new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))
    );
    const text = await stream.text();
    return JSON.parse(text);
  }

  function fmtNum(v, dec) {
    if (v == null || v === "" || Number.isNaN(v)) return "—";
    const n = Number(v);
    if (dec === 0) return Math.round(n).toLocaleString("pt-BR");
    return n.toLocaleString("pt-BR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }

  function fmtPct(v) {
    if (v == null || Number.isNaN(v)) return "—";
    return fmtNum(v, 1) + "%";
  }

  function kpiClass(val, good, warn) {
    if (val == null || good == null) return "";
    if (val >= good) return "good";
    if (warn != null && val >= warn) return "warn";
    return "bad";
  }

  function suffixJanela() {
    const j = APP_STATE.filters.janela;
    if (j === "mat") return "";
    if (j === "3m") return "_3m";
    if (j === "1m") return "_1m";
    if (j === "parcial") return "_parcial";
    return "";
  }

  function fieldFor(base) {
    const s = suffixJanela();
    if (!s) return base;
    const alt = base + s;
    return alt;
  }

  function getConsultores() {
    let list = (PAYLOAD.consultores || []).filter((c) => !c.afastado);
    const f = APP_STATE.filters;
    if (f.gd !== "__all__") list = list.filter((c) => (c.gd_name || c.gd_code) === f.gd);
    if (f.salesForce !== "__all__") list = list.filter((c) => c.sales_force === f.salesForce);
    if (f.consultor !== "__all__") list = list.filter((c) => c.ISID === f.consultor);
    return list;
  }

  function aggTeamMetric(getter) {
    const cs = getConsultores();
    if (!cs.length) return null;
    const vals = cs.map(getter).filter((v) => v != null && !Number.isNaN(v));
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  function exportCsv(filename, rows, columns) {
    const sep = ";";
    const head = columns.map((c) => c.label).join(sep);
    const body = rows
      .map((r) =>
        columns
          .map((c) => {
            let v = r[c.key];
            if (v == null) v = "";
            v = String(v).replace(/"/g, '""');
            if (String(v).includes(sep) || String(v).includes("\n")) v = '"' + v + '"';
            return v;
          })
          .join(sep)
      )
      .join("\n");
    const blob = new Blob(["\ufeff" + head + "\n" + body], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function renderKpis(items) {
    return (
      '<div class="kpi-row">' +
      items
        .map(
          (k) =>
            '<div class="kpi ' +
            (k.cls || "") +
            '"><div class="val">' +
            k.val +
            '</div><div class="lbl">' +
            k.lbl +
            "</div></div>"
        )
        .join("") +
      "</div>"
    );
  }

  function renderBarChart(series, valueKey, labelKey) {
    if (!series || !series.length)
      return '<p style="color:#888;font-size:12px">Sem dados para o filtro atual.</p>';
    const max = Math.max(...series.map((x) => Number(x[valueKey]) || 0), 1);
    return (
      '<div class="chart-bars">' +
      series
        .map((x) => {
          const v = Number(x[valueKey]) || 0;
          const h = Math.round((v / max) * 140);
          const lbl = (x[labelKey] || "").toString().slice(0, 8);
          return (
            '<div class="bar-wrap"><div class="bar" style="height:' +
            h +
            'px" title="' +
            lbl +
            ": " +
            v +
            '"></div><div class="bar-lbl">' +
            lbl +
            "</div></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderTable(columns, rows, tableId) {
    return (
      '<div style="overflow-x:auto"><table class="data" id="' +
      tableId +
      '"><thead><tr>' +
      columns.map((c) => "<th>" + c.label + "</th>").join("") +
      "</tr></thead><tbody>" +
      rows
        .map(
          (r) =>
            "<tr>" +
            columns
              .map((c) => {
                const v = r[c.key];
                const cls = c.num ? ' class="num"' : "";
                return "<td" + cls + ">" + (c.fmt ? c.fmt(v, r) : v ?? "—") + "</td>";
              })
              .join("") +
            "</tr>"
        )
        .join("") +
      "</tbody></table></div>"
    );
  }

  const BLOCKS = {
    kpi_consultores() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([
        { val: fmtNum(k.n_consultores, 0), lbl: "Consultores ativos" },
        { val: fmtNum(k.n_sf, 0), lbl: "Sales Forces" },
        { val: fmtNum(k.n_gd, 0), lbl: "GDs" },
      ]);
    },
    kpi_painel() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([
        { val: fmtNum(k.painel_total_time, 0), lbl: "Médicos no painel (time)" },
        { val: fmtNum(k.painel_medio, 1), lbl: "Painel médio / consultor" },
        { val: fmtNum(k.painel_mediano, 0), lbl: "Painel mediano" },
      ]);
    },
    kpi_vis_dia() {
      const k = PAYLOAD.kpis || {};
      const med = aggTeamMetric((c) => c[fieldFor("vis_dia_media")] ?? c.vis_dia_media);
      return renderKpis([
        {
          val: fmtNum(med != null ? med : k.vis_dia_media, 2),
          lbl: "Visitas/dia (média filtrada)",
          cls: kpiClass(med != null ? med : k.vis_dia_media, 5, 4),
        },
        { val: fmtNum(k.vis_dia_mediana, 2), lbl: "Mediana time" },
        { val: fmtNum(k.vis_total_12m, 0), lbl: "Visitas totais MAT" },
      ]);
    },
    kpi_cobertura() {
      const pct = aggTeamMetric((c) => c[fieldFor("pctCoberturaF2F")] ?? c.pctCoberturaF2F);
      const pctM = aggTeamMetric((c) => c[fieldFor("pctCoberturaMulti")] ?? c.pctCoberturaMulti);
      return renderKpis([
        { val: fmtPct(pct), lbl: "Cobertura F2F", cls: kpiClass(pct, 80, 60) },
        { val: fmtPct(pctM), lbl: "Cobertura multicanal", cls: kpiClass(pctM, 85, 70) },
      ]);
    },
    kpi_mccp() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([
        {
          val: fmtPct(k.mccp_pct_cumprido_team),
          lbl: "MCCP % cumprido (time)",
          cls: kpiClass(k.mccp_pct_cumprido_team, 80, 50),
        },
        { val: fmtNum(k.mccp_freq_media_tri_team, 2), lbl: "Freq. média tri MCCP" },
        { val: fmtPct(k.pct_dentro_mccp_team), lbl: "% visitas dentro MCCP" },
      ]);
    },
    kpi_ausencia() {
      const pct = aggTeamMetric((c) => c[fieldFor("pct_ausencia")] ?? c.pct_ausencia);
      const k = PAYLOAD.kpis || {};
      return renderKpis([
        { val: fmtPct(pct != null ? pct : k.pct_ausencia_media), lbl: "% ausência", cls: kpiClass(100 - (pct || 0), 70, 50) },
        { val: fmtNum(k.dias_trabalhados_mes_medio, 1), lbl: "Dias trabalhados/mês" },
      ]);
    },
    kpi_overlap() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtPct(k.overlap_intra_medio), lbl: "Overlap intra médio" }]);
    },
    kpi_vis_total() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.vis_total_12m, 0), lbl: "Visitas MAT" }]);
    },
    kpi_mccp_cumprido() {
      return BLOCKS.kpi_mccp();
    },
    kpi_mccp_freq() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.mccp_freq_media_tri_team, 2), lbl: "Frequência MCCP tri" }]);
    },
    kpi_pct_dentro_mccp() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtPct(k.pct_dentro_mccp_team), lbl: "% dentro MCCP" }]);
    },
    kpi_cobertura_f2f() {
      return BLOCKS.kpi_cobertura();
    },
    kpi_cobertura_multi() {
      const pctM = aggTeamMetric((c) => c[fieldFor("pctCoberturaMulti")] ?? c.pctCoberturaMulti);
      return renderKpis([{ val: fmtPct(pctM), lbl: "Cobertura multicanal" }]);
    },
    kpi_fora_mccp() {
      const cs = getConsultores();
      const avg = cs.length ? cs.reduce((a, c) => a + (c.pct_fora_mccp || 0), 0) / cs.length : null;
      return renderKpis([{ val: fmtPct(avg), lbl: "% visitas fora MCCP (média)" }]);
    },
    kpi_turnover() {
      const flagged = getConsultores().filter((c) => c.turnover_flag).length;
      return renderKpis([{ val: fmtNum(flagged, 0), lbl: "Consultores com turnover alto (3m)" }]);
    },
    kpi_freq_medico() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.freq_medico_mes_medio, 2), lbl: "Freq. médico/mês" }]);
    },
    kpi_medicos_unicos() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.medicos_unicos_mes_consultor_medio, 1), lbl: "Médicos únicos/mês (média)" }]);
    },
    kpi_tipo_setor() {
      const cs = getConsultores();
      const loc = cs.filter((c) => c.tipo_setor === "local").length;
      const via = cs.filter((c) => (c.tipo_setor || "").includes("viagem")).length;
      return renderKpis([
        { val: fmtNum(loc, 0), lbl: "Setor local" },
        { val: fmtNum(via, 0), lbl: "Com viagem" },
      ]);
    },
    kpi_viagem() {
      const cs = getConsultores();
      const v = cs.reduce((a, c) => a + (c.viagem_mes || 0), 0) / Math.max(cs.length, 1);
      return renderKpis([{ val: fmtNum(v, 1), lbl: "Dias viagem/mês (média)" }]);
    },
    kpi_brickagem() {
      const n = getConsultores().filter((c) => c.flag_brickagem_subutilizada).length;
      return renderKpis([{ val: fmtNum(n, 0), lbl: "Flags brickagem subutilizada" }]);
    },
    kpi_uf_sede() {
      const pct = aggTeamMetric((c) => c[fieldFor("pct_visitas_uf_sede")] ?? c.pct_visitas_uf_sede);
      return renderKpis([{ val: fmtPct(pct), lbl: "% visitas na UF sede" }]);
    },
    kpi_score_territorio() {
      const avg = aggTeamMetric((c) => c.score_territorio);
      return renderKpis([{ val: fmtNum(avg, 1), lbl: "Score território médio" }]);
    },
    kpi_capacidade() {
      const avg = aggTeamMetric((c) => c.capacidade_dias_ano);
      return renderKpis([{ val: fmtNum(avg, 0), lbl: "Capacidade dias/ano" }]);
    },
    kpi_gap_capacidade() {
      const avg = aggTeamMetric((c) => c.gap_capacidade_mes);
      return renderKpis([{ val: fmtNum(avg, 1), lbl: "Gap capacidade/mês" }]);
    },
    kpi_meta_painel() {
      const m = (PAYLOAD.meta || {}).meta_painel_default || (PAYLOAD.kpis || {}).meta_painel || 120;
      return renderKpis([{ val: fmtNum(m, 0), lbl: "Meta painel" }]);
    },
    kpi_meta_vis_dia() {
      const m = (PAYLOAD.meta || {}).meta_visitas_dia_default || (PAYLOAD.kpis || {}).meta_visitas_dia || 6;
      return renderKpis([{ val: fmtNum(m, 1), lbl: "Meta visitas/dia" }]);
    },
    kpi_mat_3m() {
      const cs = getConsultores();
      const v3 = cs.reduce((a, c) => a + (c.vis_dia_3m || 0), 0) / Math.max(cs.length, 1);
      const vm = cs.reduce((a, c) => a + (c.vis_dia_media || 0), 0) / Math.max(cs.length, 1);
      return renderKpis([
        { val: fmtNum(vm, 2), lbl: "Vis/dia MAT" },
        { val: fmtNum(v3, 2), lbl: "Vis/dia 3m" },
      ]);
    },
    kpi_mat_1m() {
      const cs = getConsultores();
      const v1 = cs.reduce((a, c) => a + (c.vis_dia_1m || 0), 0) / Math.max(cs.length, 1);
      return renderKpis([{ val: fmtNum(v1, 2), lbl: "Vis/dia último mês" }]);
    },
    kpi_painel_mediano() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.painel_mediano, 0), lbl: "Painel mediano" }]);
    },
    kpi_vis_dia_mediana() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.vis_dia_mediana, 2), lbl: "Vis/dia mediana" }]);
    },
    kpi_shared() {
      const n = (PAYLOAD.pares_overlap || []).length;
      return renderKpis([{ val: fmtNum(n, 0), lbl: "Pares com overlap" }]);
    },
    kpi_gap_f2f_multi() {
      const cs = getConsultores();
      let gap = 0;
      cs.forEach((c) => {
        const m = c.pctCoberturaMulti || 0;
        const f = c.pctCoberturaF2F || 0;
        if (m - f > 15) gap++;
      });
      return renderKpis([{ val: fmtNum(gap, 0), lbl: "Consultores com gap multi−F2F >15pp" }]);
    },
    kpi_especialidade_placeholder() {
      return '<div class="insight">Configure <code>bases/franquias_especialidades.csv</code> para índices IAEF/ICEF. Especialidades operacionais estão em Qualidade de Execução.</div>';
    },
    kpi_treinamento() {
      const v = aggTeamMetric((c) => c.treinamento_mes);
      return renderKpis([{ val: fmtNum(v, 1), lbl: "Dias treinamento/mês" }]);
    },
    kpi_congressos() {
      const v = aggTeamMetric((c) => c.congressos_mes);
      return renderKpis([{ val: fmtNum(v, 1), lbl: "Dias congressos/mês" }]);
    },
    kpi_pessoais() {
      const v = aggTeamMetric((c) => c.pessoais_mes);
      return renderKpis([{ val: fmtNum(v, 1), lbl: "Ausência pessoal/mês" }]);
    },
    kpi_dias_trabalhados() {
      const k = PAYLOAD.kpis || {};
      return renderKpis([{ val: fmtNum(k.dias_trabalhados_mes_medio, 1), lbl: "Dias trabalhados/mês" }]);
    },
    chart_series_team() {
      const s = (PAYLOAD.series_team || {}).visitas || [];
      const filtered = s.slice(-12);
      return renderBarChart(
        filtered.map((x) => ({ mes: x.mes || x.ym || x.label, v: x.valor ?? x.visitas ?? x.v })),
        "v",
        "mes"
      );
    },
    chart_series_visitas() {
      return BLOCKS.chart_series_team();
    },
    chart_ausencia() {
      const s = (PAYLOAD.series_team || {}).ausencia || [];
      return renderBarChart(
        s.slice(-12).map((x) => ({ mes: x.mes || x.ym, v: x.valor ?? x.pct ?? x.v })),
        "v",
        "mes"
      );
    },
    chart_freq_dist() {
      const fd = PAYLOAD.freq_dist_mccp || {};
      const series = Object.entries(fd).map(([k, v]) => ({ mes: k, v: Number(v) }));
      return renderBarChart(series, "v", "mes");
    },
    table_consultores() {
      const cols = [
        { key: "nome", label: "Consultor" },
        { key: "sales_force", label: "SF" },
        { key: "painel_size", label: "Painel", num: true, fmt: (v) => fmtNum(v, 0) },
        { key: "vis_dia_media", label: "Vis/dia", num: true, fmt: (v) => fmtNum(v, 2) },
        { key: "pctCoberturaF2F", label: "Cob F2F%", num: true, fmt: (v) => fmtPct(v) },
        { key: "mccp_pct_cumprido", label: "MCCP%", num: true, fmt: (v) => fmtPct(v) },
        { key: "pct_ausencia", label: "Ausência%", num: true, fmt: (v) => fmtPct(v) },
      ];
      const rows = getConsultores().slice(0, 100);
      const tid = "tbl-c-" + Date.now();
      setTimeout(() => {
        const btn = document.getElementById("exp-" + tid);
        if (btn)
          btn.onclick = () => exportCsv("consultores.csv", rows, cols);
      }, 0);
      return (
        renderTable(cols, rows, tid) +
        '<div class="block-actions"><button class="btn btn-outline" id="exp-' +
        tid +
        '">Download CSV</button></div>'
      );
    },
    table_sf() {
      const rows = (PAYLOAD.sales_forces || []).map((sf) => ({
        nome: sf.nome || sf.sales_force || sf.sf,
        n: sf.n_consultores || sf.consultores,
        painel: sf.painel_medio || sf.painel_media,
        vis: sf.vis_dia_media,
        cob: sf.pct_cobertura_f2f || sf.cobertura_f2f,
      }));
      const cols = [
        { key: "nome", label: "Sales Force" },
        { key: "n", label: "REPs", num: true },
        { key: "painel", label: "Painel médio", num: true, fmt: (v) => fmtNum(v, 1) },
        { key: "vis", label: "Vis/dia", num: true, fmt: (v) => fmtNum(v, 2) },
        { key: "cob", label: "Cobertura", num: true, fmt: (v) => fmtPct(v) },
      ];
      return renderTable(cols, rows, "tbl-sf");
    },
    table_gd() {
      const rows = (PAYLOAD.gds || []).map((g) => ({
        nome: g.nome || g.gd_name || g.gd,
        n: g.n_consultores,
        vis: g.vis_dia_media,
      }));
      const cols = [
        { key: "nome", label: "GD" },
        { key: "n", label: "REPs", num: true },
        { key: "vis", label: "Vis/dia média", num: true, fmt: (v) => fmtNum(v, 2) },
      ];
      return renderTable(cols, rows, "tbl-gd");
    },
    table_overlap() {
      const rows = (PAYLOAD.pares_overlap || []).slice(0, 40);
      const cols = [
        { key: "consultor_a", label: "Consultor A" },
        { key: "consultor_b", label: "Consultor B" },
        { key: "shared", label: "Compartilhados", num: true, fmt: (v, r) => fmtNum(v ?? r.n_shared ?? r.medicos, 0) },
      ];
      const tid = "tbl-ov-" + Date.now();
      setTimeout(() => {
        const btn = document.getElementById("exp-" + tid);
        if (btn) btn.onclick = () => exportCsv("overlap.csv", rows, cols);
      }, 0);
      return (
        renderTable(cols, rows, tid) +
        '<div class="block-actions"><button class="btn btn-outline" id="exp-' +
        tid +
        '">Download CSV</button></div>'
      );
    },
    table_pares() {
      return BLOCKS.table_overlap();
    },
    table_nao_visitados() {
      const cs = getConsultores()
        .filter((c) => (c.pctCoberturaF2F || 0) < 70)
        .sort((a, b) => (a.pctCoberturaF2F || 0) - (b.pctCoberturaF2F || 0))
        .slice(0, 30)
        .map((c) => ({
          consultor: c.nome,
          painel: c.painel_size,
          cob: c.pctCoberturaF2F,
          mccp: c.mccp_pct_cumprido,
          gap: (c.painel_size || 0) - (c.mdmsCobertosF2F || 0),
        }));
      const cols = [
        { key: "consultor", label: "Consultor" },
        { key: "painel", label: "Painel", num: true },
        { key: "cob", label: "Cob F2F%", num: true, fmt: (v) => fmtPct(v) },
        { key: "mccp", label: "MCCP%", num: true, fmt: (v) => fmtPct(v) },
        { key: "gap", label: "Gap est.", num: true },
      ];
      return renderTable(cols, cs, "tbl-nv");
    },
    ranking_vis_dia() {
      const rows = getConsultores()
        .sort((a, b) => (b.vis_dia_media || 0) - (a.vis_dia_media || 0))
        .slice(0, 15)
        .map((c, i) => ({ rank: i + 1, nome: c.nome, val: c.vis_dia_media }));
      const cols = [
        { key: "rank", label: "#", num: true },
        { key: "nome", label: "Consultor" },
        { key: "val", label: "Vis/dia", num: true, fmt: (v) => fmtNum(v, 2) },
      ];
      return renderTable(cols, rows, "rk-vd");
    },
    ranking_top_vis() {
      return BLOCKS.ranking_vis_dia();
    },
    ranking_bottom_vis() {
      const rows = getConsultores()
        .sort((a, b) => (a.vis_dia_media || 0) - (b.vis_dia_media || 0))
        .slice(0, 15)
        .map((c, i) => ({ rank: i + 1, nome: c.nome, val: c.vis_dia_media }));
      const cols = [
        { key: "rank", label: "#", num: true },
        { key: "nome", label: "Consultor" },
        { key: "val", label: "Vis/dia", num: true, fmt: (v) => fmtNum(v, 2) },
      ];
      return renderTable(cols, rows, "rk-bv");
    },
    ranking_top_mccp() {
      const rows = getConsultores()
        .sort((a, b) => (b.mccp_pct_cumprido || 0) - (a.mccp_pct_cumprido || 0))
        .slice(0, 15)
        .map((c, i) => ({ rank: i + 1, nome: c.nome, val: c.mccp_pct_cumprido }));
      const cols = [
        { key: "rank", label: "#", num: true },
        { key: "nome", label: "Consultor" },
        { key: "val", label: "MCCP%", num: true, fmt: (v) => fmtPct(v) },
      ];
      return renderTable(cols, rows, "rk-mccp-t");
    },
    ranking_bottom_mccp() {
      const rows = getConsultores()
        .sort((a, b) => (a.mccp_pct_cumprido || 0) - (b.mccp_pct_cumprido || 0))
        .slice(0, 15)
        .map((c, i) => ({ rank: i + 1, nome: c.nome, val: c.mccp_pct_cumprido }));
      const cols = [
        { key: "rank", label: "#", num: true },
        { key: "nome", label: "Consultor" },
        { key: "val", label: "MCCP%", num: true, fmt: (v) => fmtPct(v) },
      ];
      return renderTable(cols, rows, "rk-mccp-b");
    },
    ranking_cobertura() {
      const rows = getConsultores()
        .sort((a, b) => (b.pctCoberturaF2F || 0) - (a.pctCoberturaF2F || 0))
        .slice(0, 15)
        .map((c, i) => ({ rank: i + 1, nome: c.nome, val: c.pctCoberturaF2F }));
      const cols = [
        { key: "rank", label: "#", num: true },
        { key: "nome", label: "Consultor" },
        { key: "val", label: "Cob F2F%", num: true, fmt: (v) => fmtPct(v) },
      ];
      return renderTable(cols, rows, "rk-cob");
    },
    ranking_gap_cobertura() {
      const rows = getConsultores()
        .map((c) => ({
          nome: c.nome,
          gap: (c.painel_size || 0) * (1 - (c.pctCoberturaF2F || 0) / 100),
          cob: c.pctCoberturaF2F,
        }))
        .sort((a, b) => b.gap - a.gap)
        .slice(0, 15);
      const cols = [
        { key: "nome", label: "Consultor" },
        { key: "cob", label: "Cob%", num: true, fmt: (v) => fmtPct(v) },
        { key: "gap", label: "Gap médicos est.", num: true, fmt: (v) => fmtNum(v, 0) },
      ];
      return renderTable(cols, rows, "rk-gap");
    },
    ranking_sf() {
      return BLOCKS.table_sf();
    },
    ranking_score() {
      const rows = getConsultores()
        .filter((c) => c.score_territorio != null)
        .sort((a, b) => (a.score_territorio || 0) - (b.score_territorio || 0))
        .slice(0, 15);
      const cols = [
        { key: "nome", label: "Consultor" },
        { key: "score_territorio", label: "Score", num: true },
        { key: "score_territorio_status", label: "Status" },
      ];
      return renderTable(cols, rows, "rk-sc");
    },
    insight_executive() {
      const k = PAYLOAD.kpis || {};
      const lines = [];
      if (k.mccp_pct_cumprido_team < 60)
        lines.push("MCCP do time abaixo de 60% — priorizar cumprimento do plano.");
      if (k.pct_ausencia_media > 25)
        lines.push("Ausência média acima de 25% — revisar capacidade disponível.");
      if ((k.overlap_intra_medio || 0) > 15)
        lines.push("Overlap intra elevado — avaliar redistribuição de painel.");
      if (!lines.length) lines.push("Indicadores dentro de faixas típicas para o recorte atual.");
      return '<div class="insight">' + lines.join("<br>") + "</div>";
    },
    insight_alertas() {
      return BLOCKS.insight_executive().replace('class="insight"', 'class="insight alert"');
    },
    insight_produtividade() {
      const med = aggTeamMetric((c) => c.vis_dia_media);
      const meta = (PAYLOAD.kpis || {}).meta_visitas_dia || 6;
      const txt =
        med != null && med < meta
          ? "Produtividade média abaixo da meta de " + meta + " visitas/dia."
          : "Produtividade média alinhada ou acima da meta de visitas/dia.";
      return '<div class="insight">' + txt + "</div>";
    },
    insight_cobertura() {
      const pct = aggTeamMetric((c) => c.pctCoberturaF2F);
      const txt =
        pct != null && pct < 70
          ? "Cobertura F2F média abaixo de 70% — foco em médicos descobertos no MCCP."
          : "Cobertura F2F em patamar aceitável para o recorte.";
      return '<div class="insight">' + txt + "</div>";
    },
    insight_mccp() {
      return BLOCKS.insight_executive();
    },
    insight_oportunidades() {
      const n = getConsultores().filter((c) => (c.pctCoberturaF2F || 0) < 60).length;
      return (
        '<div class="insight alert">' +
        n +
        " consultor(es) com cobertura F2F &lt;60%. Ver seção Cobertura e Plano de Ação.</div>"
      );
    },
    insight_tendencia() {
      return '<div class="insight">Use a série temporal e compare janelas MAT vs 3m nos filtros globais.</div>';
    },
    insight_performance() {
      return BLOCKS.insight_produtividade();
    },
    insight_canal() {
      const f = aggTeamMetric((c) => c.pctCoberturaF2F);
      const m = aggTeamMetric((c) => c.pctCoberturaMulti);
      const d = m != null && f != null ? m - f : 0;
      return (
        '<div class="insight">Gap médio multicanal−F2F: ' +
        fmtNum(d, 1) +
        " pp. Remoto complementa mas não substitui F2F em decisores.</div>"
      );
    },
    methodology() {
      const m = PAYLOAD.meta || {};
      return (
        '<div class="insight"><strong>Metodologia</strong><br>Janela: ' +
        (m.janela_label || "—") +
        "<br>Snapshot painel: " +
        (m.snapshot_painel || "—") +
        "<br>Ciclo MCCP: " +
        (m.ciclo_mccp || "—") +
        "<br>SFs excluídas: " +
        ((m.sfs_excluidas || []).join(", ") || "—") +
        "<br><em>KPIs calculados por processar.py — não alterados neste portal.</em></div>"
      );
    },
    glossary() {
      return (
        '<div class="insight"><strong>Glossário resumido</strong><br>' +
        "IPA/Cobertura F2F: % médicos alvo visitados presencialmente.<br>" +
        "MCCP: cumprimento do plano de contatos por ciclo.<br>" +
        "Overlap intra: médicos compartilhados no mesmo time.<br>" +
        "Para simulador completo e tabelas detalhadas, use o HTML legado (opcional).</div>"
      );
    },
    meta_fontes() {
      const m = PAYLOAD.meta || {};
      return (
        '<div class="insight"><strong>Fontes</strong><br>estrutura.xlsx, relatorio_visitas_24/25/26.csv, ausencias, relatorio_painel, relatorio_mccp<br>Gerado: ' +
        (m.gerado_em || "—") +
        "</div>"
      );
    },
    meta_exclusoes() {
      const m = PAYLOAD.meta || {};
      return (
        '<div class="insight">SFs excluídas do universo: <strong>' +
        ((m.sfs_excluidas || []).join(", ") || "—") +
        "</strong><br>Consultores afastados permanecem no detalhe com tag, fora de médias.</div>"
      );
    },
    meta_dedup() {
      return '<div class="insight">Ausências deduplicadas conforme regras em processar.py. Ver dedup_audit.csv na pasta de saída.</div>';
    },
    meta_completude() {
      const k = PAYLOAD.kpis || {};
      return (
        '<div class="insight">Consultores com dado MCCP: ' +
        fmtNum(k.mccp_consultores_com_dado_q, 0) +
        " / " +
        fmtNum(k.n_consultores, 0) +
        "</div>"
      );
    },
    export_hint() {
      return '<div class="block-actions"><p style="font-size:12px;color:#666">Use os botões <strong>Download CSV</strong> nas tabelas desta página.</p></div>';
    },
  };

  // stubs → methodology
  [
    "insight_alertas",
    "insight_alta",
    "insight_baixa",
    "insight_fora",
    "insight_turnover",
    "insight_freq",
    "insight_consistencia",
    "insight_dia",
    "insight_sazonal",
    "insight_medico",
    "insight_setor",
    "insight_desloc",
    "insight_brick",
    "insight_geo",
    "insight_score",
    "insight_ausencia",
    "insight_pessoal",
    "insight_capacidade",
    "insight_gap",
    "insight_esp",
    "insight_matriz",
    "insight_franquia",
    "insight_plano",
    "insight_segmento",
    "insight_cadastro",
    "insight_overlap",
    "insight_territorio_overlap",
    "insight_redist",
    "insight_sim",
    "insight_plan",
    "insight_cenario",
    "insight_backlog",
    "insight_meta",
    "insight_janela",
    "insight_digital",
    "insight_profundidade",
    "insight_relacionamento",
    "insight_sf",
    "insight_gd",
  ].forEach((id) => {
    if (!BLOCKS[id])
      BLOCKS[id] = () =>
        '<div class="insight">Análise derivada do payload filtrado. Ajuste GD/SF/Consultor e janela para refinar.</div>';
  });
  ["table_alertas", "table_consistencia", "table_fora_painel", "table_turnover", "table_janelas", "table_deslocamento", "table_brickagem", "table_geo", "table_ausencia_tipo", "table_pessoais", "table_gap_dias", "table_matriz_esp", "table_sf_cobertura", "table_plano_consultor", "table_painel_alto", "table_tipo_setor", "table_freq_baixa", "table_overlap_cross", "table_mccp_top"].forEach(
    (id) => {
      if (!BLOCKS[id]) BLOCKS[id] = () => BLOCKS.table_consultores();
    }
  );

  function findPage() {
    for (const sec of SECTIONS.sections) {
      if (sec.id !== APP_STATE.sectionId) continue;
      for (const sub of sec.subsections) {
        if (sub.id === APP_STATE.pageId) return { sec, sub };
      }
    }
    return null;
  }

  function renderBlocks(blockIds) {
    return blockIds
      .slice(0, SECTIONS.maxBlocksPerPage || 8)
      .map((bid) => {
        const fn = BLOCKS[bid];
        const title = bid.replace(/_/g, " ");
        const body = fn
          ? fn()
          : '<p style="color:#888">Bloco em construção: ' + bid + "</p>";
        return '<div class="block"><h4>' + title + "</h4>" + body + "</div>";
      })
      .join("");
  }

  function render() {
    const app = document.getElementById("app-main");
    const meta = PAYLOAD.meta || {};
    let html = "";

    if (APP_STATE.view === "home") {
      html =
        '<div class="hero"><h2>Healthcheck Operacional</h2><p>' +
        (meta.bu || "Portal") +
        " · " +
        (meta.janela_label || "") +
        ' — navegue por tema e pergunta de negócio.</p></div><div class="legacy-banner">💡 <strong>Análise crítica:</strong> Este portal prioriza leitura executiva por tema. O dashboard legado (simulador, overlap detalhado, histogramas) continua disponível via <code>python main.py --with-legacy</code>.</div><div class="grid-cards">' +
        SECTIONS.sections
          .map(
            (s) =>
              '<div class="card-section" data-sec="' +
              s.id +
              '"><div class="icon">' +
              (s.icon || "📁") +
              "</div><h3>" +
              s.title +
              "</h3><p>" +
              (s.description || "") +
              "</p></div>"
          )
          .join("") +
        "</div>";
    } else if (APP_STATE.view === "section") {
      const sec = SECTIONS.sections.find((s) => s.id === APP_STATE.sectionId);
      html =
        '<div class="hero"><h2>' +
        sec.title +
        '</h2><p>' +
        (sec.description || "") +
        '</p></div><div class="grid-subs">' +
        sec.subsections
          .map(
            (sub) =>
              '<div class="card-sub" data-page="' +
              sub.id +
              '"><strong>' +
              sub.title +
              "</strong><br><span style='font-size:11px;color:#666'>" +
              (sub.question || "") +
              "</span></div>"
          )
          .join("") +
        "</div>";
    } else if (APP_STATE.view === "page") {
      const found = findPage();
      if (!found) html = "<p>Página não encontrada.</p>";
      else {
        const { sub } = found;
        html =
          '<div class="page-header"><h2>' +
          sub.title +
          '</h2><p class="q">' +
          (sub.question || "") +
          '</p><p class="d">' +
          (sub.decision || "") +
          '</p></div><div class="blocks">' +
          renderBlocks(sub.blocks || []) +
          "</div>";
      }
    }

    app.innerHTML = html;
    updateBreadcrumb();
    bindCards();
  }

  function updateBreadcrumb() {
    const el = document.getElementById("breadcrumb");
    let parts = ['<span data-nav="home">Home</span>'];
    if (APP_STATE.sectionId) {
      const sec = SECTIONS.sections.find((s) => s.id === APP_STATE.sectionId);
      parts.push('<span class="sep">›</span><span data-nav="section">' + (sec ? sec.title : "") + "</span>");
    }
    if (APP_STATE.pageId) {
      const found = findPage();
      if (found) parts.push('<span class="sep">›</span><span>' + found.sub.title + "</span>");
    }
    el.innerHTML = parts.join("");
    el.querySelectorAll("[data-nav]").forEach((n) => {
      n.onclick = () => {
        const t = n.getAttribute("data-nav");
        if (t === "home") {
          APP_STATE.view = "home";
          APP_STATE.sectionId = null;
          APP_STATE.pageId = null;
        } else if (t === "section") {
          APP_STATE.view = "section";
          APP_STATE.pageId = null;
        }
        render();
      };
    });
  }

  function bindCards() {
    document.querySelectorAll(".card-section").forEach((c) => {
      c.onclick = () => {
        APP_STATE.view = "section";
        APP_STATE.sectionId = c.getAttribute("data-sec");
        APP_STATE.pageId = null;
        render();
      };
    });
    document.querySelectorAll(".card-sub").forEach((c) => {
      c.onclick = () => {
        APP_STATE.view = "page";
        APP_STATE.pageId = c.getAttribute("data-page");
        render();
      };
    });
  }

  function populateFilters() {
    const gds = new Set();
    const sfs = new Set();
    (PAYLOAD.consultores || []).forEach((c) => {
      if (c.gd_name) gds.add(c.gd_name);
      if (c.sales_force) sfs.add(c.sales_force);
    });
    const selGd = document.getElementById("f-gd");
    const selSf = document.getElementById("f-sf");
    const selC = document.getElementById("f-consultor");
    [...gds].sort().forEach((g) => {
      selGd.innerHTML += '<option value="' + g + '">' + g + "</option>";
    });
    [...sfs].sort().forEach((s) => {
      selSf.innerHTML += '<option value="' + s + '">' + s + "</option>";
    });
    (PAYLOAD.consultores || []).forEach((c) => {
      selC.innerHTML += '<option value="' + c.ISID + '">' + c.nome + "</option>";
    });
  }

  async function init() {
    try {
      PAYLOAD = await decompressPayload(PAYLOAD_B64);
    } catch (e) {
      document.getElementById("app-main").innerHTML =
        '<p style="color:red">Erro ao carregar payload: ' + e.message + "</p>";
      return;
    }
    document.getElementById("btn-home").onclick = () => {
      APP_STATE.view = "home";
      APP_STATE.sectionId = null;
      APP_STATE.pageId = null;
      render();
    };
    ["f-gd", "f-sf", "f-consultor", "f-janela"].forEach((id) => {
      document.getElementById(id).addEventListener("change", (e) => {
        const key =
          id === "f-gd"
            ? "gd"
            : id === "f-sf"
              ? "salesForce"
              : id === "f-consultor"
                ? "consultor"
                : "janela";
        APP_STATE.filters[key] = e.target.value;
        render();
      });
    });
    populateFilters();
    const m = PAYLOAD.meta || {};
    document.querySelector(".topbar .sub").textContent =
      (m.bu || "") + " · " + (m.janela_label || "") + " · Gerado " + (m.gerado_em || "");
    render();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
