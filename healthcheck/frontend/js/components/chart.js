// Componente de gráfico (SVG puro, sem dependências externas).
HC.components = HC.components || {};

const PALETTE = ["#00857c", "#2f6fb0", "#e0a106", "#d4503e", "#7a5bb0", "#1f9d74"];

HC.components.chart = function (block) {
  const card = HC.util.el("div", "card chart");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  let svg = "";
  if (block.chartType === "heatmap") {
    svg = heatmap(block);
  } else if (block.x && block.series && block.series.length) {
    svg = block.chartType === "line" ? lineChart(block) : barSeries(block);
  } else if (block.labelField && block.valueField) {
    if (block.chartType === "donut") svg = donut(block);
    else svg = barCategory(block);
  }
  const body = HC.util.el("div");
  body.innerHTML = svg || "<p class='muted'>Sem dados para os filtros atuais.</p>";
  card.appendChild(body);
  card._span = "span-6";
  return card;
};

function opFor(field) {
  return /^pct_|dia|score|icef|ifef|idef|iaef|media|freq/.test(field) ? "mean" : "sum";
}

function legend(items) {
  return "<div class='chart-legend'>" + items.map((it, i) =>
    "<span><i style='background:" + PALETTE[i % PALETTE.length] + "'></i>" + HC.util.escapeHtml(it) + "</span>").join("") + "</div>";
}

function lineChart(block) {
  const rows = HC.agg.dataset(block.dataset);
  if (!rows.length) return "";
  const W = 560, H = 220, pad = 34;
  const xs = rows.map((r) => r[block.x]);
  const allVals = [];
  block.series.forEach((s) => rows.forEach((r) => allVals.push(parseFloat(r[s.field]) || 0)));
  const max = Math.max(1, ...allVals);
  const stepX = (W - pad * 2) / Math.max(1, rows.length - 1);
  const y = (v) => H - pad - (v / max) * (H - pad * 2);
  let paths = "";
  block.series.forEach((s, si) => {
    const pts = rows.map((r, i) => (pad + i * stepX) + "," + y(parseFloat(r[s.field]) || 0)).join(" ");
    paths += "<polyline fill='none' stroke='" + PALETTE[si % PALETTE.length] + "' stroke-width='2.5' points='" + pts + "'/>";
    paths += rows.map((r, i) => "<circle cx='" + (pad + i * stepX) + "' cy='" + y(parseFloat(r[s.field]) || 0) + "' r='2.5' fill='" + PALETTE[si % PALETTE.length] + "'/>").join("");
  });
  const labels = rows.map((r, i) => i % Math.ceil(rows.length / 8 || 1) === 0
    ? "<text class='lbl' x='" + (pad + i * stepX) + "' y='" + (H - 12) + "' text-anchor='middle'>" + HC.util.escapeHtml(xs[i]) + "</text>" : "").join("");
  return "<svg viewBox='0 0 " + W + " " + H + "'>" +
    "<line class='axis' x1='" + pad + "' y1='" + (H - pad) + "' x2='" + (W - pad) + "' y2='" + (H - pad) + "'/>" +
    paths + labels + "</svg>" + legend(block.series.map((s) => s.label));
}

function barSeries(block) {
  const rows = HC.agg.dataset(block.dataset);
  if (!rows.length) return "";
  const W = 560, H = 220, pad = 34;
  const s = block.series[0];
  const max = Math.max(1, ...rows.map((r) => parseFloat(r[s.field]) || 0));
  const bw = (W - pad * 2) / rows.length * 0.7;
  const step = (W - pad * 2) / rows.length;
  const y = (v) => H - pad - (v / max) * (H - pad * 2);
  let bars = rows.map((r, i) => {
    const v = parseFloat(r[s.field]) || 0;
    const x = pad + i * step + (step - bw) / 2;
    return "<rect x='" + x + "' y='" + y(v) + "' width='" + bw + "' height='" + (H - pad - y(v)) + "' fill='" + PALETTE[0] + "' rx='2'/>";
  }).join("");
  const labels = rows.map((r, i) => i % Math.ceil(rows.length / 8 || 1) === 0
    ? "<text class='lbl' x='" + (pad + i * step + step / 2) + "' y='" + (H - 12) + "' text-anchor='middle'>" + HC.util.escapeHtml(r[block.x]) + "</text>" : "").join("");
  return "<svg viewBox='0 0 " + W + " " + H + "'><line class='axis' x1='" + pad + "' y1='" + (H - pad) + "' x2='" + (W - pad) + "' y2='" + (H - pad) + "'/>" + bars + labels + "</svg>" + legend([s.label]);
}

function barCategory(block) {
  let data = HC.agg.groupBy(HC.agg.dataset(block.dataset), block.labelField, block.valueField, opFor(block.valueField));
  data = data.filter((d) => d.label && d.label !== "(sem)").sort((a, b) => b.value - a.value).slice(0, 14);
  if (!data.length) return "";
  const W = 560, rowH = 26, H = data.length * rowH + 10, labelW = 150;
  const max = Math.max(1, ...data.map((d) => d.value));
  const bars = data.map((d, i) => {
    const w = (d.value / max) * (W - labelW - 60);
    const y = i * rowH + 4;
    return "<text class='lbl' x='0' y='" + (y + 14) + "'>" + HC.util.escapeHtml(String(d.label).slice(0, 22)) + "</text>" +
      "<rect x='" + labelW + "' y='" + y + "' width='" + w + "' height='16' fill='" + PALETTE[0] + "' rx='3'/>" +
      "<text class='lbl' x='" + (labelW + w + 5) + "' y='" + (y + 13) + "'>" + (Math.round(d.value * 10) / 10).toLocaleString("pt-BR") + "</text>";
  }).join("");
  return "<svg viewBox='0 0 " + W + " " + H + "'>" + bars + "</svg>";
}

function donut(block) {
  let data = HC.agg.groupBy(HC.agg.dataset(block.dataset), block.labelField, block.valueField, "count");
  data = data.filter((d) => d.label && d.label !== "(sem)").sort((a, b) => b.value - a.value);
  if (!data.length) return "";
  const total = data.reduce((a, b) => a + b.value, 0) || 1;
  const cx = 90, cy = 90, r = 70, rin = 42;
  let a0 = -Math.PI / 2, arcs = "";
  data.slice(0, 6).forEach((d, i) => {
    const a1 = a0 + (d.value / total) * Math.PI * 2;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const xi1 = cx + rin * Math.cos(a1), yi1 = cy + rin * Math.sin(a1);
    const xi0 = cx + rin * Math.cos(a0), yi0 = cy + rin * Math.sin(a0);
    arcs += "<path d='M" + x0 + "," + y0 + " A" + r + "," + r + " 0 " + large + " 1 " + x1 + "," + y1 +
      " L" + xi1 + "," + yi1 + " A" + rin + "," + rin + " 0 " + large + " 0 " + xi0 + "," + yi0 + " Z' fill='" + PALETTE[i % PALETTE.length] + "'/>";
    a0 = a1;
  });
  return "<div style='display:flex;gap:16px;align-items:center;flex-wrap:wrap'><svg viewBox='0 0 180 180' style='width:180px'>" + arcs + "</svg>" +
    "<div>" + data.slice(0, 6).map((d, i) =>
      "<div style='font-size:12px;margin:3px 0'><i style='display:inline-block;width:10px;height:10px;border-radius:3px;background:" + PALETTE[i % PALETTE.length] + ";margin-right:6px'></i>" +
      HC.util.escapeHtml(d.label) + " — <b>" + d.value + "</b></div>").join("") + "</div></div>";
}

function heatmap(block) {
  const rows = HC.agg.dataset(block.dataset);
  if (!rows.length) return "";
  const franquias = [...new Set(rows.map((r) => r.franquia))].slice(0, 12);
  const esp = [...new Set(rows.map((r) => r.especialidade))].slice(0, 16);
  const map = {};
  rows.forEach((r) => { map[r.franquia + "||" + r.especialidade] = parseFloat(r[block.valueField]) || 0; });
  const cell = 30, labelW = 120, headH = 70;
  const W = labelW + esp.length * cell + 10;
  const H = headH + franquias.length * cell + 10;
  function color(v) {
    if (v == null) return "#eceff1";
    const t = Math.min(1, v / 100);
    const r = Math.round(212 - t * (212 - 31)), g = Math.round(80 + t * (157 - 80)), b = Math.round(62 + t * (116 - 62));
    return "rgb(" + r + "," + g + "," + b + ")";
  }
  let svg = "";
  esp.forEach((e, j) => {
    svg += "<text class='lbl' transform='translate(" + (labelW + j * cell + cell / 2) + "," + (headH - 6) + ") rotate(-45)' text-anchor='start'>" + HC.util.escapeHtml(String(e).slice(0, 14)) + "</text>";
  });
  franquias.forEach((f, i) => {
    svg += "<text class='lbl' x='0' y='" + (headH + i * cell + cell / 2 + 3) + "'>" + HC.util.escapeHtml(String(f).slice(0, 16)) + "</text>";
    esp.forEach((e, j) => {
      const v = map[f + "||" + e];
      svg += "<rect class='heat-cell' x='" + (labelW + j * cell) + "' y='" + (headH + i * cell) + "' width='" + cell + "' height='" + cell + "' fill='" + color(v) + "'><title>" + HC.util.escapeHtml(f + " / " + e + ": " + (v == null ? "sem dado" : v + "%")) + "</title></rect>";
    });
  });
  return "<div style='overflow:auto'><svg viewBox='0 0 " + W + " " + H + "' style='min-width:" + W + "px'>" + svg + "</svg></div>";
}
