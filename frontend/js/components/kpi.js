(function () {
  window.Portal = window.Portal || {};
  window.Portal.components = window.Portal.components || {};

  function formatValue(value, format) {
    if (format === "percent") return `${Number(value || 0).toFixed(1)}%`;
    if (format === "float1") return Number(value || 0).toFixed(1);
    return Number(value || 0).toLocaleString("pt-BR");
  }

  window.Portal.components.renderKpiCard = function renderKpiCard(card) {
    return `
      <article class="card kpi-card">
        <div class="title">${card.title}</div>
        <div class="value">${formatValue(card.value, card.format)}</div>
      </article>
    `;
  };
})();
