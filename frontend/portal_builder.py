"""
Monta o portal a partir do dashboard original (html 13.py / gerar_html_legacy.py).

Não recria KPIs nem gráficos: reutiliza CSS, BODY, vistas e todo o JavaScript
do healthcheck existente, adicionando apenas navegação tipo portal (Home → seção → página).
"""
from __future__ import annotations

import base64
import gzip
import json
import re
from pathlib import Path

import config


def _extract_raw_string(py_source: str, var_name: str) -> str:
    """Extrai variável Python do tipo VAR = r\"\"\" ... \"\"\"."""
    pattern = rf'^{re.escape(var_name)}\s*=\s*r"""(.*?)"""'
    m = re.search(pattern, py_source, re.DOTALL | re.MULTILINE)
    if not m:
        raise ValueError(f"Não encontrei {var_name} em gerar_html_legacy.py")
    return m.group(1)


def _extract_head(py_source: str) -> str:
    m = re.search(r'^HEAD\s*=\s*"""(.*?)"""', py_source, re.DOTALL | re.MULTILINE)
    if not m:
        raise ValueError("HEAD não encontrado")
    return m.group(1)


PORTAL_NAV_CSS = """
/* === Portal (camada sobre o dashboard original) === */
#portal-home{display:none;padding:8px 0 24px;}
#portal-home.active{display:block;}
#portal-breadcrumb{display:none;align-items:center;gap:6px;font-size:12px;color:var(--ink3);margin:8px 0 12px;flex-wrap:wrap;}
#portal-breadcrumb.active{display:flex;}
#portal-breadcrumb span{cursor:pointer;color:var(--teal);}
#portal-breadcrumb .sep{opacity:.5;cursor:default;color:var(--ink3);}
.portal-hero{margin-bottom:16px;}
.portal-hero h2{font-size:20px;color:var(--navy);margin:0 0 6px;}
.portal-hero p{font-size:12px;color:var(--ink3);margin:0;max-width:720px;}
.portal-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:12px;}
.portal-card{background:#fff;border:1px solid var(--lineSt);border-radius:8px;padding:14px;cursor:pointer;transition:.12s;}
.portal-card:hover{border-color:var(--teal);box-shadow:0 2px 8px rgba(0,0,0,.06);}
.portal-card h3{font-size:14px;color:var(--navy);margin:0 0 4px;}
.portal-card p{font-size:11px;color:var(--ink3);margin:0;}
.portal-subs{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-top:12px;}
.portal-sub{background:#fff;border:1px solid var(--lineSt);border-radius:6px;padding:12px;cursor:pointer;}
.portal-sub:hover{border-color:var(--navy);}
.portal-sub strong{font-size:13px;display:block;margin-bottom:4px;}
.portal-page-intro{background:#F4F8FB;border-left:3px solid var(--purple);padding:10px 14px;margin-bottom:12px;font-size:12px;}
.portal-page-intro .q{font-style:italic;color:var(--teal);}
body.portal-mode-home .controls{display:none;}
body.portal-mode-home .vista{display:none!important;}
body.portal-mode-page #portal-home{display:none!important;}
body.portal-mode-page #tab-toggle{display:none!important;}
#btn-portal-home{margin-left:8px;}
"""

PORTAL_NAV_JS = r"""
// === Navegação portal (usa setTab/renderAll do dashboard original) ===
const PORTAL_SECTIONS = __PORTAL_SECTIONS_JSON__;

function portalBuildHome(){
  const root = document.getElementById('portal-home');
  if(!root) return;
  let ins = '';
  if(typeof DATA !== 'undefined' && DATA.portal && DATA.portal.insights_global){
    ins = '<div style="margin:12px 0">' + DATA.portal.insights_global.map(i=>'<div class="portal-page-intro" style="margin-bottom:6px"><strong>'+i.type+'</strong>: '+i.text+'</div>').join('') + '</div>';
  }
  root.innerHTML = '<div class="portal-hero"><h2>Healthcheck — Portal Analítico</h2><p>Navegue por tema. Dashboard original (gráficos, tabelas, CSV). Insights da Fase 2 abaixo.</p></div>'+ins+'<div class="portal-grid" id="portal-sec-grid"></div>';
  const grid = document.getElementById('portal-sec-grid');
  (PORTAL_SECTIONS.sections||[]).forEach(sec=>{
    const card = document.createElement('div');
    card.className = 'portal-card';
    card.innerHTML = '<h3>'+(sec.icon?sec.icon+' ':'')+sec.title+'</h3><p>'+(sec.description||'')+'</p>';
    card.onclick = ()=> portalOpenSection(sec.id);
    grid.appendChild(card);
  });
}

function portalOpenSection(sectionId){
  const sec = (PORTAL_SECTIONS.sections||[]).find(s=>s.id===sectionId);
  if(!sec) return;
  ST.portal = { sectionId, pageId: null, view: 'section' };
  const root = document.getElementById('portal-home');
  root.classList.add('active');
  root.innerHTML = '<div class="portal-hero"><h2>'+sec.title+'</h2><p>'+(sec.description||'')+'</p></div><div class="portal-subs" id="portal-sub-grid"></div>';
  const grid = document.getElementById('portal-sub-grid');
  (sec.subsections||[]).forEach(sub=>{
    const el = document.createElement('div');
    el.className = 'portal-sub';
    el.innerHTML = '<strong>'+sub.title+'</strong><span style="font-size:11px;color:var(--ink3)">'+(sub.question||'')+'</span>';
    el.onclick = ()=> portalOpenPage(sectionId, sub.id);
    grid.appendChild(el);
  });
  document.body.className = 'portal-mode-home';
  portalUpdateBreadcrumb();
}

function portalOpenPage(sectionId, pageId){
  const sec = (PORTAL_SECTIONS.sections||[]).find(s=>s.id===sectionId);
  const sub = sec && (sec.subsections||[]).find(p=>p.id===pageId);
  if(!sub || !sub.legacyVista) return;
  ST.portal = { sectionId, pageId, view: 'page' };
  document.body.className = 'portal-mode-page';
  document.getElementById('portal-home').classList.remove('active');
  let intro = document.getElementById('portal-page-intro');
  if(!intro){
    intro = document.createElement('div');
    intro.id = 'portal-page-intro';
    intro.className = 'portal-page-intro';
    const ctrl = document.querySelector('.controls');
    if(ctrl) ctrl.parentNode.insertBefore(intro, ctrl.nextSibling);
  }
  intro.innerHTML = '<strong>'+sub.title+'</strong><br><span class="q">'+(sub.question||'')+'</span><br><span style="color:var(--ink3)">'+(sub.decision||'')+'</span>';
  intro.style.display = 'block';
  setTab(sub.legacyVista);
  if(sub.legacyAnchor){
    const el = document.getElementById(sub.legacyAnchor);
    if(el) setTimeout(()=> el.scrollIntoView({behavior:'smooth',block:'start'}), 120);
  }
  portalUpdateBreadcrumb();
}

function portalShowHome(){
  ST.portal = { view: 'home', sectionId: null, pageId: null };
  document.body.className = 'portal-mode-home';
  document.querySelectorAll('.vista').forEach(v=>v.classList.remove('active'));
  const intro = document.getElementById('portal-page-intro');
  if(intro) intro.style.display = 'none';
  const ph = document.getElementById('portal-home');
  ph.classList.add('active');
  portalBuildHome();
  portalUpdateBreadcrumb();
}

function portalUpdateBreadcrumb(){
  const bc = document.getElementById('portal-breadcrumb');
  if(!bc) return;
  const p = ST.portal || {};
  let html = '<span data-p="home">Home</span>';
  if(p.sectionId){
    const sec = (PORTAL_SECTIONS.sections||[]).find(s=>s.id===p.sectionId);
    html += '<span class="sep">›</span><span data-p="sec">'+(sec?sec.title:'')+'</span>';
  }
  if(p.pageId && p.sectionId){
    const sec = (PORTAL_SECTIONS.sections||[]).find(s=>s.id===p.sectionId);
    const sub = sec && (sec.subsections||[]).find(x=>x.id===p.pageId);
    html += '<span class="sep">›</span><span>'+(sub?sub.title:'')+'</span>';
  }
  bc.innerHTML = html;
  bc.classList.toggle('active', p.view !== 'home' || p.sectionId);
  bc.querySelectorAll('[data-p]').forEach(el=>{
    el.onclick = ()=>{
      const t = el.getAttribute('data-p');
      if(t==='home') portalShowHome();
      if(t==='sec' && p.sectionId) portalOpenSection(p.sectionId);
    };
  });
}

function bootPortal(){
  const banner = document.getElementById('preview-warning');
  if(banner) banner.style.display = 'none';
  ST.portal = { view: 'home', sectionId: null, pageId: null };
  patchICPFromQuarters();
  fillMeta();
  fillFilters();
  initSimInputs();
  setPairFilter('all');
  installFloatingTooltip();
  renderAll();
  refreshCenarioStatusBar();
  portalBuildHome();
  portalShowHome();
  const btn = document.getElementById('btn-portal-home');
  if(btn) btn.onclick = ()=> portalShowHome();
}
"""

PORTAL_BODY_INJECT = """
<!-- ========== PORTAL (navegação) — conteúdo analítico nas .vista abaixo ========== -->
<div id="portal-breadcrumb"></div>
<div id="portal-home" class="active"></div>
"""


def _patch_body(body: str) -> str:
    """Insere shell do portal após o header, antes dos controls."""
    marker = "<!-- CONTROLS"
    if marker not in body:
        marker = '<div class="controls">'
    idx = body.find(marker)
    if idx < 0:
        return PORTAL_BODY_INJECT + body
    return body[:idx] + PORTAL_BODY_INJECT + body[idx:]


def _patch_script(script: str) -> str:
    """Substitui boot() por bootPortal() no arranque."""
    script = script.replace("try { boot(); }", "try { bootPortal(); }")
    if "ST.portal" not in script:
        script = script.replace(
            "const ST = {",
            "const ST = {\n  portal: { view: 'home', sectionId: null, pageId: null },",
            1,
        )
    return script


def _patch_head(head: str, title_bu: str) -> str:
    head = head.replace("Healthcheck — MSD", f"Healthcheck Portal — {title_bu}")
    return head


def gerar_portal(
    payload_path: Path | None = None,
    output_path: Path | None = None,
    legacy_py: Path | None = None,
) -> Path:
    payload_path = payload_path or config.PAYLOAD_PATH
    output_path = output_path or config.PORTAL_HTML_PATH
    legacy_py = legacy_py or config.LEGACY_PY

    if not legacy_py.exists():
        raise FileNotFoundError(f"Dashboard original não encontrado: {legacy_py}")
    if not payload_path.exists():
        raise FileNotFoundError(f"payload.json não encontrado: {payload_path}")

    py_source = legacy_py.read_text(encoding="utf-8")
    css = _extract_raw_string(py_source, "CSS")
    body = _patch_body(_extract_raw_string(py_source, "BODY"))
    script = _patch_script(_extract_raw_string(py_source, "SCRIPT"))
    head = _extract_head(py_source)

    sections = json.loads((config.SECTIONS_JSON).read_text(encoding="utf-8"))
    sections_js = json.dumps(sections, ensure_ascii=False)

    payload_str = payload_path.read_text(encoding="utf-8")
    payload_gz = gzip.compress(payload_str.encode("utf-8"), compresslevel=9)
    payload_b64 = base64.b64encode(payload_gz).decode("ascii")

    try:
        bu = json.loads(payload_str).get("meta", {}).get("bu", "MSD")
    except Exception:
        bu = "MSD"

    nav_js = (
        PORTAL_NAV_JS.replace("__PORTAL_SECTIONS_JSON__", sections_js)
        + "\n"
    )
    script = script.replace("__DADOS_B64__", payload_b64)
    # Inserir portal JS antes do boot decode (após const ST definido — na verdade após decode)
    # Colocar após abertura <script> do SCRIPT (já inclui <script>)
    nav_js_block = f"<script>\n{nav_js}\n</script>\n"

    # Botão Home no header original
    body = body.replace(
        '<header class="hdr">',
        '<header class="hdr">',
        1,
    )
    if "btn-portal-home" not in body:
        body = body.replace(
            "</header>",
            '  <button type="button" class="btn-secondary" id="btn-portal-home" style="position:absolute;right:16px;top:18px;">← Home portal</button>\n</header>',
            1,
        )

    bu_safe = bu.replace('"', "")
    html = (
        f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Healthcheck Portal — {bu_safe}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
'''
        + css
        + PORTAL_NAV_CSS
        + "</style>\n</head>\n<body>\n"
        + body
        + nav_js_block
        + script
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    mb = output_path.stat().st_size / 1024 / 1024
    print(f"  Portal (dashboard original + navegação): {output_path} ({mb:.2f} MB)")
    print(f"  Bases usadas no processamento: {config.BASES_PATH}")
    return output_path
