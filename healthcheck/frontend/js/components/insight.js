// Componente de insight automático. Avalia regras contra valores de KPIs já
// renderizados na página (registrados em HC.pageKpiValues) ou contra summaries.
HC.components = HC.components || {};

HC.components.insight = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  const ctx = HC.pageKpiValues || {};
  let mostrou = false;
  (block.rules || []).forEach((rule) => {
    const cond = rule.if;
    const val = ctx[cond.field];
    if (val == null) return;
    if (testOp(val, cond.op, cond.value)) {
      const level = rule.level || "info";
      const ico = level === "risco" || level === "alerta" ? "⚠️" : level === "oportunidade" ? "💡" : "ℹ️";
      const ins = HC.util.el("div", "insight " + level,
        "<div class='ico'>" + ico + "</div><div class='txt'><b>" + level.toUpperCase() + "</b>" + HC.util.escapeHtml(rule.text) + "</div>");
      ins.style.marginBottom = "8px";
      card.appendChild(ins);
      mostrou = true;
    }
  });
  if (!mostrou) {
    card.appendChild(HC.util.el("div", "insight", "<div class='ico'>✅</div><div class='txt'><b>SEM ALERTAS</b>Nenhuma regra crítica disparada para o recorte atual.</div>"));
  }
  card._span = "span-6";
  return card;
};

function testOp(a, op, b) {
  a = parseFloat(a); b = parseFloat(b);
  switch (op) {
    case "<": return a < b;
    case "<=": return a <= b;
    case ">": return a > b;
    case ">=": return a >= b;
    case "==": return a === b;
    default: return false;
  }
}
