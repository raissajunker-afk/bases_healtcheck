(function () {
  window.Portal = window.Portal || {};

  function sectionsFromRegistry(pageRegistry) {
    const sections = {};
    Object.values(pageRegistry).forEach((page) => {
      if (!sections[page.sectionId]) {
        sections[page.sectionId] = {
          id: page.sectionId,
          title: page.section,
          pages: [],
        };
      }
      sections[page.sectionId].pages.push(page);
    });
    return Object.values(sections).sort((a, b) => a.title.localeCompare(b.title));
  }

  window.Portal.registry = {
    sectionsFromRegistry,
  };
})();
