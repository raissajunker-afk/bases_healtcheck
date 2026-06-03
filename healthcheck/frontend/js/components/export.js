// Componente de exportação. Gera CSV do dataset (respeitando os filtros) e
// dispara o download no próprio navegador (offline).
HC.components = HC.components || {};

HC.components.export = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  const rows = HC.agg.dataset(block.dataset);
  const info = HC.util.el("p", "muted", rows.length + " registros no recorte atual.");
  card.appendChild(info);
  const btn = HC.util.el("button", "btn", "⬇ Exportar CSV");
  btn.addEventListener("click", () => download(block.dataset, rows));
  card.appendChild(btn);
  card._span = "span-6";
  return card;
};

function download(name, rows) {
  if (!rows.length) { alert("Sem dados para exportar."); return; }
  const cols = Object.keys(rows[0]).filter((k) => !k.startsWith("_"));
  const sep = ";";
  let csv = cols.join(sep) + "\n";
  rows.forEach((r) => { csv += cols.map((c) => HC.util.csvEscape(r[c])).join(sep) + "\n"; });
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "healthcheck_" + name + ".csv";
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
