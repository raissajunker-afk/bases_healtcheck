// Componentes de tabela e ranking.
HC.components = HC.components || {};

HC.components.table = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));

  let rows = HC.agg.dataset(block.dataset);
  // agregação por dimensão se a primeira coluna for categórica e houver repetição
  rows = maybeAggregate(rows, block);

  if (block.sort) {
    const dir = block.dir === "asc" ? 1 : -1;
    rows = [...rows].sort((a, b) => {
      const va = a[block.sort], vb = b[block.sort];
      const na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
      return String(va || "").localeCompare(String(vb || "")) * dir;
    });
  }
  rows = rows.slice(0, block.limit || 50);

  const wrap = HC.util.el("div", "tbl-wrap");
  const tbl = HC.util.el("table", "tbl");
  const thead = HC.util.el("thead");
  const trh = HC.util.el("tr");
  block.columns.forEach((c) => {
    const isNum = ["int", "float", "decimal2", "percent"].includes(c.format);
    const th = HC.util.el("th", isNum ? "num" : null, HC.util.escapeHtml(c.label));
    trh.appendChild(th);
  });
  thead.appendChild(trh);
  tbl.appendChild(thead);

  const tbody = HC.util.el("tbody");
  if (!rows.length) {
    const tr = HC.util.el("tr");
    const td = HC.util.el("td", "muted", "Sem dados para os filtros atuais.");
    td.colSpan = block.columns.length;
    tr.appendChild(td); tbody.appendChild(tr);
  }
  rows.forEach((r) => {
    const tr = HC.util.el("tr");
    block.columns.forEach((c) => {
      const isNum = ["int", "float", "decimal2", "percent"].includes(c.format);
      const td = HC.util.el("td", isNum ? "num" : null, HC.util.fmt(r[c.field], c.format));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
  card.appendChild(wrap);
  card._span = "span-6";
  return card;
};

// Quando a tabela é "por SF" ou "por GD" (1ª coluna categórica e repetida),
// agregamos automaticamente as métricas numéricas.
function maybeAggregate(rows, block) {
  const first = block.columns[0];
  if (!first) return rows;
  const dim = first.field;
  if (!["sales_force", "gd"].includes(dim)) return rows;
  // só agrega se houver repetição da dimensão
  const keys = new Set(rows.map((r) => r[dim]));
  if (keys.size === rows.length) return rows;

  const m = {};
  rows.forEach((r) => {
    const k = r[dim] || "(sem)";
    if (!m[k]) { m[k] = { _n: 0 }; block.columns.forEach((c) => (m[k][c.field] = 0)); m[k][dim] = k; }
    m[k]._n += 1;
    block.columns.slice(1).forEach((c) => {
      const v = parseFloat(r[c.field]);
      if (!isNaN(v)) m[k][c.field] += v;
    });
  });
  return Object.values(m).map((g) => {
    block.columns.slice(1).forEach((c) => {
      if (c.format === "percent" || c.format === "decimal2") g[c.field] = g._n ? g[c.field] / g._n : 0;
    });
    return g;
  });
}

HC.components.ranking = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));

  let rows = HC.agg.dataset(block.dataset).filter((r) => r[block.valueField] != null);
  const dir = block.dir === "asc" ? 1 : -1;
  rows = [...rows].sort((a, b) => ((parseFloat(a[block.valueField]) || 0) - (parseFloat(b[block.valueField]) || 0)) * dir);
  rows = rows.slice(0, block.limit || 15);

  const max = Math.max(1, ...rows.map((r) => Math.abs(parseFloat(r[block.valueField]) || 0)));
  if (!rows.length) card.appendChild(HC.util.el("p", "muted", "Sem dados para os filtros atuais."));

  rows.forEach((r, i) => {
    const row = HC.util.el("div", "rank-row");
    row.appendChild(HC.util.el("div", "rank-pos", String(i + 1)));
    let sub = "";
    (block.extra || []).forEach((c) => { if (r[c.field]) sub += HC.util.escapeHtml(r[c.field]) + " "; });
    const lbl = HC.util.el("div", "rank-label",
      HC.util.escapeHtml(r[block.labelField] || "—") + (sub ? "<small>" + sub + "</small>" : ""));
    row.appendChild(lbl);
    row.appendChild(HC.util.el("div", "rank-val", HC.util.fmt(r[block.valueField], block.format)));
    const bar = HC.util.el("div", "rank-bar");
    const span = HC.util.el("span");
    span.style.width = ((Math.abs(parseFloat(r[block.valueField]) || 0) / max) * 100) + "%";
    bar.appendChild(span);
    row.appendChild(bar);
    card.appendChild(row);
  });
  card._span = "span-6";
  return card;
};
