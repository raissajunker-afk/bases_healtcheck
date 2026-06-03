// Componente KPI. Renderiza um cartão de indicador com semáforo opcional.
HC.components = HC.components || {};
HC.components.kpi = function (block) {
  const benchmarks = (window.PAYLOAD.meta || {}).benchmarks || {};
  const bench = block.benchmark ? benchmarks[block.benchmark] : null;
  const value = HC.agg.kpiValue(block);
  const cls = HC.util.benchClass(value, bench);

  const card = HC.util.el("div", "card kpi " + cls);
  if (cls) card.appendChild(HC.util.el("span", "dot " + cls));
  card.appendChild(HC.util.el("span", "kpi-label", HC.util.escapeHtml(block.title)));
  card.appendChild(HC.util.el("span", "kpi-value", HC.util.fmt(value, block.format)));
  if (block.subtitle) card.appendChild(HC.util.el("span", "kpi-sub", HC.util.escapeHtml(block.subtitle)));
  if (bench) {
    const pct = bench.higher_is_better === false
      ? Math.max(0, 100 - Math.min(100, (value / (bench.warn * 2)) * 100))
      : Math.min(100, (value / (bench.good || 1)) * 100);
    const bar = HC.util.el("div", "kpi-bar");
    const span = HC.util.el("span");
    span.style.width = pct + "%";
    span.style.background = cls === "good" ? "var(--c-good)" : cls === "warn" ? "var(--c-warn)" : "var(--c-bad)";
    bar.appendChild(span);
    card.appendChild(bar);
  }
  // marca como kpi-block para gráficos por SF/GD reaproveitarem grid menor
  card._span = "span-3";
  return card;
};
