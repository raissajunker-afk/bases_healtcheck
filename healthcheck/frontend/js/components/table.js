// Componentes de tabela e ranking.
HC.components = HC.components || {};

HC.components.table = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));

  let rows = HC.agg.dataset(block.dataset);

  if (block.sort) {
    const dir = block.dir === "asc" ? 1 : -1;
    rows = [...rows].sort((a, b) => {
      const va = HC.agg.fval(a, block.sort), vb = HC.agg.fval(b, block.sort);
      const na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
      return String(va == null ? "" : va).localeCompare(String(vb == null ? "" : vb)) * dir;
    });
  }
  rows = rows.slice(0, block.limit || 50);

  const wrap = HC.util.el("div", "tbl-wrap");
  const tbl = HC.util.el("table", "tbl");
  const thead = HC.util.el("thead");
  const trh = HC.util.el("tr");
  block.columns.forEach((c) => {
    const isNum = ["int", "float", "decimal2", "percent"].includes(c.format);
    trh.appendChild(HC.util.el("th", isNum ? "num" : null, HC.util.escapeHtml(c.label)));
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
      tr.appendChild(HC.util.el("td", isNum ? "num" : null, HC.util.fmt(HC.agg.fval(r, c.field), c.format)));
    });
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
  card.appendChild(wrap);
  card._span = "span-6";
  return card;
};

HC.components.ranking = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));

  let rows = HC.agg.dataset(block.dataset).filter((r) => HC.agg.fval(r, block.valueField) != null);
  const dir = block.dir === "asc" ? 1 : -1;
  rows = [...rows].sort((a, b) => ((parseFloat(HC.agg.fval(a, block.valueField)) || 0) - (parseFloat(HC.agg.fval(b, block.valueField)) || 0)) * dir);
  rows = rows.slice(0, block.limit || 15);

  const max = Math.max(1, ...rows.map((r) => Math.abs(parseFloat(HC.agg.fval(r, block.valueField)) || 0)));
  if (!rows.length) card.appendChild(HC.util.el("p", "muted", "Sem dados para os filtros atuais."));

  rows.forEach((r, i) => {
    const row = HC.util.el("div", "rank-row");
    row.appendChild(HC.util.el("div", "rank-pos", String(i + 1)));
    let sub = "";
    (block.extra || []).forEach((c) => { const v = HC.agg.fval(r, c.field); if (v) sub += HC.util.escapeHtml(HC.util.fmt(v, c.format)) + " "; });
    const lbl = HC.util.el("div", "rank-label",
      HC.util.escapeHtml(r[block.labelField] || "—") + (sub ? "<small>" + sub + "</small>" : ""));
    row.appendChild(lbl);
    row.appendChild(HC.util.el("div", "rank-val", HC.util.fmt(HC.agg.fval(r, block.valueField), block.format)));
    const bar = HC.util.el("div", "rank-bar");
    const span = HC.util.el("span");
    span.style.width = ((Math.abs(parseFloat(HC.agg.fval(r, block.valueField)) || 0) / max) * 100) + "%";
    bar.appendChild(span);
    row.appendChild(bar);
    card.appendChild(row);
  });
  card._span = "span-6";
  return card;
};
