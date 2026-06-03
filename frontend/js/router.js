(function () {
  window.Portal = window.Portal || {};

  function getSectionDescription(payload, sectionId) {
    return payload.sections?.[sectionId]?.description || "";
  }

  function getSections(payload, pageRegistry) {
    const sections = window.Portal.registry.sectionsFromRegistry(pageRegistry);
    return sections.map((section) => ({
      ...section,
      description: getSectionDescription(payload, section.id),
    }));
  }

  function updateBreadcrumb(parts) {
    document.getElementById("breadcrumb").textContent = parts.join(" > ");
  }

  function renderHome(payload, pageRegistry) {
    const sections = getSections(payload, pageRegistry);
    updateBreadcrumb(["Home"]);
    return `
      <section class="stack">
        <div class="page-heading">
          <div>
            <h2>Home</h2>
            <p class="page-subtitle">Selecione uma macro secao para navegar no portal analitico.</p>
          </div>
        </div>
        <div class="grid">
          ${sections
            .map(
              (section) => `
            <article class="card section-card" data-action="open-section" data-section-id="${section.id}">
              <h3>${section.title}</h3>
              <p class="page-subtitle">${section.description || "Sem descricao."}</p>
              <p class="page-subtitle">${section.pages.length} subsecoes mapeadas</p>
            </article>
          `
            )
            .join("")}
        </div>
      </section>
    `;
  }

  function renderSection(payload, pageRegistry, sectionId) {
    const section = getSections(payload, pageRegistry).find((item) => item.id === sectionId);
    if (!section) {
      return `<div class="empty-state">Secao nao encontrada.</div>`;
    }

    updateBreadcrumb(["Home", section.title]);
    return `
      <section class="stack">
        <div class="page-heading">
          <div>
            <h2>${section.title}</h2>
            <p class="page-subtitle">${section.description || ""}</p>
          </div>
        </div>
        <div class="grid">
          ${section.pages
            .map(
              (page) => `
            <article class="card section-card" data-action="open-page" data-page-id="${page.pageId}" data-section-id="${sectionId}">
              <h3>${page.subsection}</h3>
              <p class="page-subtitle">${page.businessQuestion}</p>
            </article>
          `
            )
            .join("")}
        </div>
      </section>
    `;
  }

  function renderPage(payload, pageRegistry, pageId) {
    const page = pageRegistry[pageId];
    if (!page) {
      return `<div class="empty-state">Pagina nao encontrada.</div>`;
    }

    const sectionData = payload.sections?.[page.sectionId] || {};
    const subsectionId = pageId.split("__")[1];
    const pageData = sectionData.pages?.[subsectionId] || {
      cards: [],
      charts: [],
      tables: [],
      insights: [],
      exports: [],
      methodology: [],
    };
    const filters = window.Portal.state.filters;
    const filterTags = Object.entries(filters)
      .map(([key, value]) => `<span class="badge">${key}: ${value}</span>`)
      .join("");

    updateBreadcrumb(["Home", page.section, page.subsection]);

    const cardsHtml = (pageData.cards || []).map(window.Portal.components.renderKpiCard).join("");
    const chartsHtml = (pageData.charts || []).map(window.Portal.components.renderChart).join("");
    const tablesHtml = (pageData.tables || []).map(window.Portal.components.renderTable).join("");
    const insightsHtml = (pageData.insights || []).map(window.Portal.components.renderInsight).join("");
    const exportsHtml = (pageData.exports || []).map(window.Portal.components.renderExportButton).join("");
    const methodologyHtml = (pageData.methodology || []).map((item) => `<li>${item}</li>`).join("");

    return `
      <section class="stack">
        <div class="page-heading">
          <div>
            <h2>${page.title}</h2>
            <p class="page-subtitle"><strong>Pergunta:</strong> ${page.businessQuestion}</p>
            <p class="page-subtitle"><strong>Decisao:</strong> ${page.decisionSupported}</p>
            <div>${filterTags}</div>
          </div>
        </div>

        ${cardsHtml ? `<div class="grid">${cardsHtml}</div>` : `<div class="empty-state">Sem KPIs configurados.</div>`}
        ${chartsHtml ? `<div class="grid">${chartsHtml}</div>` : ""}
        ${tablesHtml ? `<div class="stack">${tablesHtml}</div>` : ""}
        ${insightsHtml ? `<div class="stack">${insightsHtml}</div>` : ""}
        ${
          exportsHtml
            ? `<article class="card"><h4>Exports</h4><div>${exportsHtml}</div></article>`
            : ""
        }
        ${
          methodologyHtml
            ? `<article class="card"><h4>Metodologia</h4><ul>${methodologyHtml}</ul></article>`
            : ""
        }
      </section>
    `;
  }

  function attachActions(payload, pageRegistry, render) {
    const content = document.getElementById("app-content");
    content.querySelectorAll("[data-action='open-section']").forEach((node) => {
      node.addEventListener("click", () => {
        window.Portal.state.currentSection = node.dataset.sectionId;
        window.Portal.state.currentPageId = null;
        render();
      });
    });
    content.querySelectorAll("[data-action='open-page']").forEach((node) => {
      window.Portal.state.currentSection = node.dataset.sectionId;
      node.addEventListener("click", () => {
        window.Portal.state.currentPageId = node.dataset.pageId;
        render();
      });
    });
  }

  window.Portal.router = {
    init(payload, pageRegistry) {
      const content = document.getElementById("app-content");

      function render() {
        const { currentSection, currentPageId } = window.Portal.state;
        if (!currentSection) {
          content.innerHTML = renderHome(payload, pageRegistry);
        } else if (!currentPageId) {
          content.innerHTML = renderSection(payload, pageRegistry, currentSection);
        } else {
          content.innerHTML = renderPage(payload, pageRegistry, currentPageId);
        }
        attachActions(payload, pageRegistry, render);
      }

      window.Portal.filters.init(payload, render);
      document.getElementById("btn-home").addEventListener("click", () => {
        window.Portal.state.currentSection = null;
        window.Portal.state.currentPageId = null;
        render();
      });
      render();
    },
  };
})();
