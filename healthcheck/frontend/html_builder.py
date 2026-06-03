"""Geração do HTML final self-contained.

Junta template.html + CSS + JS + payload.json em um único arquivo HTML que
abre em qualquer navegador, sem dependências externas (offline-first).

O desenvolvimento é modular (vários arquivos css/js), mas a entrega é única.

Contrato:
    caminho = gerar_html(payload)
"""

from __future__ import annotations

import json
from pathlib import Path

import config

CSS_ORDER = ["base.css", "layout.css", "components.css", "pages.css"]
JS_ORDER = [
    "util.js",
    "state.js",
    "filters.js",
    "aggregate.js",
    "components/kpi.js",
    "components/table.js",
    "components/chart.js",
    "components/insight.js",
    "components/export.js",
    "components/simulator.js",
    "registry.js",
    "router.js",
    "app.js",
]


def _ler(base: Path, arquivos: list[str]) -> str:
    partes = []
    for nome in arquivos:
        caminho = base / nome
        if caminho.exists():
            partes.append(f"/* ===== {nome} ===== */\n" + caminho.read_text(encoding="utf-8"))
    return "\n\n".join(partes)


def gerar_html(payload: dict, destino: Path | None = None) -> Path:
    destino = destino or config.HTML_PATH
    destino.parent.mkdir(parents=True, exist_ok=True)

    template = (config.FRONTEND_DIR / "template.html").read_text(encoding="utf-8")
    css = _ler(config.FRONTEND_DIR / "css", CSS_ORDER)
    js = _ler(config.FRONTEND_DIR / "js", JS_ORDER)
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    # Evita que "</script>" dentro de strings do payload encerre o bloco <script>.
    payload_json = payload_json.replace("</", "<\\/")

    html = (
        template
        .replace("/*{{CSS}}*/", css)
        .replace("__HC_PAYLOAD__", payload_json)
        .replace("/*{{JS}}*/", js)
        .replace("{{TITLE}}", payload.get("meta", {}).get("titulo", "Healthcheck"))
        .replace("{{GERADO_EM}}", payload.get("meta", {}).get("gerado_em", ""))
    )

    destino.write_text(html, encoding="utf-8")
    return destino
