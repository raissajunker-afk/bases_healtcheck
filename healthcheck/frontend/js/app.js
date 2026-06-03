// Bootstrap da aplicação.
(function () {
  HC.filters.buildUI();

  document.getElementById("btn-home").addEventListener("click", () => HC.state.setView("home"));

  // Re-renderiza a view atual a cada mudança de estado (navegação ou filtro).
  HC.state.onChange((state) => HC.router.render(state));

  // Render inicial.
  HC.router.render(HC.state.APP_STATE);
})();
