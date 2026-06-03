(function () {
  window.Portal = window.Portal || {};
  window.Portal.components = window.Portal.components || {};

  window.Portal.components.renderTable = function renderTable(table) {
    const headers = table.columns || [];
    const rows = table.rows || [];
    const headHtml = headers.map((col) => `<th>${col}</th>`).join("");
    const rowHtml = rows
      .slice(0, 80)
      .map((row) => {
        const cols = headers.map((col) => `<td>${row[col] ?? ""}</td>`).join("");
        return `<tr>${cols}</tr>`;
      })
      .join("");

    return `
      <article class="card table-container">
        <h4>${table.title}</h4>
        <table>
          <thead><tr>${headHtml}</tr></thead>
          <tbody>${rowHtml || `<tr><td colspan="${headers.length || 1}">Sem dados.</td></tr>`}</tbody>
        </table>
      </article>
    `;
  };
})();
