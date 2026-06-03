(function () {
  window.Portal = window.Portal || {};
  window.Portal.components = window.Portal.components || {};

  window.Portal.components.renderInsight = function renderInsight(insight) {
    const kind = insight.kind || "insight";
    return `
      <article class="insight">
        <span class="badge">${kind}</span>
        <span>${insight.text || "Sem insight para este recorte."}</span>
      </article>
    `;
  };
})();
