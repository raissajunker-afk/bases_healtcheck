/* Fase 3 — renderização nativa de blocos a partir de DATA.portal */
(function (global) {
  "use strict";

  const SECTION_PORTAL_KEY = {
    executive: "executive",
    performance: "performance",
    cobertura: "cobertura",
    visitacao: "visitacao",
    territorio: "territorio",
    ausencias: "ausencias",
    especialidades: "especialidades_franquias",
    qualidade: "qualidade_execucao",
    overlap: "overlap",
    simulador: "simulador",
    oportunidades: "oportunidades",
    governanca: "governanca",
    canal_digital: "canal_digital",
    benchmarking: "benchmarking",
    relacionamento: "relacionamento",
  };

  function fmt(v, kind) {
    if (v == null || v === "" || (typeof v === "number" && Number.isNaN(v))) return "—";
    const n = Number(v);
    if (kind === "int") return Math.round(n).toLocaleString("pt-BR");
    if (kind === "percent") return n.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";
    if (kind === "decimal") return n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
    return String(v);
  }

  function kpiClass(v, good, warn, invert) {
    if (v == null || good == null) return "";
    const ok = invert ? v <= good : v >= good;
    if (ok) return "good";
    if (warn != null) {
      const wok = invert ? v <= warn : v >= warn;
      if (wok) return "warn";
    }
    return "bad";
  }

  function exportCsv(filename, columns, rows) {
    const sep = ";";
    const head = columns.map((c) => c.label).join(sep);
    const body = rows
      .map((r) =>
        columns
          .map((c) => {
            let v = r[c.key];
            if (v == null) v = "";
            v = String(v).replace(/"/g, '""');
            if (String(v).includes(sep)) v = '"' + v + '"';
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

  function renderKpiRow(block) {
    const items = block.items || [];
    return (
      '<div class="pn-kpi-row">' +
      items
        .map((k) => {
          const cls = k.status || kpiClass(k.value, k.good, k.warn, k.invert);
          return (
            '<div class="pn-kpi ' +
            cls +
            '"><div class="v">' +
            fmt(k.value, k.format) +
            '</div><div class="l">' +
            (k.label || "") +
            "</div></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderTable(block, blockId) {
    const cols = block.columns || [];
    const rows = block.rows || [];
    const tid = "pn-tbl-" + blockId;
    let html =
      '<div class="pn-table-wrap"><table class="pn-t" id="' +
      tid +
      '"><thead><tr>' +
      cols.map((c) => "<th>" + c.label + "</th>").join("") +
      "</tr></thead><tbody>";
    if (!rows.length) {
      html += '<tr><td colspan="' + cols.length + '">Sem dados para o filtro atual.</td></tr>';
    } else {
      html += rows
        .map(
          (r) =>
            "<tr>" +
            cols
              .map((c) => {
                let v = r[c.key];
                if (c.fmt) v = c.fmt(v, r);
                else if (c.format) v = fmt(v, c.format);
                return '<td class="' + (c.num ? "num" : "") + '">' + (v ?? "—") + "</td>";
              })
              .join("") +
            "</tr>"
        )
        .join("");
    }
    html += "</tbody></table></div>";
    if (block.exportCsv && rows.length) {
      html +=
        '<div class="pn-actions"><button type="button" class="btn-secondary btn-exp-sm pn-btn-csv" data-tid="' +
        tid +
        '">↓ Download CSV</button></div>';
      setTimeout(() => {
        document.querySelectorAll('.pn-btn-csv[data-tid="' + tid + '"]').forEach((btn) => {
          btn.onclick = () => exportCsv(block.exportCsv, cols, rows);
        });
      }, 0);
    }
    return html;
  }

  function renderBarChart(block) {
    const series = block.series || [];
    if (!series.length) return '<p style="font-size:12px;color:var(--ink3)">Sem série disponível.</p>';
    const max = Math.max(...series.map((x) => Number(x.value) || 0), 1);
    return (
      '<div class="pn-bars">' +
      series
        .map((x) => {
          const v = Number(x.value) || 0;
          const h = Math.round((v / max) * 130);
          return (
            '<div class="pn-bar-wrap"><div class="pn-bar" style="height:' +
            h +
            'px" title="' +
            (x.label || "") +
            ": " +
            v +
            '"></div><div class="pn-bar-lbl">' +
            (x.label || "") +
            "</div></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderInsight(block) {
    const items = block.items || [];
    return items
      .map((i) => {
        const t = i.type || "info";
        return '<div class="pn-insight ' + t + '">' + (i.text || "") + "</div>";
      })
      .join("");
  }

  function renderBlock(block, idx) {
    const t = block.type;
    const title = block.title ? "<h4>" + block.title + "</h4>" : "";
    let body = "";
    if (t === "kpi_row") body = renderKpiRow(block);
    else if (t === "table") body = renderTable(block, idx);
    else if (t === "bar_chart") body = renderBarChart(block);
    else if (t === "insight") body = renderInsight(block);
    else if (t === "text")
      body = '<p style="font-size:12px">' + (block.text || "") + "</p>";
  else if (t === "legacy_link")
      body =
        '<span class="pn-link-legacy" data-vista="' +
        (block.vista || "") +
        '" data-anchor="' +
        (block.anchor || "") +
        '">Abrir visualização completa (dashboard) →</span>';
    else body = "<p>Bloco desconhecido: " + t + "</p>";
    return '<div class="pn-block">' + title + body + "</div>";
  }

  function getPageBlocks(sectionId, pageId) {
    if (typeof DATA === "undefined" || !DATA.portal) return null;
    const key = SECTION_PORTAL_KEY[sectionId] || sectionId;
    const sec = DATA.portal.sections[key];
    if (!sec || !sec.pages || !sec.pages[pageId]) return null;
    return sec.pages[pageId].blocks || null;
  }

  function portalRenderNativePage(sectionId, pageId, sub) {
    const host = document.getElementById("portal-native-page");
    if (!host) return false;
    const blocks = getPageBlocks(sectionId, pageId);
    if (!blocks || !blocks.length) return false;

    document.querySelectorAll(".vista").forEach((v) => v.classList.remove("active"));
    host.style.display = "block";
    host.innerHTML =
      '<div class="pn-blocks">' +
      blocks.map((b, i) => renderBlock(b, sectionId + "-" + pageId + "-" + i)).join("") +
      "</div>";

    host.querySelectorAll(".pn-link-legacy").forEach((el) => {
      el.onclick = () => {
        document.body.className = "portal-mode-page";
        host.style.display = "none";
        if (typeof setTab === "function") setTab(el.dataset.vista || sub.legacyVista);
        const a = el.dataset.anchor;
        if (a) {
          const target = document.getElementById(a);
          if (target) target.scrollIntoView({ behavior: "smooth" });
        }
      };
    });
    return true;
  }

  global.PortalBlocks = {
    getPageBlocks,
    portalRenderNativePage,
    fmt,
  };
})(typeof window !== "undefined" ? window : this);
