(function () {
  window.Portal = window.Portal || {};
  window.Portal.components = window.Portal.components || {};

  window.Portal.components.renderExportButton = function renderExportButton(item) {
    const target = item.target || "#";
    return `<button class="btn-export" data-export-target="${target}">${item.label || "Exportar"}</button>`;
  };
})();
