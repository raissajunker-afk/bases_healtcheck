// Estado global único da aplicação.
HC.state = (function () {
  const APP_STATE = {
    view: "home",          // home | section | page
    sectionId: null,
    pageId: null,
    filters: {
      gd: "__all__",
      sales_force: "__all__",
      consultor: "__all__",
      janela: (window.PAYLOAD.dimensions || {}).janela_padrao || "mat",
    },
  };

  const listeners = [];
  function onChange(fn) { listeners.push(fn); }
  function emit() { listeners.forEach((fn) => fn(APP_STATE)); }

  function setView(view, sectionId, pageId) {
    APP_STATE.view = view;
    APP_STATE.sectionId = sectionId || null;
    APP_STATE.pageId = pageId || null;
    emit();
  }
  function setFilter(key, value) {
    APP_STATE.filters[key] = value;
    emit();
  }

  return { APP_STATE, onChange, emit, setView, setFilter };
})();
