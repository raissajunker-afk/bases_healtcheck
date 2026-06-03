// Filtros globais: construção da UI e aplicação centralizada.
HC.filters = (function () {
  const P = window.PAYLOAD;

  function buildUI() {
    const host = document.getElementById("filters");
    host.innerHTML = "";
    const dims = P.dimensions || {};
    const defs = [
      { key: "gd", label: "GD", values: dims.gd || [] },
      { key: "sales_force", label: "Sales Force", values: dims.sales_force || [] },
      { key: "consultor", label: "Consultor", values: dims.consultor || [] },
    ];
    defs.forEach((d) => host.appendChild(makeSelect(d.key, d.label, d.values, false)));
    // janela
    const jan = (dims.janelas || []).map((j) => ({ id: j.id, label: j.label }));
    host.appendChild(makeJanela(jan));
  }

  function makeSelect(key, label, values, allowEmpty) {
    const wrap = HC.util.el("div", "filter");
    wrap.appendChild(HC.util.el("label", null, label));
    const sel = HC.util.el("select");
    sel.appendChild(opt("__all__", "Todos"));
    values.forEach((v) => sel.appendChild(opt(v, v)));
    sel.value = HC.state.APP_STATE.filters[key];
    sel.addEventListener("change", () => HC.state.setFilter(key, sel.value));
    wrap.appendChild(sel);
    return wrap;
  }

  function makeJanela(janelas) {
    const wrap = HC.util.el("div", "filter");
    wrap.appendChild(HC.util.el("label", null, "Janela"));
    const sel = HC.util.el("select");
    janelas.forEach((j) => sel.appendChild(opt(j.id, j.label)));
    sel.value = HC.state.APP_STATE.filters.janela;
    sel.addEventListener("change", () => HC.state.setFilter("janela", sel.value));
    wrap.appendChild(sel);
    return wrap;
  }

  function opt(value, label) {
    const o = document.createElement("option");
    o.value = value; o.textContent = label;
    return o;
  }

  // Aplica filtros de GD/SF/Consultor a um array de linhas.
  function applyEntity(rows) {
    const f = HC.state.APP_STATE.filters;
    return (rows || []).filter((r) => {
      if (f.gd !== "__all__" && r.gd !== undefined && r.gd !== f.gd) return false;
      if (f.sales_force !== "__all__" && r.sales_force !== undefined && r.sales_force !== f.sales_force) return false;
      if (f.consultor !== "__all__" && r.consultor !== undefined && r.consultor !== f.consultor) return false;
      return true;
    });
  }

  // Recorte temporal: mantém apenas os últimos N meses conforme a janela.
  function applyJanela(rows, ymField) {
    const f = HC.state.APP_STATE.filters;
    const meta = { mat: 12, ult3m: 3, mes_fechado: 1, mes_atual: 1 };
    const n = meta[f.janela] || 12;
    const ordenadas = [...(rows || [])].sort((a, b) => String(a[ymField]).localeCompare(String(b[ymField])));
    return ordenadas.slice(-n);
  }

  return { buildUI, applyEntity, applyJanela };
})();
