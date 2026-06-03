(function () {
  window.Portal = window.Portal || {};
  window.Portal.components = window.Portal.components || {};

  window.Portal.components.renderChart = function renderChart(chart) {
    const preview = (chart.data || [])
      .slice(0, 8)
      .map((item) => `${Object.values(item)[0]}: ${Object.values(item)[1]}`)
      .join(" | ");

    return `
      <article class="card">
        <h4>${chart.title}</h4>
        <p class="page-subtitle">Tipo: ${chart.type || "n/a"}</p>
        <p>${preview || "Sem dados para grafico no recorte atual."}</p>
      </article>
    `;
  };
})();
