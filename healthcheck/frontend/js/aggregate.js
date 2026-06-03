// Resolução de datasets (com filtros) e agregações para os blocos.
HC.agg = (function () {
  const P = window.PAYLOAD;
  const SERIE = { serie_visitas: 1, serie_ausencias: 1, serie_painel: 1, serie_pv: 1 };
  const SUFIXOS = (P.meta && P.meta.janela_sufixos) || {};

  function dataset(name) {
    const raw = (P.datasets || {})[name] || [];
    if (SERIE[name]) {
      const ent = HC.filters.applyEntity(raw);
      return HC.filters.applyJanela(ent, "ym");
    }
    return HC.filters.applyEntity(raw);
  }

  // Resolve o valor de um campo aplicando a janela (sufixo) quando existir variante.
  function fval(row, field) {
    if (!field) return undefined;
    const jan = HC.state.APP_STATE.filters.janela;
    const suf = SUFIXOS[jan];
    if (suf) {
      const cand = field + suf;
      if (row[cand] !== undefined && row[cand] !== null) return row[cand];
    }
    return row[field];
  }

  function sum(rows, field) { return rows.reduce((a, r) => a + (parseFloat(fval(r, field)) || 0), 0); }
  function mean(rows, field) {
    const v = rows.map((r) => parseFloat(fval(r, field))).filter((x) => !isNaN(x));
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0;
  }
  function count(rows) { return rows.length; }
  function ratio(rows, num, den) {
    const n = sum(rows, num), d = sum(rows, den);
    return d ? (100 * n) / d : 0;
  }

  function kpiValue(block) {
    if (block.agg === "value") {
      const s = (P.summaries || {})[block.dataset] || {};
      return s[block.field];
    }
    const rows = dataset(block.dataset);
    switch (block.agg) {
      case "sum": return sum(rows, block.field);
      case "mean": return Math.round(mean(rows, block.field) * 100) / 100;
      case "count": return count(rows);
      case "ratio": return Math.round(ratio(rows, block.num, block.den) * 10) / 10;
      default: return null;
    }
  }

  function groupBy(rows, labelField, valueField, op) {
    const m = {};
    rows.forEach((r) => {
      const k = r[labelField] || "(sem)";
      if (!m[k]) m[k] = { label: k, sum: 0, count: 0, vals: [] };
      const v = parseFloat(fval(r, valueField));
      if (!isNaN(v)) { m[k].sum += v; m[k].vals.push(v); }
      m[k].count += 1;
    });
    return Object.values(m).map((g) => ({
      label: g.label,
      value: op === "mean" ? (g.vals.length ? g.sum / g.vals.length : 0)
        : op === "count" ? g.count : g.sum,
    }));
  }

  return { dataset, fval, sum, mean, count, ratio, kpiValue, groupBy };
})();
