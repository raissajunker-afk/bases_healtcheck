// Roteador e renderização de Home, Seção e Página.
HC.router = (function () {
  const view = document.getElementById("view");
  const crumb = document.getElementById("breadcrumb");

  function render(state) {
    if (state.view === "home") return renderHome();
    if (state.view === "section") return renderSection(state.sectionId);
    if (state.view === "page") return renderPage(state.pageId);
  }

  function setCrumb(parts) {
    crumb.innerHTML = "";
    parts.forEach((p, i) => {
      if (i > 0) crumb.appendChild(HC.util.el("span", "sep", "›"));
      if (p.onClick) {
        const a = HC.util.el("a", null, HC.util.escapeHtml(p.label));
        a.addEventListener("click", p.onClick);
        crumb.appendChild(a);
      } else {
        crumb.appendChild(HC.util.el("span", "current", HC.util.escapeHtml(p.label)));
      }
    });
  }

  function renderHome() {
    setCrumb([{ label: "Home" }]);
    view.innerHTML = "";
    const hero = HC.util.el("div", "home-hero");
    const meta = window.PAYLOAD.meta || {};
    hero.innerHTML = "<h1>" + HC.util.escapeHtml(meta.titulo || "Healthcheck") +
      "</h1><p>Portal analítico modular orientado a perguntas de negócio. Selecione uma macro seção para explorar sub seções e páginas analíticas. Os filtros do topo são globais e persistem entre páginas.</p>";
    view.appendChild(hero);

    const grid = HC.util.el("div", "grid grid-cards");
    HC.registry.sections().forEach((sec) => {
      const nSub = (sec.subsections || []).length;
      const card = HC.util.el("button", "section-card");
      card.innerHTML =
        "<div class='sc-ico'>" + HC.util.icon(sec.icon) + "</div>" +
        "<h3>" + HC.util.escapeHtml(sec.title) + "</h3>" +
        "<p>" + HC.util.escapeHtml(sec.descricao || "") + "</p>" +
        "<div class='sc-meta'>" + nSub + " sub seções →</div>";
      card.addEventListener("click", () => HC.state.setView("section", sec.id));
      grid.appendChild(card);
    });
    view.appendChild(grid);
  }

  function renderSection(sectionId) {
    const sec = HC.registry.section(sectionId);
    if (!sec) return renderHome();
    setCrumb([
      { label: "Home", onClick: () => HC.state.setView("home") },
      { label: sec.title },
    ]);
    view.innerHTML = "";
    const head = HC.util.el("div", "section-head");
    head.innerHTML = "<h1>" + HC.util.icon(sec.icon) + " " + HC.util.escapeHtml(sec.title) + "</h1><p>" + HC.util.escapeHtml(sec.descricao || "") + "</p>";
    view.appendChild(head);

    const grid = HC.util.el("div", "grid grid-cards");
    (sec.subsections || []).forEach((sub) => {
      const card = HC.util.el("button", "sub-card");
      card.innerHTML = "<h4>" + HC.util.escapeHtml(sub.title) + "</h4>" +
        "<p>" + HC.util.escapeHtml(sub.page.businessQuestion || "") + "</p>" +
        "<span class='arrow'>→</span>";
      card.addEventListener("click", () => HC.state.setView("page", sectionId, sub.page.id));
      grid.appendChild(card);
    });
    view.appendChild(grid);
  }

  function renderPage(pageId) {
    const entry = HC.registry.page(pageId);
    if (!entry) return renderHome();
    const { section, page } = entry;
    setCrumb([
      { label: "Home", onClick: () => HC.state.setView("home") },
      { label: section.title, onClick: () => HC.state.setView("section", section.id) },
      { label: page.subsection },
    ]);
    view.innerHTML = "";

    const back = HC.util.el("button", "back-link", "← Voltar para " + HC.util.escapeHtml(section.title));
    back.addEventListener("click", () => HC.state.setView("section", section.id));
    view.appendChild(back);

    const head = HC.util.el("div", "page-head");
    head.innerHTML =
      "<h1>" + HC.util.escapeHtml(page.title) + "</h1>" +
      "<div class='page-question'><span class='q-ico'>❓</span><div><b>" + HC.util.escapeHtml(page.businessQuestion || "") + "</b></div></div>" +
      "<div class='page-decision'>Decisão suportada: " + HC.util.escapeHtml(page.decisionSupported || "") + "</div>";
    view.appendChild(head);

    // pré-computa valores de KPIs para alimentar insights
    HC.pageKpiValues = {};
    (page.blocks || []).forEach((b) => {
      if (b.type === "kpi") HC.pageKpiValues[b.id] = HC.agg.kpiValue(b);
    });

    const grid = HC.util.el("div", "grid grid-blocks");
    (page.blocks || []).forEach((block) => {
      const renderer = HC.components[block.type];
      if (!renderer) return;
      let node;
      try { node = renderer(block); }
      catch (e) { node = HC.util.el("div", "card", "<p class='muted'>Erro ao renderizar bloco: " + HC.util.escapeHtml(block.id) + "</p>"); }
      const span = node._span || "span-12";
      const wrap = HC.util.el("div", "block " + (span === "span-3" ? "span-3" : span));
      // KPIs ficam em grade menor automática
      wrap.appendChild(node);
      grid.appendChild(wrap);
    });
    view.appendChild(grid);
  }

  return { render };
})();
