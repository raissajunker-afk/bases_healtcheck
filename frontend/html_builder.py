from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from config import AppConfig


CSS_FILES = [
    "css/base.css",
    "css/layout.css",
    "css/components.css",
    "css/pages.css",
]

JS_FILES = [
    "js/state.js",
    "js/filters.js",
    "js/registry.js",
    "js/components/kpi.js",
    "js/components/chart.js",
    "js/components/table.js",
    "js/components/insight.js",
    "js/components/export.js",
    "js/router.js",
    "js/pages/overview.js",
    "js/pages/coverage.js",
    "js/pages/territory.js",
    "js/pages/absence.js",
    "js/pages/governance.js",
]


def _read_assets(base_dir: Path, relative_paths: list[str]) -> str:
    chunks: list[str] = []
    for rel_path in relative_paths:
        abs_path = base_dir / rel_path
        if abs_path.exists():
            chunks.append(abs_path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def gerar_html(config: AppConfig, payload: dict[str, Any] | None = None) -> Path:
    template_path = config.project_root / "frontend" / "template.html"
    if payload is None:
        if not config.payload_path.exists():
            raise FileNotFoundError(
                f"Payload nao encontrado em {config.payload_path}. Rode sem --skip-processar para gerar."
            )
        payload = json.loads(config.payload_path.read_text(encoding="utf-8"))

    page_registry = payload.get("page_registry", {})
    frontend_dir = config.project_root / "frontend"
    inline_css = _read_assets(frontend_dir, CSS_FILES)
    inline_js = _read_assets(frontend_dir, JS_FILES)

    template = template_path.read_text(encoding="utf-8")
    html = (
        template.replace("__INLINE_CSS__", inline_css)
        .replace("__PAYLOAD_JSON__", json.dumps(payload, ensure_ascii=False))
        .replace("__PAGE_REGISTRY__", json.dumps(page_registry, ensure_ascii=False))
        .replace("__INLINE_JS__", inline_js)
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.audit_dir.mkdir(parents=True, exist_ok=True)
    config.html_output_path.write_text(html, encoding="utf-8")
    return config.html_output_path
