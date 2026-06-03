(function () {
  window.Portal = window.Portal || {};

  function unique(items) {
    return Array.from(new Set(items.filter(Boolean))).sort();
  }

  function fillSelect(selectId, values, labelField) {
    const select = document.getElementById(selectId);
    select.innerHTML = "";
    const all = document.createElement("option");
    all.value = "__all__";
    all.textContent = "Todos";
    select.appendChild(all);
    values.forEach((value) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value;
      select.appendChild(opt);
    });
  }

  window.Portal.filters = {
    init(payload, onChange) {
      const consultores = payload.dimensions.consultores || [];
      const gds = unique(consultores.map((item) => item.gd));
      const salesForces = unique(consultores.map((item) => item.sales_force));
      const consultorNames = unique(consultores.map((item) => item.consultor));

      fillSelect("filter-gd", gds, "gd");
      fillSelect("filter-sales-force", salesForces, "sales_force");
      fillSelect("filter-consultor", consultorNames, "consultor");

      const map = {
        "filter-gd": "gd",
        "filter-sales-force": "salesForce",
        "filter-consultor": "consultor",
        "filter-janela": "janela",
      };

      Object.keys(map).forEach((elementId) => {
        const key = map[elementId];
        document.getElementById(elementId).addEventListener("change", (event) => {
          window.Portal.state.filters[key] = event.target.value;
          onChange();
        });
      });
    },
  };
})();
