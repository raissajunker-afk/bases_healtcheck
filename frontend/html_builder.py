"""Monta HTML self-contained do portal analítico."""
from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import config

TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Healthcheck Portal — __BU_TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
__CSS__
</style>
</head>
<body>
<div id="app">
  <header class="topbar">
    <div>
      <h1>Healthcheck Portal</h1>
      <div class="sub">Carregando…</div>
    </div>
    <div class="topbar-actions">
      <button class="btn btn-ghost" id="btn-home">Home</button>
    </div>
  </header>
  <div class="filters-bar">
    <div><label>GD</label><select id="f-gd"><option value="__all__">Todos</option></select></div>
    <div><label>Sales Force</label><select id="f-sf"><option value="__all__">Todas</option></select></div>
    <div><label>Consultor</label><select id="f-consultor"><option value="__all__">Todos</option></select></div>
    <div><label>Janela</label><select id="f-janela">
      <option value="mat">MAT 12m</option>
      <option value="3m">Últimos 3m</option>
      <option value="1m">Último mês</option>
      <option value="parcial">Mês parcial</option>
    </select></div>
  </div>
  <div class="breadcrumb" id="breadcrumb"></div>
  <main class="main" id="app-main"><p style="padding:20px">Carregando dados…</p></main>
</div>
<script>
const PAYLOAD_B64 = "__PAYLOAD_B64__";
const __SECTIONS_JSON__ = __SECTIONS_JSON__;
</script>
<script>
__JS__
</script>
</body>
</html>
"""


def _ler_arquivo(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def gerar_html(
    payload_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    payload_path = payload_path or config.PAYLOAD_PATH
    output_path = output_path or config.PORTAL_HTML_PATH

    payload_str = payload_path.read_text(encoding="utf-8")
    payload_bytes = payload_str.encode("utf-8")
    payload_gz = gzip.compress(payload_bytes, compresslevel=9)
    payload_b64 = base64.b64encode(payload_gz).decode("ascii")

    sections = json.loads(_ler_arquivo(config.CONFIG_DIR / "sections.json"))
    sections_js = json.dumps(sections, ensure_ascii=False)

    try:
        meta = json.loads(payload_str).get("meta", {})
        bu_title = meta.get("bu", "MSD")
    except Exception:
        bu_title = "MSD"

    css = _ler_arquivo(config.FRONTEND_DIR / "css" / "portal.css")
    js = _ler_arquivo(config.FRONTEND_DIR / "js" / "portal-app.js")

    html = (
        TEMPLATE.replace("__CSS__", css)
        .replace("__JS__", js)
        .replace("__PAYLOAD_B64__", payload_b64)
        .replace("__SECTIONS_JSON__", sections_js)
        .replace("__BU_TITLE__", bu_title.replace('"', ""))
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    mb = output_path.stat().st_size / 1024 / 1024
    print(f"  Payload: {len(payload_bytes)/1024/1024:.2f} MB → gzip+b64: {len(payload_b64)/1024/1024:.2f} MB")
    print(f"  HTML portal: {output_path} ({mb:.2f} MB)")
    return output_path
