// Componentes auxiliares: simulador, metodologia, auditoria e placeholder.
HC.components = HC.components || {};

HC.components.methodology = function (block) {
  const card = HC.util.el("div", "card method");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  const ul = HC.util.el("ul");
  (block.items || []).forEach((it) => ul.appendChild(HC.util.el("li", null, HC.util.escapeHtml(it))));
  card.appendChild(ul);
  card._span = "span-6";
  return card;
};

HC.components.empty = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  card.appendChild(HC.util.el("div", "empty-block", "<div style='font-size:26px'>🧩</div><div>" + HC.util.escapeHtml(block.message) + "</div>"));
  card._span = "span-6";
  return card;
};

HC.components.audit = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  const data = resolvePath(window.PAYLOAD, block.path);
  const pre = HC.util.el("pre");
  pre.style.cssText = "white-space:pre-wrap;font-size:12px;background:var(--c-surface-2);padding:12px;border-radius:8px;overflow:auto;max-height:420px";
  pre.textContent = JSON.stringify(data, null, 2);
  card.appendChild(pre);
  card._span = "span-12";
  return card;
};

HC.components.simulator = function (block) {
  const card = HC.util.el("div", "card");
  card.appendChild(HC.util.el("div", "card-title", "<h3>" + HC.util.escapeHtml(block.title) + "</h3>"));
  const grid = HC.util.el("div", "sim-grid");
  const inputsCol = HC.util.el("div");
  const outCol = HC.util.el("div");
  const state = {};

  (block.inputs || []).forEach((inp) => {
    state[inp.id] = inp.default;
    const wrap = HC.util.el("div", "sim-input");
    wrap.appendChild(HC.util.el("label", null, HC.util.escapeHtml(inp.label)));
    const field = HC.util.el("input");
    field.type = "number"; field.value = inp.default;
    field.addEventListener("input", () => { state[inp.id] = parseFloat(field.value) || 0; recompute(); });
    wrap.appendChild(field);
    inputsCol.appendChild(wrap);
  });

  function recompute() {
    outCol.innerHTML = "";
    (block.outputs || []).forEach((o) => {
      let val = 0;
      try { val = evalFormula(o.formula, state); } catch (e) { val = 0; }
      const row = HC.util.el("div", "sim-out",
        "<span>" + HC.util.escapeHtml(o.label) + "</span><b>" + Math.round(val).toLocaleString("pt-BR") + "</b>");
      outCol.appendChild(row);
    });
  }

  grid.appendChild(inputsCol);
  grid.appendChild(outCol);
  card.appendChild(grid);
  recompute();
  card._span = "span-12";
  return card;
};

function evalFormula(formula, vars) {
  const names = Object.keys(vars);
  const vals = names.map((n) => vars[n]);
  // eslint-disable-next-line no-new-func
  const fn = new Function(...names, "return (" + formula + ");");
  return fn(...vals);
}

function resolvePath(obj, path) {
  return (path || "").split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}
