// Utilidades globais do portal. Tudo vive sob o namespace HC.
const HC = window.HC || {};
window.HC = HC;

HC.util = (function () {
  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmt(value, format) {
    if (value == null || value === "") return "—";
    const n = typeof value === "number" ? value : parseFloat(value);
    switch (format) {
      case "percent":
        return (isNaN(n) ? value : n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })) + "%";
      case "decimal2":
        return isNaN(n) ? value : n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 2 });
      case "int":
        return isNaN(n) ? value : Math.round(n).toLocaleString("pt-BR");
      case "float":
        return isNaN(n) ? value : n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
      case "status":
        return "<span class='badge " + escapeHtml(value) + "'>" + escapeHtml(value) + "</span>";
      default:
        return escapeHtml(value);
    }
  }

  // Classe de semáforo dado um valor e um benchmark.
  function benchClass(value, bench) {
    if (!bench || value == null) return "";
    const higher = bench.higher_is_better !== false;
    if (higher) {
      if (value >= bench.good) return "good";
      if (value >= bench.warn) return "warn";
      return "bad";
    } else {
      if (value <= bench.good) return "good";
      if (value <= bench.warn) return "warn";
      return "bad";
    }
  }

  const ICONS = {
    compass: "🧭", trend: "📈", target: "🎯", calendar: "🗓️", map: "🗺️",
    clock: "⏱️", layers: "🧬", check: "✅", link: "🔗", signal: "📡",
    award: "🏆", sliders: "🎚️", flag: "🚩", database: "🗄️", shield: "🛡️",
  };
  function icon(name) { return ICONS[name] || "▣"; }

  function csvEscape(v) {
    if (v == null) return "";
    const s = String(v);
    return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  return { el, escapeHtml, fmt, benchClass, icon, csvEscape };
})();
