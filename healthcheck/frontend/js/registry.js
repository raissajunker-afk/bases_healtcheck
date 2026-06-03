// Acesso ao registry de seções/subseções/páginas.
HC.registry = (function () {
  const SECTIONS = window.PAYLOAD.registry || [];
  const pageIndex = {};
  SECTIONS.forEach((sec) => (sec.subsections || []).forEach((sub) => {
    if (sub.page) pageIndex[sub.page.id] = { section: sec, sub: sub, page: sub.page };
  }));

  function sections() { return SECTIONS; }
  function section(id) { return SECTIONS.find((s) => s.id === id); }
  function page(pageId) { return pageIndex[pageId]; }
  function firstPageOf(sectionId) {
    const s = section(sectionId);
    return s && s.subsections.length ? s.subsections[0].page.id : null;
  }
  return { sections, section, page, firstPageOf };
})();
