"""
gerar_html.py — Gera o relatório HTML do Healthcheck Operacional
=================================================================
Lê payload.json e produz um arquivo HTML self-contained com 6 abas:
Visão Geral · Detalhe · Ausências · Linha do Tempo · Overlap · Glossário.

Mudanças nesta versão (Blocos B + C do checklist):
- BU parametrizável (lê de meta.bu do payload — Item 36)
- Filtro hierárquico GD → Sales Force → Consultor (Item 11)
- KPIs reativos aos filtros (Item 12)
- KPIs reescritos sem "vs meta" hardcoded (Itens 13-16)
- Simulador editável de meta painel + meta vis/dia + fórmula reversa (Itens 18-19)
- Aba "Metas Customizadas" removida — virou simulador (Item 35)
- Histogramas → curvas de Gauss com data labels (Item 21)
- Tabela SF centralizada e condicional (Itens 20, 22)
- Composição de ausências em médias mensais (Itens 23-24)
- Sazonalidade: ausência linha + visitas barra (Item 25)
- Top consultores: ranking simplificado (Item 26)
- Linha do tempo: data labels (Itens 27-28)
- Painel × ausência: correlação inversa (Item 29)
- Overlap intra-time → tabela (Item 30) + tooltip (Item 17)
- Cross-team: caixas por categoria (Item 31)
- Pares enriquecidos: SF de A/B, MDM, CRM, frequência, mesmo dia, gap 3d (Itens 32-33)
- Linguagem simples no overlap (Item 34: "Jaccard" → "compartilhados")
"""

from __future__ import annotations
import json
from pathlib import Path

BUILD = Path(__file__).resolve().parent
OUT = Path(__file__).resolve().parent


# ===========================================================================
# CSS — paleta MSD-oncologia (preservado + extensões para simulador/tooltip)
# ===========================================================================
CSS = r"""
:root {
  --ink: #0C2340;
  --ink2: #2E4D6B;
  --ink3: #8A9BAD;
  --line: #D6E4ED;
  --lineSt: #A8C4D4;
  --bg: #F4F7FA;
  --card: #FFFFFF;
  --teal: #00857C;
  --teal2: #6ECEB2;
  --tealSoft: #E0F2F0;
  --purple: #6B3FA0;
  --purpleSoft: #EBE3F4;
  --danger: #C8102E;
  --dangerSoft: #FDEAED;
  --warn: #D4900A;
  --warnSoft: #FEF5E4;
  --navy: #0C2340;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:var(--ink);
  font-size:13px;line-height:1.45;padding:0;}
.wrap{max-width:1400px;margin:0 auto;padding:24px 24px 64px;}

/* HEADER */
header{display:flex;justify-content:space-between;align-items:flex-end;
  border-bottom:2px solid var(--ink);padding-bottom:14px;margin-bottom:20px;flex-wrap:wrap;gap:16px;}
.h-sub{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--purple);font-weight:700;}
.h-title{font-size:26px;font-weight:700;color:var(--navy);margin-top:4px;}
.h-meta{font-size:11px;color:var(--ink3);text-align:right;line-height:1.6;}
.h-meta strong{color:var(--ink2);}

/* CONTROLS */
.controls{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap;
  background:var(--card);border:1px solid var(--line);padding:14px 18px;margin-bottom:20px;}
.filter-group{display:flex;flex-direction:column;gap:4px;}
.flabel{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink3);font-weight:700;}
.fsel{font-family:inherit;font-size:12px;padding:6px 10px;border:1px solid var(--lineSt);
  background:#fff;color:var(--ink);min-width:200px;}
.toggle{display:flex;gap:2px;border:1px solid var(--lineSt);overflow:hidden;flex-wrap:wrap;}
.toggle button{font-family:inherit;font-size:11.5px;padding:8px 14px;border:none;
  background:#fff;color:var(--ink2);cursor:pointer;font-weight:600;letter-spacing:.02em;}
.toggle button.active{background:var(--navy);color:#fff;}
.toggle button:hover:not(.active){background:var(--bg);}

/* KPI cards */
.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:20px;}
.kpi{background:var(--card);border:1px solid var(--line);padding:14px 14px 12px;position:relative;}
.kpi-lbl{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink3);font-weight:700;line-height:1.3;}
.kpi-val{font-size:22px;font-weight:700;color:var(--navy);margin-top:4px;line-height:1;}
.kpi-sub{font-size:10.5px;color:var(--ink2);margin-top:6px;line-height:1.4;}
.kpi-tag{position:absolute;top:10px;right:10px;font-size:9px;font-weight:700;
  padding:2px 6px;text-transform:uppercase;letter-spacing:.04em;}
.kpi-tag.ok{background:var(--tealSoft);color:var(--teal);}
.kpi-tag.warn{background:var(--warnSoft);color:var(--warn);}
.kpi-tag.bad{background:var(--dangerSoft);color:var(--danger);}
.kpi.accent-teal{border-top:3px solid var(--teal);}
.kpi.accent-purple{border-top:3px solid var(--purple);}
.kpi.accent-warn{border-top:3px solid var(--warn);}
.kpi.accent-danger{border-top:3px solid var(--danger);}
.kpi.accent-navy{border-top:3px solid var(--navy);}

/* SECTIONS / BLOCKS */
section.block{background:var(--card);border:1px solid var(--line);padding:20px 22px;margin-bottom:18px;}
.eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--purple);font-weight:700;margin-bottom:4px;}
.stitle{font-size:18px;font-weight:700;color:var(--navy);margin-bottom:6px;}
.sdesc{font-size:12.5px;color:var(--ink2);margin-bottom:16px;line-height:1.6;max-width:920px;}
.sdesc strong{color:var(--ink);}

/* SIMULADOR (Item 18-19) */
.sim-box{background:#F9FBFC;border:1px solid var(--lineSt);padding:16px 18px;margin-top:14px;
  display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start;}
.sim-inputs{display:flex;flex-direction:column;gap:12px;}
.sim-row{display:flex;align-items:center;gap:10px;}
.sim-row label{font-size:12px;color:var(--ink);font-weight:600;min-width:200px;}
.sim-row input[type=number]{font-family:inherit;font-size:13px;padding:5px 8px;width:80px;
  border:1px solid var(--lineSt);background:#fff;color:var(--ink);text-align:center;font-weight:700;}
.sim-out{padding-left:18px;border-left:2px solid var(--purple);}
.sim-out-row{font-size:12px;color:var(--ink2);margin-bottom:8px;line-height:1.5;}
.sim-out-row strong{color:var(--navy);font-weight:700;}
.sim-out-row .sim-num{color:var(--purple);font-weight:700;font-size:14px;}

/* INSIGHTS */
.insights-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px;}
.insight{padding:12px 14px;border-left:3px solid var(--ink3);background:#F9FBFC;}
.insight.alta{border-left-color:var(--danger);background:var(--dangerSoft);}
.insight.media{border-left-color:var(--warn);background:var(--warnSoft);}
.insight.baixa{border-left-color:var(--teal);background:var(--tealSoft);}
.insight-titulo{font-size:13px;font-weight:700;color:var(--ink);}
.insight-detalhe{font-size:11.5px;color:var(--ink2);margin-top:3px;line-height:1.5;}

/* TABLES */
.tab-wrap{overflow-x:auto;border:1px solid var(--line);max-height:640px;overflow-y:auto;}
table.ana{width:100%;border-collapse:collapse;font-size:11.5px;background:#fff;min-width:1000px;}
table.ana th{background:var(--ink);color:#fff;padding:8px 8px;text-align:left;font-weight:600;
  letter-spacing:.02em;font-size:10.5px;text-transform:uppercase;position:sticky;top:0;z-index:1;
  cursor:pointer;white-space:nowrap;user-select:none;-webkit-user-select:none;transition:background 0.12s;}
table.ana th.num{text-align:center;}
table.ana th:hover{background:#3D4047;}
table.ana th.sa::after,table.ana th.sd::after{display:none;}  /* desativa CSS antigo de seta — sort universal usa <span class="sort-arrow"> */
/* Setinha do sort universal — mais visível */
table.ana .sort-arrow{display:inline-block;margin-left:5px;font-size:10px;opacity:0.55;font-weight:400;transition:opacity 0.12s,color 0.12s;}
table.ana th:hover .sort-arrow{opacity:1;}
table.ana td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:middle;}
table.ana tr:hover td{background:#F4F8FB;}
table.ana td.num{text-align:center;font-variant-numeric:tabular-nums;}
table.ana td.nm{font-weight:600;color:var(--navy);}
.stoplight{display:inline-block;width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:4px;}
.stoplight.ok{background:var(--teal);}
.stoplight.warn{background:var(--warn);}
.stoplight.bad{background:var(--danger);}
.stoplight.empty{background:var(--line);}
.delta-pos{color:var(--teal);font-weight:600;}
.delta-neg{color:var(--danger);font-weight:600;}
.delta-zero{color:var(--ink3);}
.tag{display:inline-block;padding:1px 6px;font-size:9.5px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;}
.tag.ok{background:var(--tealSoft);color:var(--teal);}
.tag.warn{background:var(--warnSoft);color:var(--warn);}
.tag.bad{background:var(--dangerSoft);color:var(--danger);}
.tag.neutral{background:var(--line);color:var(--ink2);}

/* TOOLTIP (Item 17) */
.tip{display:inline-block;width:14px;height:14px;border-radius:50%;background:var(--ink3);
  color:#fff;font-size:9px;font-weight:700;text-align:center;line-height:14px;cursor:help;
  margin-left:6px;position:relative;vertical-align:middle;}
/* Tooltip flutuante — renderiza no body via JS pra escapar overflow:auto do .tab-wrap */
#floating-tooltip{position:fixed;display:none;background:var(--ink);color:#fff;font-size:11.5px;
  font-weight:400;padding:9px 11px;border-radius:4px;max-width:280px;line-height:1.45;z-index:99999;
  pointer-events:none;box-shadow:0 4px 12px rgba(0,0,0,0.25);text-align:left;
  letter-spacing:0;text-transform:none;white-space:normal;}

/* BUTTONS */
.btn-exp{font-family:inherit;font-size:11.5px;padding:7px 14px;border:1px solid var(--teal);
  background:var(--teal);color:#fff;font-weight:600;cursor:pointer;letter-spacing:.02em;}
.btn-exp:hover{background:#006B63;border-color:#006B63;}
.btn-exp-sm{font-size:11px;padding:5px 10px;}
.btn-secondary{font-family:inherit;font-size:11px;padding:5px 10px;border:1px solid var(--lineSt);
  background:#fff;color:var(--ink2);cursor:pointer;font-weight:600;transition:background 0.12s,color 0.12s,border-color 0.12s;}
.btn-secondary:hover{background:var(--bg);}
.btn-secondary.active{background:var(--ink);color:#fff;border-color:var(--ink);}
.btn-secondary.active:hover{background:var(--ink2);}
.card-actions{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;flex-wrap:wrap;gap:10px;}

/* VISTAS */
.vista{display:none;}
.vista.active{display:block;}

/* CHARTS */
.chart-host{width:100%;}
.chart-host svg{display:block;width:100%;height:auto;}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:10.5px;color:var(--ink2);margin-top:8px;}
.legend-item{display:flex;align-items:center;gap:5px;}
.legend-sw{width:10px;height:10px;display:inline-block;}

/* GRID DUPLO */
.split2{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
.split3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.split4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;}

/* CARDS interno */
.card{background:#fff;border:1px solid var(--line);padding:14px 16px;}
.card-title{font-size:13px;font-weight:700;color:var(--navy);}
.card-sub{font-size:10.5px;color:var(--ink3);margin-top:2px;}
.card-num{font-size:24px;font-weight:700;color:var(--navy);margin:6px 0 4px;}
.card-num.purple{color:var(--purple);}
.card-num.teal{color:var(--teal);}
.card-num.warn{color:var(--warn);}
.card-num.danger{color:var(--danger);}

/* CATEGORY BOXES (overlap cross-team — Item 31) */
.cat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.cat-box{background:#fff;border:1px solid var(--line);padding:14px 16px;border-left:3px solid var(--ink3);}
.cat-box.coer{border-left-color:var(--teal);}
.cat-box.incoer{border-left-color:var(--danger);}
.cat-box.naoclass{border-left-color:var(--warn);}
.cat-box.exclusivo{border-left-color:var(--purple);}
.cat-box .cat-lbl{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink3);font-weight:700;}
.cat-box .cat-val{font-size:20px;font-weight:700;color:var(--navy);margin:5px 0 2px;}
.cat-box .cat-sub{font-size:10.5px;color:var(--ink2);line-height:1.4;}

/* DRILLDOWN (overlap pairs) */
.drill-row{background:#F4F8FB;}
.drill-cell{padding:10px 14px 14px;}
.drill-inner{background:#fff;border:1px solid var(--line);padding:10px 12px;max-height:280px;overflow-y:auto;}
.drill-title{font-size:11px;font-weight:700;color:var(--purple);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;}
.drill-table{width:100%;border-collapse:collapse;font-size:11px;}
.drill-table th{background:var(--ink3);color:#fff;padding:5px 7px;text-align:left;font-weight:600;font-size:10px;text-transform:uppercase;}
.drill-table td{padding:5px 7px;border-bottom:1px solid var(--line);}
.drill-table td.num{text-align:center;font-variant-numeric:tabular-nums;}

/* GLOSSÁRIO */
.gloss-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;}
.gloss-card{background:#fff;border:1px solid var(--line);padding:16px 18px;}
.gloss-card h3{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:10px;
  padding-bottom:6px;border-bottom:2px solid var(--purple);}
.gloss-item{margin-bottom:10px;}
.gloss-term{font-size:11.5px;font-weight:700;color:var(--ink);}
.gloss-def{font-size:11.5px;color:var(--ink2);line-height:1.55;margin-top:2px;}

footer{border-top:1px solid var(--lineSt);padding-top:16px;margin-top:40px;
  font-size:10.5px;color:var(--ink3);line-height:1.7;}
footer p{margin-bottom:4px;}

/* =================== NOVOS — Refator Fatia 1+2+3 =================== */

/* KPI grid 3 colunas para os cards de médicos únicos (Visão Geral) */
.kpi-grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px;}
.kpi-grid-3 .kpi{padding:14px 16px;}
.kpi-grid-3 .kpi-val{font-size:24px;}

/* Legenda do Detalhe — ícones diferenciados */
.legend-status{background:#F4F8FB;border:1px solid var(--line);
  border-left:3px solid var(--purple);padding:10px 14px;margin-bottom:12px;font-size:11.5px;}
.legend-status-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;line-height:1.6;}
.legend-status-row.hint{color:var(--ink3);margin-top:6px;font-size:11px;}
.icon-status{display:inline-block;width:14px;text-align:center;font-weight:800;font-size:13px;}
.icon-painel{color:var(--purple);}
.icon-vis{color:var(--teal);}
.icon-aus{color:var(--warn);}

/* Cabeçalhos agrupados em tabela detalhe/cenário */
table.ana thead tr.group-row th{
  padding:5px 8px;font-size:10px;text-transform:uppercase;letter-spacing:.06em;
  font-weight:700;border-bottom:1px solid var(--ink3);text-align:center;
}
table.ana thead tr.group-row th.grp-id{background:#3D5A7C;color:#fff;}
table.ana thead tr.group-row th.grp-snap{background:#6B3FA0;color:#fff;}
table.ana thead tr.group-row th.grp-mat{background:#00857C;color:#fff;}
table.ana thead tr.group-row th.grp-tri{background:#D4900A;color:#fff;}
table.ana thead tr.group-row th.grp-add{background:#8A9BAD;color:#fff;}

/* Status cell com 3 ícones (■ ▲ ●) lado a lado */
.status-cell{display:inline-flex;gap:6px;justify-content:center;align-items:center;font-size:14px;font-weight:800;}
.status-cell .s-ok{color:var(--teal);}
.status-cell .s-warn{color:var(--warn);}
.status-cell .s-bad{color:var(--danger);}
.status-cell .s-empty{color:#C8D4DC;}
.status-cell span[data-tip]{cursor:help;}

/* Setor toggle (no Simulador e Heatmap) */
.setor-toggle{display:inline-flex;border:1px solid var(--lineSt);}
.setor-toggle button{padding:5px 12px;background:#fff;color:var(--ink2);border:none;
  border-right:1px solid var(--lineSt);cursor:pointer;font-size:11px;font-weight:600;}
.setor-toggle button:last-child{border-right:none;}
.setor-toggle button.active{background:var(--ink);color:#fff;}
.setor-hm.active{background:var(--ink) !important;color:#fff !important;}

/* Categoria Viagem destacada nos cards KPI ausência */
.card.cat-viagem{border-left:4px solid var(--warn);background:#FFF8EE;}
.card.cat-viagem .card-num{color:var(--warn);}
.card.cat-pessoal{border-left:4px solid var(--danger);}
.card.cat-produtiva{border-left:4px solid var(--purple);}

/* Heatmap */
.hm-cell{stroke:#fff;stroke-width:2;}
.hm-cell-empty{fill:#F4F7FA;}

/* Aba Setor */
.split4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.card.cat-local{border-left:4px solid var(--teal);background:#E8F5F3;}
.card.cat-vint{border-left:4px solid var(--purple);background:#F4EFFA;}
.card.cat-vinter{border-left:4px solid var(--warn);background:#FFF8EE;}
.card.cat-local .card-num,.card.cat-vint .card-num,.card.cat-vinter .card-num{font-size:32px;font-weight:800;margin:6px 0;}
.flag-card{padding:14px;}
.flag-card .card-num{font-size:28px;font-weight:800;margin:6px 0;color:var(--ink);}
.card.flag-brick{border-left:4px solid #D4900A;}
.card.flag-fora{border-left:4px solid #C8102E;}
.card.flag-aus{border-left:4px solid #6B3FA0;}
.flag-tag{display:inline-block;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700;margin-right:3px;}
.flag-tag.brick{background:#D4900A;color:#fff;}
.flag-tag.fora{background:#C8102E;color:#fff;}
.flag-tag.aus{background:#6B3FA0;color:#fff;}

/* === Banner de afastados (Onda 1) === */
.afastados-banner{
  display:flex;gap:12px;align-items:flex-start;
  background:#FEF5E4;border:1px solid #D4900A;border-left:4px solid #D4900A;
  border-radius:5px;padding:10px 14px;margin-bottom:14px;font-size:12px;
}
.afastados-banner-icon{font-size:18px;color:#D4900A;line-height:1.2;}
.afastados-banner-body{flex:1;}
.afastados-banner-body strong{color:var(--ink);}
.afastados-banner-hint{font-size:11px;color:var(--ink2);margin-top:4px;line-height:1.4;}
.afastados-list-item{display:inline-block;background:#fff;border:1px solid #D4900A;border-radius:3px;padding:1px 8px;margin:2px 4px 2px 0;font-weight:600;color:#7A4D00;font-size:11.5px;}

/* Tag inline "Afastado" usada na tabela Detalhe e no Overlap */
.tag-afastado{display:inline-block;background:#D4900A;color:#fff;border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700;margin-left:6px;vertical-align:middle;}
/* Tag "MCCP não publicado" usada em Visitação e Detalhe */
.tag-mccp-na{display:inline-block;background:#8A9BAD;color:#fff;border-radius:3px;padding:1px 6px;font-size:10px;font-weight:600;}

/* Sparkline pro Movimento do time */
.sparkline-cell{display:inline-flex;align-items:center;gap:6px;font-size:11px;}
.sparkline-cell svg{flex-shrink:0;}
.spark-3m-highlight{stroke:#C8102E;stroke-width:2;fill:none;}
.spark-6m-base{stroke:#8A9BAD;stroke-width:1.5;fill:none;}
.spark-pt-3m{fill:#C8102E;}
.spark-pt-6m{fill:#8A9BAD;}

/* === Simulador novo === */
.sim-perfis{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px;}
.sim-perfil-card{background:#fff;border:1px solid var(--lineSt);border-radius:6px;padding:14px;display:flex;flex-direction:column;}
.sim-perfil-card.sim-local{border-top:4px solid var(--teal);}
.sim-perfil-card.sim-vint{border-top:4px solid var(--purple);}
.sim-perfil-card.sim-vinter{border-top:4px solid var(--warn);}
.sim-perfil-head{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;}
.sim-perfil-tag{display:inline-block;padding:4px 12px;border-radius:3px;color:#fff;font-weight:700;font-size:11px;white-space:nowrap;}
.sim-perfil-desc{font-size:11px;color:var(--ink3);flex:1;line-height:1.4;min-width:0;padding-left:4px;}
.sim-perfil-inputs{display:flex;flex-direction:column;gap:8px;margin-bottom:10px;}
.sim-input-row{display:flex;align-items:center;gap:8px;font-size:11.5px;}
.sim-input-row label{flex:1;color:var(--ink2);font-weight:500;}
.sim-input-row input[type="number"]{width:70px;padding:4px 6px;border:1px solid var(--lineSt);border-radius:3px;font-size:12px;text-align:right;}
.sim-input-row .hint{color:var(--ink3);font-size:10.5px;flex-basis:90px;font-style:italic;}
.sim-perfil-out{background:#F9FBFC;border-top:1px solid var(--line);padding:10px;border-radius:4px;font-size:11.5px;}
.sim-perfil-out .out-row{display:flex;justify-content:space-between;align-items:baseline;margin:3px 0;line-height:1.5;}
.sim-perfil-out .out-row strong{font-weight:700;color:var(--ink);}
.sim-perfil-out .out-num{font-size:20px;font-weight:800;color:var(--ink);}
.sim-perfil-out .out-num.big{font-size:26px;}
.sim-cobertura{margin-top:8px;padding:8px 10px;border-radius:4px;text-align:center;font-weight:700;}
.sim-cobertura.ok{background:#E8F5F3;color:#00857C;}
.sim-cobertura.warn{background:#FFF8EE;color:#D4900A;}
.sim-cobertura.bad{background:#FBE4E8;color:#C8102E;}
@media(max-width:760px){
  .sim-perfis{grid-template-columns:1fr;}
}

/* Layer duplicado fix: tirar o text dentro do SVG line — já foi feito no JS, aqui só garantir consistência */

@media(max-width:760px){
  .kpi-grid{grid-template-columns:repeat(2,1fr);}
  .kpi-grid-3{grid-template-columns:1fr;}
  .split2,.split3,.split4,.gloss-grid,.insights-grid,.cat-grid,.sim-box{grid-template-columns:1fr;}
  .sim-out{border-left:none;border-top:2px solid var(--purple);padding-left:0;padding-top:14px;}
}
"""


# ===========================================================================
# HTML BODY (template — dados injetados pelo JS no carregamento)
# ===========================================================================
BODY = r"""
<body>

<!-- ============================================================================
     AVISO DE PREVIEW — visível apenas em visualizadores SEM JavaScript
     (preview do WhatsApp, anexo de email, Quick Look limitado).
     O boot() do JS esconde este bloco assim que o dashboard inicia.
============================================================================ -->
<div id="preview-warning" style="
  position:fixed;top:0;left:0;right:0;bottom:0;z-index:99999;
  background:linear-gradient(135deg, #0C2340 0%, #6B3FA0 100%);
  color:#fff;display:flex;align-items:center;justify-content:center;
  padding:20px;font-family:Arial,Helvetica,sans-serif;overflow-y:auto;
">
  <div style="max-width:520px;text-align:center;width:100%;">
    <div style="font-size:13px;letter-spacing:.2em;color:#A8C4D4;text-transform:uppercase;margin-bottom:14px;font-weight:700;">
      Healthcheck MSD Oncologia
    </div>
    <div style="font-size:24px;font-weight:700;line-height:1.25;margin-bottom:20px;">
      Para ver os dados, abra este arquivo no navegador
    </div>

    <!-- iPhone -->
    <div style="background:rgba(255,255,255,0.12);border-radius:8px;padding:18px;margin-bottom:14px;text-align:left;font-size:14px;line-height:1.55;">
      <strong style="color:#6ECEB2;font-size:11.5px;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:10px;">📱 iPhone (iOS)</strong>
      <ol style="margin:0 0 0 22px;padding:0;">
        <li style="margin-bottom:6px;">Toque no ícone <strong>Compartilhar</strong> (quadrado com seta ↑)</li>
        <li style="margin-bottom:6px;">Escolha <strong>"Salvar em Arquivos"</strong></li>
        <li style="margin-bottom:6px;">Abra o app <strong>Arquivos</strong> do iPhone</li>
        <li style="margin-bottom:6px;">Toque no arquivo salvo — vai abrir no Safari automaticamente</li>
        <li style="margin-bottom:0;">Se não abrir: toque longo → Compartilhar → <strong>Abrir no Safari</strong></li>
      </ol>
    </div>

    <!-- Android -->
    <div style="background:rgba(255,255,255,0.12);border-radius:8px;padding:18px;margin-bottom:14px;text-align:left;font-size:14px;line-height:1.55;">
      <strong style="color:#6ECEB2;font-size:11.5px;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:10px;">📱 Android</strong>
      <ol style="margin:0 0 0 22px;padding:0;">
        <li style="margin-bottom:6px;">Baixe o arquivo (ícone de download)</li>
        <li style="margin-bottom:6px;">Abra <strong>Arquivos</strong> ou <strong>Downloads</strong></li>
        <li style="margin-bottom:0;">Toque no arquivo → escolha <strong>Chrome</strong> ou outro navegador</li>
      </ol>
    </div>

    <!-- Computador -->
    <div style="background:rgba(255,255,255,0.12);border-radius:8px;padding:18px;margin-bottom:18px;text-align:left;font-size:14px;line-height:1.55;">
      <strong style="color:#6ECEB2;font-size:11.5px;text-transform:uppercase;letter-spacing:.1em;display:block;margin-bottom:10px;">💻 Computador</strong>
      <div>Baixe o arquivo e abra com duplo clique (abre no navegador padrão).</div>
    </div>

    <div style="font-size:12px;color:#A8C4D4;line-height:1.5;margin-bottom:16px;">
      A prévia do WhatsApp e visualizadores rápidos <strong>não rodam JavaScript</strong>. Por isso o conteúdo aparece em branco aqui — abrir no navegador é necessário para ver gráficos, filtros, simulador e exports.
    </div>

    <div style="padding-top:16px;border-top:1px solid rgba(255,255,255,0.2);font-size:11px;color:#A8C4D4;letter-spacing:.05em;">
      Se você já está no navegador e vê esta mensagem, aguarde 1-2 segundos enquanto os dados carregam.
    </div>
  </div>
</div>

<div class="wrap">

<!-- HEADER (BU parametrizada — Item 36) -->
<header>
  <div>
    <div class="h-sub">MSD · <span id="m-bu">—</span> · Healthcheck Painel + Visitas</div>
    <div class="h-title">Healthcheck Operacional — <span id="m-bu-title">—</span></div>
  </div>
  <div class="h-meta">
    <div>Visitas: <strong id="m-janela">—</strong> · F2F Submitted</div>
    <div>Painel: snapshot <strong id="m-snapshot">—</strong></div>
    <div>MCCP: ciclo <strong id="m-ciclo">—</strong></div>
    <div>Equipe: <strong id="m-cons">—</strong> consultores ativos</div>
    <div>Gerado em: <strong id="m-gerado">—</strong></div>
  </div>
</header>

<!-- (Banner de afastados removido — informação fica apenas via tag na tabela Detalhe e glossário) -->

<!-- CONTROLS — filtro GD adicionado (Item 11) -->
<div class="controls">
  <div class="filter-group">
    <label class="flabel" for="fgd">Gerência (GD)</label>
    <select class="fsel" id="fgd"><option value="__all__">Todas</option></select>
  </div>
  <div class="filter-group">
    <label class="flabel" for="fsf">Sales Force</label>
    <select class="fsel" id="fsf"><option value="__all__">Todas</option></select>
  </div>
  <div class="filter-group">
    <label class="flabel" for="fc">Consultor</label>
    <select class="fsel" id="fc"><option value="__all__">Todo o time</option></select>
  </div>
  <button class="btn-secondary" onclick="resetFilters()" style="height:32px;align-self:flex-end;">Limpar filtros</button>
  <div style="margin-left:auto;">
    <div class="toggle" id="tab-toggle">
      <button class="active" data-tab="overview">Visão Geral</button>
      <button data-tab="detail">Detalhe por Consultor</button>
      <button data-tab="visitation">Visitação</button>
      <button data-tab="simulator">Simulador</button>
      <button data-tab="absence">Ausências</button>
      <button data-tab="setor">Deslocamento</button>
      <button data-tab="timeline">Linha do Tempo</button>
      <button data-tab="overlap">Overlap</button>
      <button data-tab="gloss">Glossário</button>
    </div>
  </div>
</div>

<!-- =================== 1. VISÃO GERAL =================== -->
<div class="vista active" id="vista-overview">

  <!-- Toggle janela global da Visão Geral (KPIs + Resumo SF + Distribuições) -->
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding:8px 12px;background:#F4F8FB;border-radius:5px;border-left:3px solid var(--purple);">
    <span style="font-size:11.5px;color:var(--ink3);font-weight:600;">Janela das métricas:</span>
    <button class="btn-secondary btn-exp-sm overview-jan active" data-jan="mat" onclick="setOverviewJanela('mat')">MAT 12m</button>
    <button class="btn-secondary btn-exp-sm overview-jan" data-jan="3m" onclick="setOverviewJanela('3m')">Últimos 3m</button>
    <button class="btn-secondary btn-exp-sm overview-jan" data-jan="1m" onclick="setOverviewJanela('1m')">Último mês fechado</button>
    <button class="btn-secondary btn-exp-sm overview-jan" data-jan="parcial" onclick="setOverviewJanela('parcial')" id="btn-jan-parcial" title="Mês corrente em andamento — visitas registradas até hoje">Mês atual (parcial)</button>
    <span id="overview-jan-info" style="margin-left:auto;font-size:10.5px;color:var(--ink3);font-style:italic;"></span>
  </div>

  <!-- KPIs principais -->
  <div class="kpi-grid" id="kpi-grid"></div>

  <!-- Distribuições estáticas (sem interação com simulador — ele virou aba) -->
  <section class="block">
    <div class="eyebrow">Distribuição</div>
    <h2 class="stitle">Como o time se distribui</h2>
    <p class="sdesc">Distribuição dos consultores filtrados. Linha tracejada interna = média do recorte. Para testar metas/cenários, use a aba <strong>Simulador</strong>.</p>
    <div class="split2">
      <div class="card">
        <div class="card-actions" style="margin-bottom:6px;">
          <div class="card-title" style="margin:0;">Tamanho de painel — distribuição</div>
          <button class="btn-exp btn-exp-sm" onclick="downloadHist('painel')">↓ CSV</button>
        </div>
        <div class="card-sub" id="hist-painel-sub">—</div>
        <div class="chart-host" id="svg-hist-painel"></div>
      </div>
      <div class="card">
        <div class="card-actions" style="margin-bottom:6px;">
          <div class="card-title" style="margin:0;">Visitas/dia (MAT) — distribuição</div>
          <button class="btn-exp btn-exp-sm" onclick="downloadHist('vis')">↓ CSV</button>
        </div>
        <div class="card-sub" id="hist-vis-sub">—</div>
        <div class="chart-host" id="svg-hist-visitas"></div>
      </div>
    </div>
  </section>

  <!-- Tabela SF -->
  <section class="block" id="sf-block">
    <div class="eyebrow">Recorte</div>
    <h2 class="stitle">Resumo por Sales Force</h2>
    <p class="sdesc">Médias agregadas por time, considerando o filtro de GD aplicado.</p>
    <div class="card-actions" style="margin-bottom:8px;">
      <div style="font-size:11.5px;color:var(--ink3);">Janela das visitas:</div>
      <div class="setor-toggle" id="sf-janela-toggle">
        <button class="active" data-jan="mat" onclick="setSfJanela('mat')">MAT 12m</button>
        <button data-jan="3m" onclick="setSfJanela('3m')">Últimos 3m</button>
        <button data-jan="1m" onclick="setSfJanela('1m')">Último mês</button>
      </div>
    </div>
    <div class="tab-wrap" style="max-height:none;">
      <table class="ana" id="tbl-sf">
        <thead><tr>
          <th>Sales Force</th>
          <th class="num">Consultores</th>
          <th class="num">Painel médio</th>
          <th class="num" id="sf-th-visdia">Visitas/dia (MAT)</th>
          <th class="num" id="sf-th-ausencia">% Ausência (MAT)</th>
          <th class="num">Viagem Interest.</th>
          <th class="num">Viagem Interna</th>
          <th class="num">Local</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- (Removida seção 'Tempo no setor × Performance do time' — não acrescentava à análise) -->
</div>

<!-- =================== 2. DETALHE POR CONSULTOR =================== -->
<div class="vista" id="vista-detail">
  <section class="block">
    <div class="eyebrow">Healthcheck individual</div>
    <h2 class="stitle">Indicadores por consultor</h2>
    <p class="sdesc">Cada linha = um consultor. Clique nos cabeçalhos para reordenar. Os indicadores estão agrupados em três janelas temporais: <strong>Snapshot</strong> (foto atual, ex.: painel), <strong>Janela selecionada</strong> (MAT 12m, últimos 3 meses ou último mês — botões abaixo), <strong>Tri atual</strong> (quarter corrente do MCCP).</p>

    <div class="card-actions">
      <div style="font-size:11.5px;color:var(--ink3);">
        Janela das colunas Vis/dia, Visitas e Ausência:
        <button class="btn-secondary btn-exp-sm detail-jan active" data-jan="mat" onclick="setDetailJanela('mat')">MAT 12m</button>
        <button class="btn-secondary btn-exp-sm detail-jan" data-jan="3m" onclick="setDetailJanela('3m')">Últimos 3 meses</button>
        <button class="btn-secondary btn-exp-sm detail-jan" data-jan="1m" onclick="setDetailJanela('1m')">Último mês</button>
        <span id="d-count" style="margin-left:8px;"></span>
      </div>
      <button class="btn-exp" onclick="exportDetalhe()">↓ Exportar Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-detail">
        <thead>
        <tr class="group-row">
          <th colspan="4" class="grp-id">Identificação</th>
          <th colspan="2" class="grp-snap">Snapshot</th>
          <th colspan="6" class="grp-mat">MAT 12m</th>
          <th colspan="4" class="grp-tri">Tri atual (MCCP)</th>
          <th colspan="3" class="grp-add">Adicionais</th>
        </tr>
        <tr>
          <th data-col="nome">Consultor</th>
          <th data-col="sales_force">Sales Force</th>
          <th data-col="gd_name">GD</th>
          <th data-col="tipo_setor">Setor</th>
          <th data-col="meses_no_setor" class="num">Meses setor</th>
          <th data-col="painel_size" class="num">Painel</th>
          <th data-col="vis_dia_media" class="num"><span id="th-vis-dia">Vis/dia</span></th>
          <th data-col="visitas_12m" class="num"><span id="th-visitas">Visitas MAT</span></th>
          <th data-col="medicos_unicos_mes" class="num">Méd. únicos/mês</th>
          <th data-col="cobertura_mensal_pct" class="num">% Cob. mensal <span class="tip" data-tip="Quanto do painel oficial é tocado em um mês típico (méd. únicos/mês ÷ painel oficial). Indica se o painel cabe na rotina mensal. ≥70% = painel cabe bem; 50-70% = OK; <50% = painel grande para a rotina."></span></th>
          <th data-col="freq_medico_mes" class="num">Freq/méd/mês</th>
          <th data-col="pct_ausencia" class="num"><span id="th-ausencia">% Ausência</span> <span class="tip" data-tip="Janela varia conforme o botão acima: MAT 12m, 3m ou 1m. NÃO significa que X% dos consultores estão fora todo dia."></span></th>
          <th data-col="mccp_panel" class="num">MCCP Painel</th>
          <th data-col="mccp_freq_media_tri" class="num">Freq/Tri planejada (MCCP) <span class="tip" data-tip="Frequência média de visita/médico/trimestre planejada no MCCP do quarter atual. Calculada como (total de visitas planejadas no trimestre ÷ médicos no plano). Anual ≈ valor × 4."></span></th>
          <th data-col="mccp_pct_cumprido" class="num">% MCCP cumprido <span class="tip" data-tip="Visitas MCCP do trimestre atual ÷ meta trimestral. Ciclo: ver glossário."></span></th>
          <th data-col="pct_dentro_mccp" class="num">% Dentro MCCP <span class="tip" data-tip="% das visitas que foram feitas a médicos com indicação MCCP no ciclo atual (não confundir com cumprimento de meta)."></span></th>
          <th data-col="pct_overlap_intra" class="num">% Overlap intra <span class="tip" data-tip="% do painel do consultor que está sendo visitado também por colega(s) da MESMA Sales Force. Esperado <10%."></span></th>
          <th data-col="pct_overlap_cross_naoclass" class="num">% Overlap cross <span class="tip" data-tip="% do painel visitado também por consultor(es) de OUTRA Sales Force. Em Oncologia é esperado (mesmo oncologista atende várias indicações)."></span></th>
          <th data-col="turnover_pct_3m" class="num">Turnover painel <span class="tip" data-tip="% médio de médicos novos por mês (média dos últimos 3 meses fechados). Mede troca de médicos no painel real. <15% = estável (constrói relacionamento); 15-30% = equilibrado; 30-50% = rotativo (atenção); >50% = volátil. Médico considerado novo = não visitado nos 3 meses anteriores."></span></th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Variabilidade no ritmo -->
  <section class="block">
    <div class="eyebrow">Variabilidade no ritmo</div>
    <h2 class="stitle">Top 5 instáveis × Top 5 consistentes</h2>
    <p class="sdesc">
      Compara consultores pela <strong>variação relativa do número de visitas/dia (CV)</strong>. Um CV alto significa que o consultor <strong>tem dias muito diferentes</strong> — provavelmente alterna semanas de viagem com semanas paradas. Um CV baixo indica <strong>rotina previsível</strong>. Consistentes são candidatos a benchmark; instáveis precisam de revisão da rotina.
    </p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportVariabilidadeMensal()">↓ CSV mês a mês (todos os consultores)</button>
    </div>
    <div class="split2" id="kpi-variabilidade">
      <!-- Card instável | Card consistente -->
    </div>
  </section>
</div>

<!-- =================== 3. VISITAÇÃO (NOVA ABA) =================== -->
<div class="vista" id="vista-visitation">

  <!-- 3 Cards Total/Dentro/Fora com toggle por quarter -->
  <section class="block">
    <div class="eyebrow">Visitação</div>
    <h2 class="stitle">Cobertura do painel — quem está sendo visitado?</h2>
    <p class="sdesc">Compara <strong>médicos no painel oficial (snapshot atual)</strong> com <strong>médicos efetivamente visitados</strong> no quarter escolhido. Médicos visitados que não estão no painel são oportunidades — talvez devam ser adicionados, talvez sejam contatos eventuais.</p>
    <div class="card-actions" style="margin-bottom:8px;">
      <div style="font-size:11.5px;color:var(--ink3);">Período:</div>
      <div class="setor-toggle" id="visit-q-toggle">
        <!-- preenchido pelo JS com base em DATA.consultores[0].quarters -->
      </div>
      <div style="font-size:11px;color:var(--ink3);margin-left:auto;" id="visit-painel-ref">
        Painel oficial: <strong>—</strong> médicos (snapshot <strong>—</strong>)
      </div>
    </div>
    <div class="kpi-grid kpi-grid-3" id="kpi-medicos"></div>
  </section>

  <!-- Tabela por Sales Force -->
  <section class="block">
    <div class="eyebrow">Por equipe</div>
    <h2 class="stitle">Cobertura de painel por Sales Force</h2>
    <p class="sdesc">Para cada SF: médicos do painel agregado, visitados na janela escolhida, e % de cobertura. Times com baixa cobertura têm painel ocioso; times com muitos médicos "fora do painel" estão visitando além do alocado.</p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportVisitSF()">↓ Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-visit-sf">
        <thead><tr>
          <th>Sales Force</th>
          <th class="num">Consultores</th>
          <th class="num">Painel do período</th>
          <th class="num">Visitados (janela)</th>
          <th class="num">Dentro painel</th>
          <th class="num">Fora painel</th>
          <th class="num">% Cobertura</th>
          <th class="num">% Fora painel</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Tabela por Consultor -->
  <section class="block">
    <div class="eyebrow">Por consultor</div>
    <h2 class="stitle">Cobertura individual de painel</h2>
    <p class="sdesc">Detalhe consultor a consultor para a janela escolhida acima.</p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportVisitConsultor()">↓ Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-visit-cons">
        <thead><tr>
          <th>Consultor</th>
          <th>SF</th>
          <th>GD</th>
          <th class="num">Painel</th>
          <th class="num">Visitados</th>
          <th class="num">Dentro painel</th>
          <th class="num">Fora painel</th>
          <th class="num">% Cobertura</th>
          <th class="num">% Fora</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Frequência por médico granular -->
  <section class="block">
    <div class="eyebrow">Padrões de frequência</div>
    <h2 class="stitle">Quantas vezes cada médico do painel é visitado?</h2>
    <p class="sdesc" id="freq-medico-desc">Dos médicos do painel oficial, quantos foram visitados 1, 2, 3, 4, 5, 6 ou 7+ vezes no período. Médicos do painel não visitados aparecem na primeira barra ("0×"). Use os botões para comparar quarters.</p>
    <div class="card-actions" style="margin-bottom:8px;">
      <div style="font-size:11.5px;color:var(--ink3);">Período:</div>
      <div class="setor-toggle" id="freq-q-toggle">
        <!-- preenchido pelo JS -->
      </div>
      <button class="btn-exp" style="margin-left:auto;" onclick="exportFreqMedico()">↓ CSV distribuição</button>
      <button class="btn-exp" onclick="exportNaoVisitados()">↓ CSV médicos não visitados</button>
    </div>
    <div class="card">
      <div id="freq-medico-header" style="font-size:12px;color:var(--ink2);margin-bottom:12px;">—</div>
      <div class="chart-host" id="freq-medico-chart"></div>
    </div>
  </section>

  <!-- Médicos sem visita há 60+ dias -->
  <section class="block">
    <div class="eyebrow">Risco de relacionamento</div>
    <h2 class="stitle">Médicos do painel sem visita há mais de 60 dias</h2>
    <p class="sdesc">
      Identifica médicos que estão no <strong>painel oficial atual</strong> mas <strong>não foram visitados nos últimos 3 meses</strong>. Quanto mais tempo sem visita, maior o risco de erosão do relacionamento.
      <br><strong>Filtros de qualidade aplicados:</strong> excluímos consultores com painel cadastrado há menos de 3 meses ou com mudança recente significativa de território (overlap &lt;50% com painel de 90 dias atrás). Esses casos não permitem medir "parados" com confiança.
    </p>
    <div class="split3" id="kpi-medicos-parados" style="margin-bottom:14px;">
      <!-- 3 cards: total parado, consultores com 10+ parados, % do painel parado -->
    </div>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportMedicosParados()">↓ CSV (médico-a-médico)</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-medicos-parados">
        <thead><tr>
          <th>Consultor</th>
          <th>SF</th>
          <th>GD</th>
          <th class="num">Painel oficial</th>
          <th class="num">Visitados últ. 3m</th>
          <th class="num">Sem visita 60+d</th>
          <th class="num">% do painel parado</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Top médicos fora do painel — candidatos a adicionar -->
  <section class="block">
    <div class="eyebrow">Oportunidade de painel</div>
    <h2 class="stitle">Top médicos fora do painel mais visitados pelo time</h2>
    <p class="sdesc">
      Médicos que <strong>não estão no painel oficial</strong> de ninguém mas estão sendo visitados frequentemente. Podem ser <strong>candidatos a adicionar oficialmente</strong> à brickagem ou estão sendo visitados por engano. Quanto mais consultores visitam o mesmo médico fora do painel, mais relevante é o caso. Ranking considera <strong>MAT 12m</strong>.
    </p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportMedicosForaPainel()">↓ CSV completo</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-medicos-fora-painel">
        <thead><tr>
          <th class="num">#</th>
          <th>MDM (médico)</th>
          <th class="num">Total visitas (MAT)</th>
          <th class="num">Consultores que visitam</th>
          <th>SFs envolvidas</th>
          <th>Status</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Visitas dentro/fora MCCP -->
  <section class="block">
    <div class="eyebrow">Aderência ao MCCP</div>
    <h2 class="stitle">Visitas dentro vs fora do plano MCCP do trimestre</h2>
    <p class="sdesc">Das visitas feitas no trimestre corrente, quantas foram para médicos planejados no MCCP e quantas foram extras. % alto fora MCCP pode indicar plano desatualizado ou prospecção. Consultores sem MCCP no Q corrente não aparecem nesta seção.</p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportVisitMCCP()">↓ Excel resumido</button>
      <button class="btn-exp" onclick="exportMCCPMedicoMedico()">↓ CSV médico-a-médico</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-visit-mccp">
        <thead><tr>
          <th>Consultor</th>
          <th>SF</th>
          <th class="num">Visitas trimestre</th>
          <th class="num">Dentro MCCP</th>
          <th class="num">Fora MCCP</th>
          <th class="num">% Dentro</th>
          <th class="num">% Fora</th>
          <th>Diagnóstico</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>
</div>

<!-- =================== 4. SIMULADOR =================== -->
<div class="vista" id="vista-simulator">

  <!-- Introdução -->
  <section class="block">
    <div class="eyebrow">Simulador de Capacidade</div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px;">
      <div style="flex:1;">
        <h2 class="stitle">Quanto cada perfil de setor consegue cobrir do painel?</h2>
        <p class="sdesc">
          A produtividade real depende do <strong>perfil de deslocamento</strong>. O modelo simula a <strong>capacidade efetiva mensal</strong> descontando dias em trânsito e a taxa de <strong>no-show</strong> (médico que cancela ou não aparece). Ajuste os parâmetros e veja quantos médicos cada perfil consegue cobrir realisticamente.
        </p>
      </div>
      <button class="btn-exp" onclick="exportSimulacaoCompleta()" style="white-space:nowrap;">↓ Excel completo</button>
    </div>
    <div style="background:#F4F8FB;border-left:3px solid var(--purple);padding:10px 14px;margin:8px 0;font-size:11.5px;color:var(--ink2);line-height:1.6;">
      <strong>Modelo de cálculo:</strong>
      <code style="background:#fff;padding:1px 4px;border-radius:2px;">Dias em campo = 20 − (deslocamento_semanal × 4)</code> ·
      <code style="background:#fff;padding:1px 4px;border-radius:2px;">Capacidade efetiva = dias × vis/dia × (1 − no-show)</code> ·
      <code style="background:#fff;padding:1px 4px;border-radius:2px;">Painel ideal = capacidade ÷ (freq mensal × cobertura)</code>.
      <br><strong>Gordura pra no-show:</strong> a margem é embutida na capacidade — o painel resultante já considera que ~10-15% das visitas não acontecem.
    </div>
  </section>

  <!-- Parâmetros por perfil -->
  <section class="block">
    <div class="eyebrow">Parâmetros por perfil</div>
    <h2 class="stitle">Configure o que se espera de cada perfil</h2>
    <p class="sdesc">Defaults baseados no racional praticado pelo time (Excel Simulacao_Cobertura): Local 0,5 dia/sem em deslocamento, Viagem Interna 0,75, Viagem Interestadual 1,5. No-show entre 10–15% conforme perfil.</p>

    <div class="sim-perfis">
      <!-- Perfil Local -->
      <div class="sim-perfil-card sim-local">
        <div class="sim-perfil-head">
          <span class="sim-perfil-tag" style="background:#00857C;">Local</span>
          <span class="sim-perfil-desc">≥80% das visitas em 1 cidade — sem tempo em trânsito relevante</span>
        </div>
        <div class="sim-perfil-inputs">
          <div class="sim-input-row">
            <label>Deslocamento (dias/semana):</label>
            <input type="number" id="sim-desloc-local" min="0" max="3" step="0.25" value="0.5" />
            <span class="hint">~0,5 dia (curtos)</span>
          </div>
          <div class="sim-input-row">
            <label>Visitas/dia (bruta):</label>
            <input type="number" id="sim-visdia-local" min="3" max="12" step="0.5" value="5" />
            <span class="hint">antes do no-show</span>
          </div>
          <div class="sim-input-row">
            <label>No-show (%):</label>
            <input type="number" id="sim-noshow-local" min="0" max="40" step="1" value="10" />
            <span class="hint">cancela / não aparece</span>
          </div>
          <div class="sim-input-row">
            <label>Freq. mensal MCCP:</label>
            <input type="number" id="sim-freq-local" min="0.5" max="6" step="0.1" value="1.0" />
            <span class="hint">visitas/médico/mês</span>
          </div>
          <div class="sim-input-row" style="border-top:1px dashed var(--lineSt);padding-top:6px;margin-top:2px;">
            <label><strong>Cobertura alvo:</strong></label>
            <input type="number" id="sim-alvo-local" min="30" max="100" step="5" value="80" />
            <span class="hint">% do painel a visitar</span>
          </div>
        </div>
        <div class="sim-perfil-out" id="sim-out-local">
          <!-- preenchido pelo JS -->
        </div>
      </div>

      <!-- Perfil Viagem Interna -->
      <div class="sim-perfil-card sim-vint">
        <div class="sim-perfil-head">
          <span class="sim-perfil-tag" style="background:#6B3FA0;">Viagem Interna</span>
          <span class="sim-perfil-desc">Várias cidades, MESMA UF — deslocamento terrestre</span>
        </div>
        <div class="sim-perfil-inputs">
          <div class="sim-input-row">
            <label>Deslocamento (dias/semana):</label>
            <input type="number" id="sim-desloc-vint" min="0" max="3" step="0.25" value="0.75" />
            <span class="hint">~0,75 dia (raio até 300km)</span>
          </div>
          <div class="sim-input-row">
            <label>Visitas/dia (bruta):</label>
            <input type="number" id="sim-visdia-vint" min="3" max="12" step="0.5" value="5" />
            <span class="hint">antes do no-show</span>
          </div>
          <div class="sim-input-row">
            <label>No-show (%):</label>
            <input type="number" id="sim-noshow-vint" min="0" max="40" step="1" value="12" />
            <span class="hint">cancela / não aparece</span>
          </div>
          <div class="sim-input-row">
            <label>Freq. mensal MCCP:</label>
            <input type="number" id="sim-freq-vint" min="0.5" max="6" step="0.1" value="1.0" />
            <span class="hint">visitas/médico/mês</span>
          </div>
          <div class="sim-input-row" style="border-top:1px dashed var(--lineSt);padding-top:6px;margin-top:2px;">
            <label><strong>Cobertura alvo:</strong></label>
            <input type="number" id="sim-alvo-vint" min="30" max="100" step="5" value="80" />
            <span class="hint">% do painel a visitar</span>
          </div>
        </div>
        <div class="sim-perfil-out" id="sim-out-vint"></div>
      </div>

      <!-- Perfil Viagem Interestadual -->
      <div class="sim-perfil-card sim-vinter">
        <div class="sim-perfil-head">
          <span class="sim-perfil-tag" style="background:#D4900A;">Viagem Interestadual</span>
          <span class="sim-perfil-desc">2+ UFs com deslocamento aéreo</span>
        </div>
        <div class="sim-perfil-inputs">
          <div class="sim-input-row">
            <label>Deslocamento (dias/semana):</label>
            <input type="number" id="sim-desloc-vinter" min="0" max="3" step="0.25" value="1.5" />
            <span class="hint">~1,5 dia (voo+embarque)</span>
          </div>
          <div class="sim-input-row">
            <label>Visitas/dia (bruta):</label>
            <input type="number" id="sim-visdia-vinter" min="3" max="12" step="0.5" value="5" />
            <span class="hint">antes do no-show</span>
          </div>
          <div class="sim-input-row">
            <label>No-show (%):</label>
            <input type="number" id="sim-noshow-vinter" min="0" max="40" step="1" value="15" />
            <span class="hint">cancela / não aparece</span>
          </div>
          <div class="sim-input-row">
            <label>Freq. mensal MCCP:</label>
            <input type="number" id="sim-freq-vinter" min="0.5" max="6" step="0.1" value="1.0" />
            <span class="hint">visitas/médico/mês</span>
          </div>
          <div class="sim-input-row" style="border-top:1px dashed var(--lineSt);padding-top:6px;margin-top:2px;">
            <label><strong>Cobertura alvo:</strong></label>
            <input type="number" id="sim-alvo-vinter" min="30" max="100" step="5" value="80" />
            <span class="hint">% do painel a visitar</span>
          </div>
        </div>
        <div class="sim-perfil-out" id="sim-out-vinter"></div>
      </div>
    </div>
    <div class="card-actions">
      <button class="btn-secondary btn-exp-sm" onclick="resetSimPerfis()">↺ Reset defaults</button>
    </div>
  </section>

  <!-- Meta universal por GD -->
  <section class="block">
    <div class="eyebrow">Capacidade por GD</div>
    <h2 class="stitle">Meta universal por gestor — ponderada pela composição do time</h2>
    <p class="sdesc">
      Cada gestor tem uma mistura diferente de perfis. A <strong>meta universal</strong> é a média ponderada do que cada perfil consegue cobrir, considerando quantos consultores de cada tipo o GD tem.
      Exemplo: GD com <em>3 Local + 5 Viagem Interna + 2 Interestadual</em> e capacidades <em>90% / 80% / 70%</em> → meta universal = <strong>82%</strong>.
    </p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportCapacidadeGD()">↓ Exportar Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-cap-gd">
        <thead><tr>
          <th>GD</th>
          <th class="num">Time</th>
          <th class="num">Local</th>
          <th class="num">V. Interna</th>
          <th class="num">V. Interestadual</th>
          <th class="num">Cobertura Local</th>
          <th class="num">Cobertura V. Interna</th>
          <th class="num">Cobertura Interestadual</th>
          <th class="num">Meta Universal</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Quem atende o alvo de cobertura -->
  <section class="block">
    <div class="eyebrow">Atingimento do alvo</div>
    <h2 class="stitle">Quem atende a cobertura alvo do seu perfil</h2>
    <p class="sdesc">
      Compara a <strong>cobertura real do painel</strong> de cada consultor (médicos únicos visitados ÷ painel oficial do quarter) com o <strong>alvo configurado no card do perfil dele</strong>. Use os botões de período para comparar momentos diferentes.
    </p>
    <div class="card-actions" style="margin-bottom:8px;">
      <div style="font-size:11.5px;color:var(--ink3);">Período:</div>
      <div class="setor-toggle" id="alvo-q-toggle">
        <!-- preenchido pelo JS -->
      </div>
      <button class="btn-exp" style="margin-left:auto;" onclick="exportAlvoPerfil()">↓ CSV</button>
    </div>
    <div class="split3" id="alvo-resumo-cards" style="margin-bottom:14px;">
      <!-- 3 cards de resumo por perfil -->
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-alvo-perfil">
        <thead><tr>
          <th>Consultor</th>
          <th>SF</th>
          <th>GD</th>
          <th>Perfil</th>
          <th class="num">Painel</th>
          <th class="num">Visitados</th>
          <th class="num">Cobertura real</th>
          <th class="num">Alvo do perfil</th>
          <th class="num">Δ</th>
          <th>Situação</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Comparativo histórico: simulado × realizado -->
  <section class="block">
    <div class="eyebrow">Histórico</div>
    <h2 class="stitle">Cobertura simulada × realizada (4 últimos trimestres)</h2>
    <p class="sdesc">
      Compara a <strong>cobertura possível</strong> (baseada nos parâmetros que você configurou no topo) com a <strong>cobertura real entregue</strong> em cada quarter. Permite avaliar a tendência de cada perfil ao longo do tempo e validar se os parâmetros refletem a realidade.
    </p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportHistComparativo()">↓ CSV</button>
    </div>
    <div class="split3" id="hist-cards">
      <!-- 3 mini-gráficos lado a lado (Local, Vint, Vinter), preenchidos pelo JS -->
    </div>
    <div style="margin-top:10px;font-size:11px;color:var(--ink3);line-height:1.5;">
      <strong>Linha sólida</strong> = % realizado (cobertura real do recorte por quarter) ·
      <strong>Linha pontilhada</strong> = % simulado (capacidade possível com os parâmetros atuais).
      Quando o realizado está acima do simulado, o time está performando melhor do que os parâmetros indicam.
    </div>
  </section>

  <!-- Painel ideal teórico -->
  <section class="block">
    <div class="eyebrow">Dimensionamento</div>
    <h2 class="stitle">Painel ideal teórico — quanto cabe na rotina real de cada consultor</h2>
    <p class="sdesc">
      Calcula o <strong>tamanho de painel que o consultor consegue cobrir</strong> dado o ritmo atual (vis/dia × dias trabalhados/mês) e a frequência mensal alvo do perfil dele. Compara com o painel oficial atual. <strong>Setores com painel maior que o ideal estão sobrecarregados</strong> — explica baixa cobertura mesmo com bom esforço. <strong>Setores com painel menor</strong> têm capacidade ociosa.
    </p>
    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportPainelIdeal()">↓ CSV</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-painel-ideal">
        <thead><tr>
          <th>Consultor</th>
          <th>SF</th>
          <th>GD</th>
          <th>Perfil</th>
          <th class="num">Painel atual</th>
          <th class="num">Vis/dia</th>
          <th class="num">Dias trab./mês</th>
          <th class="num">Painel ideal</th>
          <th class="num">Δ (ideal − atual)</th>
          <th>Status</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- (Removido: Diagnóstico por consultor — Comparação individual com o cenário simulado) -->
  <!-- (Removido: Calculadora de viagem — Distribuição planejada por UF) -->
</div>
<!-- =================== 4. AUSÊNCIAS (DEEP DIVE) =================== -->
<div class="vista" id="vista-absence">
  <!-- KPIs em médias mensais -->
  <section class="block">
    <div class="eyebrow">Deep dive · Ausências</div>
    <h2 class="stitle">Onde o tempo do time vai (média mensal)</h2>
    <p class="sdesc">Cada métrica mostra a <strong>média mensal por consultor</strong> nos últimos 12 meses. "Tempo fora do campo" agrega tudo que tira o consultor da rua. Viagem aparece em destaque pela importância da análise de deslocamento. Use o filtro de arquétipo para comparar como o tempo se distribui entre quem é Local, Viagem Interna e Viagem Interestadual.</p>

    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;padding:8px 12px;background:#F4F8FB;border-radius:5px;border-left:3px solid var(--purple);flex-wrap:wrap;">
      <span style="font-size:11.5px;color:var(--ink3);font-weight:600;">Arquétipo:</span>
      <button class="btn-secondary btn-exp-sm aus-arquetipo active" data-arq="all" onclick="setAusArquetipo('all')">Todos</button>
      <button class="btn-secondary btn-exp-sm aus-arquetipo" data-arq="Local" onclick="setAusArquetipo('Local')">Local</button>
      <button class="btn-secondary btn-exp-sm aus-arquetipo" data-arq="Viagem Interna" onclick="setAusArquetipo('Viagem Interna')">Viagem Interna</button>
      <button class="btn-secondary btn-exp-sm aus-arquetipo" data-arq="Viagem Interestadual" onclick="setAusArquetipo('Viagem Interestadual')">Viagem Interestadual</button>
      <span id="aus-arq-info" style="margin-left:auto;font-size:10.5px;color:var(--ink3);font-style:italic;"></span>
    </div>

    <div class="card-actions" style="justify-content:flex-end;margin-bottom:8px;">
      <button class="btn-exp" onclick="exportAbsKpis()">↓ CSV (KPIs)</button>
    </div>
    <div class="split3" id="abs-kpis"></div>
  </section>

  <!-- Mês típico: 2 BARRAS SEPARADAS com escalas próprias (em campo | fora) -->
  <section class="block">
    <div class="eyebrow">Composição</div>
    <h2 class="stitle">Onde vai o mês típico (em dias)</h2>
    <p class="sdesc">Duas barras separadas: <strong>em campo</strong> (escala própria, dias produtivos) e <strong>tempo fora</strong> (escala própria, desmembrada por categoria). Viagem e Treinamento contam como tempo produtivo do trabalho, mas reduzem o slot de visita. Filtro de arquétipo acima também se aplica aqui.</p>
    <div class="card">
      <div class="chart-host" id="svg-abs-comp"></div>
    </div>
  </section>

  <!-- Ausência × Cobertura de painel mensal (correlação por consultor) -->
  <section class="block">
    <div class="eyebrow">Correlação</div>
    <h2 class="stitle">Ausência × Cobertura de painel mensal</h2>
    <p class="sdesc">Cada ponto = um consultor. Eixo X = % de ausência (MAT). Eixo Y = cobertura mensal média do painel (médicos únicos visitados ÷ painel oficial). A linha pontilhada mostra a tendência: se inclina pra baixo, ausência está derrubando cobertura — quanto mais íngreme, maior o impacto. Consultores afastados são excluídos.</p>
    <div class="card">
      <div class="chart-host" id="svg-aus-cob-scatter"></div>
      <div id="aus-cob-leitura" style="margin-top:10px;font-size:11.5px;color:var(--ink2);line-height:1.5;"></div>
    </div>
  </section>

  <!-- Ranking simplificado -->
  <section class="block">
    <div class="eyebrow">Ranking</div>
    <h2 class="stitle">Consultores com maior % de ausência</h2>
    <p class="sdesc">Top 20 pelo % de ausência. Use o filtro de GD/SF acima para refinar o universo. Clique no nome para focar o filtro nesse consultor.</p>
    <div class="card-actions">
      <div style="font-size:11.5px;color:var(--ink3);">
        Janela:
        <button class="btn-secondary btn-exp-sm abs-jan active" data-jan="mat" onclick="setAbsJanela('mat')">MAT 12m</button>
        <button class="btn-secondary btn-exp-sm abs-jan" data-jan="3m" onclick="setAbsJanela('3m')">Últimos 3m</button>
        <button class="btn-secondary btn-exp-sm abs-jan" data-jan="1m" onclick="setAbsJanela('1m')">Último mês</button>
      </div>
      <button class="btn-exp" onclick="exportAusencia()">↓ Exportar Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-absence">
        <thead><tr>
          <th data-col="nome">Consultor</th>
          <th data-col="sales_force">Sales Force</th>
          <th data-col="gd_name">GD</th>
          <th data-col="trabalhados_mes" class="num">Trab./mês <span class="tip" data-tip="Média mensal: (dias úteis MAT − ausências MAT) ÷ 12."></span></th>
          <th data-col="ausencia_mes" class="num">Aus. campo/mês</th>
          <th data-col="deslocamento_mes" class="num">Viagem/mês</th>
          <th data-col="reunioes_mes" class="num">Reunião/mês</th>
          <th data-col="congressos_mes" class="num">Congresso/mês</th>
          <th data-col="treinamento_mes" class="num">Treinamento/mês</th>
          <th data-col="gestao_mes" class="num">Gestão/mês</th>
          <th data-col="pessoais_mes" class="num">Pessoal/mês</th>
          <th data-col="pct_ausencia" class="num"><span id="abs-th-pct">% Aus. (MAT)</span></th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>
</div>

<!-- =================== 5. SETOR (NOVA ABA) =================== -->
<div class="vista" id="vista-setor">

  <!-- Banner status cidade-sede -->
  <section class="block" id="sede-status-banner" style="background:#FFF8EE;border:1px solid #F0C419;padding:12px 16px;margin-bottom:14px;">
    <div style="font-size:12px;color:var(--ink2);">
      <strong>📋 Cidade sede (referência):</strong>
      <span id="sede-status-text">—</span>
      <span style="color:var(--ink3);">· A cidade sede vem do arquivo de estrutura. Consultores com sede em validação aparecem com "—" nas colunas de % vs sede e ficam fora do flag <em>Atuando fora da UF sede</em>.</span>
    </div>
  </section>

  <!-- Bloco explicativo das 3 categorias -->
  <section class="block">
    <div class="eyebrow">Como classificamos o deslocamento</div>
    <h2 class="stitle">Local, Viagem Interna e Viagem Interestadual</h2>
    <p class="sdesc">A classificação considera as <strong>visitas realmente realizadas nos últimos 12 meses</strong> usando a <strong>conta primária da visita</strong> como referência de cidade. Ou seja: olha onde o consultor de fato esteve, não onde a brickagem o aloca. O objetivo é separar setores que exigem deslocamento aéreo (alto custo) dos que rodam em um polo urbano ou em UF única.</p>
    <div class="split3" id="setor-categorias">
      <div class="card cat-local">
        <div class="card-title" style="font-size:13px;">Local</div>
        <div class="card-num" id="cat-local-n">—</div>
        <div class="card-sub">≥80% das visitas em <strong>uma única cidade</strong>. Custos de deslocamento mínimos.</div>
      </div>
      <div class="card cat-vint">
        <div class="card-title" style="font-size:13px;">Viagem Interna</div>
        <div class="card-num" id="cat-vint-n">—</div>
        <div class="card-sub">Várias cidades, mas <strong>concentrado em 1 UF</strong>. Viagens curtas, geralmente terrestres.</div>
      </div>
      <div class="card cat-vinter">
        <div class="card-title" style="font-size:13px;">Viagem Interestadual</div>
        <div class="card-num" id="cat-vinter-n">—</div>
        <div class="card-sub">2+ UFs com ≥10% das visitas. <strong>Requer aéreo</strong>, custos altos de deslocamento.</div>
      </div>
    </div>
  </section>

  <!-- KPIs do recorte -->
  <section class="block">
    <div class="eyebrow">Indicadores do recorte</div>
    <h2 class="stitle">Como o time atua no território</h2>
    <p class="sdesc">Métricas agregadas considerando o filtro aplicado. <strong>Brickagem</strong> = cidades onde o consultor está formalmente alocado no sistema. <strong>Visitadas</strong> = cidades onde ele de fato fez visita (via conta primária do registro).</p>
    <div class="split3" id="setor-kpis"></div>
  </section>

  <!-- Sinalizadores qualitativos -->
  <section class="block">
    <div class="eyebrow">Sinalizadores qualitativos</div>
    <h2 class="stitle">Gaps entre alocação e execução</h2>
    <p class="sdesc">Três flags ajudam o gestor a identificar problemas de planejamento ou execução. Use a tabela abaixo para investigar cada caso.</p>
    <div class="split3">
      <div class="card flag-card flag-brick">
        <div class="card-title"><span class="flag-tag brick">B</span> Brickagem muito ampla</div>
        <div class="card-num" id="flag-brick-n">—</div>
        <div class="card-sub">Consultor com &gt;100 cidades alocadas e cobertura &lt;10%. Indica que o desenho do território pode estar maior do que o operacionalmente viável.</div>
      </div>
      <div class="card flag-card flag-fora">
        <div class="card-title"><span class="flag-tag fora">F</span> Atuando fora da UF sede</div>
        <div class="card-num" id="flag-fora-n">—</div>
        <div class="card-sub">Menos de 50% das visitas na UF da cidade-sede registrada. Só aplica para consultores com sede definida na estrutura.</div>
      </div>
      <div class="card flag-card flag-aus">
        <div class="card-title"><span class="flag-tag aus">A</span> Ausência possivelmente subreportada</div>
        <div class="card-num" id="flag-aus-n">—</div>
        <div class="card-sub">Mais de 30 dias úteis sem visita e sem ausência lançada no MAT. Oportunidade do gestor cobrar lançamento.</div>
      </div>
    </div>
  </section>

  <!-- Tabela por consultor com cidade-sede e storytelling -->
  <section class="block">
    <div class="eyebrow">Detalhe por consultor</div>
    <h2 class="stitle">Cidade sede × Concentração real de visitas</h2>
    <p class="sdesc">Para cada consultor: cidade/UF sede (estrutura) × cobertura de cidades (brickagem) × concentração real das visitas. Por exemplo: "sede em São Paulo, 80% das visitas em São Paulo mesmo" vs "sede em Goiânia, mas 87% das visitas em Brasília". Use o export para análise de despesas de deslocamento.</p>
    <div style="background:#FEF5E4;border-left:3px solid #D4900A;padding:8px 12px;margin:8px 0 12px;font-size:11.5px;color:var(--ink2);line-height:1.5;">
      <strong style="color:#7A4D00;">⚠ Sobre as colunas "% Vis. cidade/UF sede":</strong>
      ficam em <strong>—</strong> quando o consultor não tem cidade sede preenchida na <code>estrutura.xlsx</code>.
      Apenas <span id="sede-preenchidos">42 dos 79</span> consultores têm sede definida hoje — peça à equipe responsável pela estrutura para preencher os restantes.
    </div>
    <div style="background:#F4F8FB;border-left:3px solid var(--purple);padding:8px 12px;margin:8px 0 12px;font-size:11px;color:var(--ink2);line-height:1.5;">
      <strong>Legenda das flags:</strong>
      <span class="flag-tag brick" style="margin-left:4px;">B</span> Brickagem muito ampla — &gt;100 cidades alocadas com &lt;10% de cobertura ·
      <span class="flag-tag fora">F</span> Atuando fora da UF sede — &lt;50% das visitas na UF da sede registrada ·
      <span class="flag-tag aus">A</span> Ausência possivelmente subreportada — &gt;30 dias úteis sem visita e sem ausência lançada
    </div>
    <div class="card-actions" style="margin-bottom:8px;">
      <div style="font-size:11.5px;color:var(--ink3);">Período das visitas para o cálculo das %:</div>
      <div class="setor-toggle" id="setor-jan-toggle">
        <button class="active" data-jan="mat" onclick="setSetorJanela('mat')">MAT 12m</button>
        <button data-jan="3m" onclick="setSetorJanela('3m')">Últimos 3m</button>
        <button data-jan="1m" onclick="setSetorJanela('1m')">Último mês</button>
      </div>
      <button class="btn-exp" style="margin-left:auto;" onclick="exportSetor()">↓ Exportar Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-setor">
        <thead><tr>
          <th data-col="nome">Consultor</th>
          <th data-col="sales_force">SF</th>
          <th data-col="tipo_setor">Deslocamento</th>
          <th data-col="cidade_sede">Cidade sede</th>
          <th data-col="uf_sede">UF sede</th>
          <th data-col="ufs_alocadas_n" class="num">UFs alocadas</th>
          <th data-col="cidades_alocadas_n" class="num">Cidades alocadas</th>
          <th data-col="cidades_visitadas_n" class="num">Cidades visitadas</th>
          <th data-col="pct_cobertura_cidades" class="num">% Cobertura <span class="tip" data-tip="Cidades alocadas que foram efetivamente visitadas ÷ total de cidades alocadas (brickagem)."></span></th>
          <th data-col="pct_visitas_cidade_sede" class="num">% Vis. na cidade sede</th>
          <th data-col="pct_visitas_uf_sede" class="num">% Vis. na UF sede</th>
          <th data-col="score_territorio" class="num">Score território <span class="tip" data-tip="0-100, combinando overlap intra (35%), overlap cross (10%), viagem vs perfil (20%), % UF sede (15%) e delta painel atual×ideal (20%)."></span></th>
          <th data-col="score_territorio_status">Status</th>
          <th>Flags</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <!-- Performance por UF (consultor focado) -->
  <section class="block" id="setor-perf-uf-block" style="display:none;">
    <div class="eyebrow">Performance por UF — consultor focado</div>
    <h2 class="stitle">Onde esse consultor performa melhor?</h2>
    <p class="sdesc">Quebra das visitas do consultor por UF visitada nos últimos 12 meses. Útil para entender se ele bate meta em uma UF mas tem dificuldade em outra (ex.: setor de viagem mas alta produtividade só na UF principal).</p>
    <div class="card">
      <div id="setor-perf-uf-titulo" style="font-size:13px;font-weight:700;margin-bottom:10px;"></div>
      <div class="tab-wrap">
        <table class="ana" id="tbl-perf-uf">
          <thead><tr>
            <th>UF</th>
            <th class="num">Visitas</th>
            <th class="num">Dias ativos</th>
            <th class="num">Vis/dia</th>
            <th class="num">Médicos únicos</th>
            <th>Observação</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>
</div>
<div class="vista" id="vista-timeline">
  <section class="block">
    <div class="eyebrow">Comportamento histórico</div>
    <h2 class="stitle">Evolução mensal — visitas, médicos únicos e revisitas</h2>
    <p class="sdesc">Série temporal desde Jan/24, recortada no último mês fechado. <strong>Pergunta-chave:</strong> a média de vis/dia está sendo inflada por revisitas (visitar o mesmo médico várias vezes) em vez de cobrir mais médicos únicos? Quando vis/dia sobe mas únicos não acompanham, o ritmo está vindo de revisita. Use o seletor de consultor (topo) para ver a série individual; sem filtro, mostra o time todo.</p>

    <div class="split2">
      <div class="card">
        <div class="card-title">Visitas por dia ativo</div>
        <div class="card-sub">F2F Submitted ÷ dias com visita registrada</div>
        <div class="chart-host" id="svg-tl-visdia"></div>
      </div>
      <div class="card">
        <div class="card-title">Médicos únicos × Revisitas</div>
        <div class="card-sub">Linha cheia = únicos no mês · Linha pontilhada = visitas adicionais ao mesmo médico (revisitas)</div>
        <div class="chart-host" id="svg-tl-medicos"></div>
      </div>
    </div>
    <div id="tl-revisita-leitura" style="margin-top:10px;font-size:11.5px;color:var(--ink2);line-height:1.5;"></div>
  </section>

  <section class="block">
    <div class="eyebrow">Painel + Ausência</div>
    <h2 class="stitle">Cobertura de painel × Ausência (evolução temporal)</h2>
    <p class="sdesc">Linhas sobrepostas mês a mês: <strong>cobertura mensal do painel</strong> (médicos únicos visitados ÷ painel oficial) e <strong>% de ausência</strong>. Quando cobertura cai e ausência sobe nos mesmos meses, há sinal de impacto direto da ausência na produtividade do time. Eixos independentes para facilitar a leitura.</p>
    <div class="card">
      <div class="chart-host" id="svg-cob-aus-temporal"></div>
      <div id="cob-aus-leitura" style="margin-top:10px;font-size:11.5px;color:var(--ink2);line-height:1.5;"></div>
    </div>
  </section>

  <!-- Correlação visitas/dia × ausência (mantido — análise complementar) -->
  <section class="block">
    <div class="eyebrow">Correlação</div>
    <h2 class="stitle">Ausência impacta visitas/dia?</h2>
    <p class="sdesc">Agrupamos os consultores em quatro faixas de ausência e comparamos a média de visitas/dia de cada grupo. Se ausência alta vier com visitas/dia muito baixas, o impacto está confirmado.</p>
    <div class="card">
      <div class="chart-host" id="svg-scatter"></div>
    </div>
  </section>

  <!-- Heatmap 2D: Cobertura × ausência → cor = visitas/dia -->
  <section class="block">
    <div class="eyebrow">Mapa 2D</div>
    <h2 class="stitle">Cobertura de painel × Ausência — onde está a produtividade?</h2>
    <p class="sdesc">Cada célula = consultores em uma faixa de cobertura mensal × faixa de ausência. A cor mostra a <strong>média de visitas/dia</strong> daquele grupo (verde = alta produtividade; vermelho = baixa). Use o filtro de tipo de setor para isolar populações comparáveis.</p>
    <div class="card-actions">
      <div style="font-size:11.5px;color:var(--ink3);">
        Setor:
        <button class="btn-secondary btn-exp-sm setor-hm active" data-setor="all" onclick="setHeatmapSetor('all')">Todos</button>
        <button class="btn-secondary btn-exp-sm setor-hm" data-setor="Local" onclick="setHeatmapSetor('Local')">Local</button>
        <button class="btn-secondary btn-exp-sm setor-hm" data-setor="Viagem Interna" onclick="setHeatmapSetor('Viagem Interna')">Viagem Interna</button>
        <button class="btn-secondary btn-exp-sm setor-hm" data-setor="Viagem Interestadual" onclick="setHeatmapSetor('Viagem Interestadual')">Viagem Interestadual</button>
      </div>
    </div>
    <div class="card">
      <div class="chart-host" id="svg-heatmap"></div>
    </div>
  </section>

  <!-- Tendência em alta / em queda -->
  <section class="block">
    <div class="eyebrow">Movimento do time</div>
    <h2 class="stitle">Quem está em alta e quem está em queda</h2>
    <p class="sdesc">
      Slope (inclinação da regressão linear de visitas/dia) calculado sobre os <strong>últimos 6 meses fechados</strong> (mais sensível ao momento atual que MAT 12m, mas mais robusto que 3m). O minigráfico mostra a série dos 6 meses, com os <span style="color:#C8102E;font-weight:700;">3 últimos</span> em destaque. Consultores afastados são excluídos da análise.
    </p>
    <div class="split2" id="kpi-tendencia">
      <!-- Top 10 em alta | Top 10 em queda -->
    </div>
  </section>
</div>

<!-- =================== 5. OVERLAP =================== -->
<div class="vista" id="vista-overlap">
  <!-- (Removida: "Consultores com sobreposição dentro da mesma SF" — Raissa pediu) -->

  <!-- Pares enriquecidos -->
  <section class="block">
    <div class="eyebrow">Análise de cobertura conjunta</div>
    <h2 class="stitle">Médicos visitados por mais de um consultor</h2>
    <p class="sdesc">
      Cada linha = um par de consultores que compartilham médicos. <strong>Período de referência: MAT 12m</strong> ·
      <strong>Painel comparado:</strong> universo de médicos visitados pelos dois no MAT (não o painel oficial cadastrado).
      A coluna <strong>Padrão de visita</strong> indica se os dois estão visitando o mesmo médico no mesmo dia (sinal de cobertura redundante a revisar) ou distribuindo os toques (operação saudável).
    </p>
    <div style="background:#F4F8FB;border-left:3px solid var(--purple);padding:10px 14px;margin:8px 0 14px;font-size:11.5px;color:var(--ink2);line-height:1.5;">
      <strong>Como ler:</strong>
      <span style="display:inline-block;margin:0 6px 0 4px;padding:1px 8px;background:#C8102E;color:#fff;border-radius:3px;font-weight:700;font-size:10px;">Sobreposição alta</span>
      ≥30% dos médicos compartilhados visitados pelos dois <strong>no mesmo dia</strong> (vale revisar agenda com o gestor).
      <span style="display:inline-block;margin:0 6px;padding:1px 8px;background:#D4900A;color:#fff;border-radius:3px;font-weight:700;font-size:10px;">Acompanhar</span>
      10-30%, vale monitorar.
      <span style="display:inline-block;margin:0 6px;padding:1px 8px;background:#00857C;color:#fff;border-radius:3px;font-weight:700;font-size:10px;">Distribuídos</span>
      &lt;10%, agendas independentes (saudável).
    </div>
    <div class="card-actions">
      <div style="font-size:11.5px;color:var(--ink3);">
        Tipo:
        <button class="btn-secondary btn-exp-sm" id="btn-tipo-todos" onclick="setPairFilter('all')">Todos</button>
        <button class="btn-secondary btn-exp-sm" id="btn-tipo-intra" onclick="setPairFilter('intra')">Intra-time</button>
        <button class="btn-secondary btn-exp-sm" id="btn-tipo-cross" onclick="setPairFilter('cross')">Cross-team</button>
      </div>
      <button class="btn-exp" onclick="exportPares()">↓ Exportar Excel</button>
    </div>
    <div class="tab-wrap">
      <table class="ana" id="tbl-pairs">
        <thead><tr>
          <th>Consultor A</th>
          <th>SF A</th>
          <th>Consultor B</th>
          <th>SF B</th>
          <th>Tipo</th>
          <th class="num">A: painel</th>
          <th class="num">B: painel</th>
          <th class="num">Compart. <span class="tip" data-tip="Médicos visitados pelos DOIS consultores no MAT 12m."></span></th>
          <th class="num">% sobre menor <span class="tip" data-tip="Compartilhados ÷ painel do consultor com menor painel. 10% começa a ser relevante; 20%+ é problema."></span></th>
          <th class="num">Mesmo dia <span class="tip" data-tip="Médicos visitados pelos dois consultores no MESMO DIA, ao menos uma vez."></span></th>
          <th class="num">% mesmo dia <span class="tip" data-tip="Médicos mesmo dia ÷ médicos compartilhados. Base do padrão de visita."></span></th>
          <th>Padrão de visita</th>
          <th></th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>
</div>

<!-- =================== 6. GLOSSÁRIO =================== -->
<div class="vista" id="vista-gloss">
  <section class="block">
    <div class="eyebrow">Referência</div>
    <h2 class="stitle">Glossário e regras de cálculo por aba</h2>
    <p class="sdesc">
      Aqui está a documentação resumida do que cada métrica significa, agrupada pela aba do dashboard onde ela aparece. Para <strong>reproduzir os cálculos em Excel</strong> (com fórmulas prontas e exemplos numéricos), baixe o arquivo técnico completo:
    </p>
    <div style="background:#F4F8FB;border-left:4px solid var(--purple);padding:12px 16px;margin:10px 0 16px;font-size:11.5px;color:var(--ink2);line-height:1.5;">
      <strong>📄 Arquivo complementar:</strong> existe um Excel técnico chamado <strong>Healthcheck_Formulas.xlsx</strong> com 9 abas e 52 métricas documentadas (fórmula Python + Excel reproduzível + exemplo numérico).
      <div style="margin-top:8px;">
        <button class="btn-exp" onclick="downloadFormulasXlsx()">↓ Baixar Healthcheck_Formulas.xlsx</button>
        <span style="font-size:10.5px;color:var(--ink3);margin-left:8px;font-style:italic;">Gera uma planilha com a documentação completa das fórmulas.</span>
      </div>
    </div>

    <div class="gloss-grid">

      <!-- 1. Universo & Filtros -->
      <div class="gloss-card">
        <h3>Universo & Filtros base</h3>
        <div class="gloss-item">
          <div class="gloss-term">BU = ONCOLOGIA</div>
          <div class="gloss-def">Filtro inicial do <em>estrutura.xlsx</em>: apenas linhas com coluna BU = ONCOLOGIA entram no universo.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">Hierarquia = REP</div>
          <div class="gloss-def">Apenas representantes de campo (não gestores). Coluna ACC HIERARCHY LEVEL.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">STATUS = "Ativo"</div>
          <div class="gloss-def">Match exato com "Ativo" (case-sensitive). Vazio, "ATIVO", "Afastado", etc → excluídos. Consultores não-Ativos não entram em nenhuma estatística.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">MES_FECHADO</div>
          <div class="gloss-def">Último mês completo com dados consolidados. Define a janela MAT 12m (últimos 12 meses fechados).</div>
        </div>
      </div>

      <!-- 2. Visão Geral -->
      <div class="gloss-card">
        <h3>Visão Geral</h3>
        <div class="gloss-item">
          <div class="gloss-term">painel_size (atual)</div>
          <div class="gloss-def">Médicos no painel oficial do consultor no snapshot mais recente do <em>relatorio_painel.csv</em>.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">vis_dia_media (MAT 12m)</div>
          <div class="gloss-def">Visitas F2F Submitted ÷ dias trabalhados (úteis − ausências) na janela MAT 12m.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">% Cob. mensal</div>
          <div class="gloss-def">Médicos únicos visitados num mês típico ÷ painel oficial. Cores: ≥70% verde, 50-70% neutro, &lt;50% amarelo.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">capacidade_efetiva</div>
          <div class="gloss-def">Soma das capacidades anuais (vis_dia × dias_mês × 12) sobre o time. Indica produtividade agregada.</div>
        </div>
      </div>

      <!-- 3. Detalhe -->
      <div class="gloss-card">
        <h3>Detalhe por Consultor</h3>
        <div class="gloss-item">
          <div class="gloss-term">meses_no_setor</div>
          <div class="gloss-def">Quantos meses inteiros o consultor está no setor atual (Sales Area Effective Date).</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">freq_medico_mes</div>
          <div class="gloss-def">Visitas MAT ÷ médicos únicos MAT ÷ meses ativos. Frequência média com que cada médico é visitado.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">pct_overlap_intra</div>
          <div class="gloss-def">% do painel também visitado por outro consultor da MESMA SF. Indica problema territorial. Esperado próximo de 0%.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">pct_overlap_cross</div>
          <div class="gloss-def">% do painel visitado por consultor de OUTRA SF. Em oncologia é esperado.</div>
        </div>
      </div>

      <!-- 4. Visitação -->
      <div class="gloss-card">
        <h3>Visitação</h3>
        <div class="gloss-item">
          <div class="gloss-term">painel do Quarter</div>
          <div class="gloss-def">Snapshot do painel oficial no <strong>2º mês do Q</strong> (Q1=fev/14, Q2=mai/14, Q3=ago, Q4=nov/18).</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">cobertura realizada Q</div>
          <div class="gloss-def">Médicos do painel do Q com <strong>≥1 visita</strong> no Q ÷ tamanho do painel do Q. Cada médico conta uma única vez.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">médicos parados 60+d</div>
          <div class="gloss-def">Painel atual − médicos visitados nos últimos 3m. Excluímos consultores com painel cadastrado há menos de 3 meses ou com mudança recente significativa de território.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">top fora do painel</div>
          <div class="gloss-def">Médicos visitados por algum consultor mas não estão no painel oficial de ninguém. Ranking por nº de consultores que visitam.</div>
        </div>
      </div>

      <!-- 5. Simulador -->
      <div class="gloss-card">
        <h3>Simulador</h3>
        <div class="gloss-item">
          <div class="gloss-term">cobertura simulada</div>
          <div class="gloss-def">(dias_campo_mês × 3 × vis_dia) ÷ (painel × freq_mensal × 3) × 100. Mostra quanto cabe no tri.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">dias em campo por perfil</div>
          <div class="gloss-def">Local: input direto. Vint: 4×(5−tempo_trânsito_semana). Vinter: 20−(viagens_mês × dias_por_viagem).</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">meta universal GD</div>
          <div class="gloss-def">Média ponderada das coberturas por perfil, ponderada pela composição do time do gestor.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">painel ideal teórico</div>
          <div class="gloss-def">vis_dia × dias_trabalhados_mês ÷ freq_mensal. Indica painel que cabe na rotina real.</div>
        </div>
      </div>

      <!-- 6. Linha do Tempo / Tendência -->
      <div class="gloss-card">
        <h3>Linha do Tempo & Tendência</h3>
        <div class="gloss-item">
          <div class="gloss-term">slope_vis_dia</div>
          <div class="gloss-def">Regressão linear de vis/dia ao longo dos 12 meses da janela MAT. Meses sem visita contam como 0 (não são pulados — assim afastamento é capturado corretamente).</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">tendência</div>
          <div class="gloss-def">|slope| &lt; 0.02 = Estável; slope &lt; 0 = Piorando; slope &gt; 0 = Melhorando.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">cv_vis_dia (variabilidade)</div>
          <div class="gloss-def">Desvio padrão de vis/dia mensal ÷ média × 100. CV alto = ritmo imprevisível. CV baixo = rotina consistente.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">filtro Top Alta/Queda</div>
          <div class="gloss-def">Consultor com 0 visitas nos últimos 3 meses é excluído da classificação (não dá pra dizer se está em alta ou queda — está afastado).</div>
        </div>
      </div>

      <!-- 7. Ausências -->
      <div class="gloss-card">
        <h3>Ausências</h3>
        <div class="gloss-item">
          <div class="gloss-term">% Ausência (MAT)</div>
          <div class="gloss-def">Dias ausentes ÷ dias úteis × 100 na janela MAT 12m. É média acumulada do ano (NÃO significa que X% dos consultores estão fora todo dia).</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">dias_trabalhados_mes</div>
          <div class="gloss-def">(dias úteis MAT − ausências MAT) ÷ 12. Captura sazonalidade do ano todo.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">Dedup R0/R2/R3</div>
          <div class="gloss-def">Regras para evitar dupla contagem do mesmo dia: R0 sistema vs próprio, R2 parcial vs dia inteiro, R3 subtipo conflitante.</div>
        </div>
      </div>

      <!-- 8. Deslocamento -->
      <div class="gloss-card">
        <h3>Deslocamento (Setor)</h3>
        <div class="gloss-item">
          <div class="gloss-term">tipo Local</div>
          <div class="gloss-def">≥80% das visitas em uma única cidade. Sem tempo em trânsito relevante.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">tipo Viagem Interna</div>
          <div class="gloss-def">Várias cidades na MESMA UF. Deslocamento terrestre.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">tipo Viagem Interestadual</div>
          <div class="gloss-def">2+ UFs com ≥10% das visitas em cada. Deslocamento aéreo.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">cidade_sede</div>
          <div class="gloss-def">Cidade-sede oficial cadastrada no <em>estrutura.xlsx</em>. "VERIFICAR" ou vazio → status em_validacao.</div>
        </div>
      </div>

      <!-- 9. Overlap -->
      <div class="gloss-card">
        <h3>Overlap</h3>
        <div class="gloss-item">
          <div class="gloss-term">overlap intra-SF</div>
          <div class="gloss-def">Pares de consultores da MESMA SF com médicos em comum. Esperado próximo de 0%.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">overlap cross-SF</div>
          <div class="gloss-def">Pares de SFs diferentes com médicos em comum. Em oncologia é esperado (mesmo médico atende várias indicações).</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">% mesmo dia</div>
          <div class="gloss-def">% das visitas compartilhadas no MESMO dia. ≥30% = "Visita em dupla — revisar"; 10-30% = "Acompanhar"; &lt;10% = "Distribuído".</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">% sobre o menor</div>
          <div class="gloss-def">Para um par: médicos compartilhados ÷ painel do menor. Mais intuitivo que Jaccard.</div>
        </div>
      </div>

      <!-- Convenções gerais -->
      <div class="gloss-card">
        <h3>Convenções gerais</h3>
        <div class="gloss-item">
          <div class="gloss-term">Janela MAT 12m</div>
          <div class="gloss-def">Últimos 12 meses fechados antes de MES_FECHADO. F2F + Submitted_vod + Person Account.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">Quarters</div>
          <div class="gloss-def">Q1=jan-mar, Q2=abr-jun, Q3=jul-set, Q4=out-dez. Snapshot do painel = 2º mês do Q.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">Ciclo MCCP</div>
          <div class="gloss-def">Trimestral, canal F2F. Visitas planejadas pelo consultor no início do trimestre.</div>
        </div>
        <div class="gloss-item">
          <div class="gloss-term">Calendário farma</div>
          <div class="gloss-def">Ano comercial que termina em 20/12 (~252 dias úteis). Considera feriados nacionais.</div>
        </div>
      </div>

    </div>
  </section>
</div>

<footer>
  <p><strong>Healthcheck Operacional</strong> — base MSD. Dados de painel e MCCP refletem o último snapshot/ciclo disponível; visitas e ausências consolidam os últimos 12 meses encerrados.</p>
  <p>F2F = Face to Face · MDM = Master Data Management ID do médico · MCCP = Multi-Channel Customer Plan · ISID = Identificador do consultor · GD = Gerência Distrital (Parent Sales Area).</p>
</footer>

</div>
<!-- HTML 100% offline: nenhuma dependência externa. Exports usam CSV nativo. -->
"""


# ===========================================================================
# JAVASCRIPT — render + filtros hierárquicos + simulador + exports
# ===========================================================================
SCRIPT = r"""
<script>
// === Payload comprimido (gzip + base64) — embarcado inline ===
// Estratégia: comprimir o JSON reduz o HTML em ~5×, evita truncamento em clientes (WhatsApp/iOS)
const DATA_B64 = "__DADOS_B64__";

// Descompactador: roda no boot, antes de qualquer render
async function _decodePayload(b64) {
  // base64 → bytes
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  // gzip → string
  if (typeof DecompressionStream !== 'undefined') {
    const stream = new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip')));
    const text = await stream.text();
    return JSON.parse(text);
  } else {
    // Fallback se o browser não suportar DecompressionStream (raro hoje)
    document.body.innerHTML =
      '<div style="padding:40px;font-family:Arial;color:#c8102e;font-size:14px;line-height:1.6;">' +
      '<strong>Navegador antigo detectado.</strong><br>Este arquivo usa <code>DecompressionStream</code>, suportado em Chrome 80+, Safari 16.4+, Firefox 113+. Atualize seu navegador.' +
      '</div>';
    throw new Error('DecompressionStream not supported');
  }
}

// Boot
let DATA = null;
_decodePayload(DATA_B64).then(payload => {
  DATA = payload;
  try { boot(); } catch(e) { console.error('Boot error:', e); }
}).catch(e => {
  console.error('Decode error:', e);
});

// ============================================================================
// STATE — filtros hierárquicos (Item 11) + simulador (Item 18)
// ============================================================================
const ST = {
  tab: 'overview',
  gd: '__all__',
  sales_force: '__all__',
  consultor: '__all__',
  // Sort por aba
  detail_sort: 'painel_size', detail_dir: -1,
  abs_sort: 'pct_ausencia', abs_dir: -1,
  intra_sort: 'pct_overlap_intra', intra_dir: -1,
  // Simulador
  // Simulador novo lê inputs direto via getSimParams(), não usa ST
  // Heatmap (timeline)
  hm_setor: 'all',
  // Visitação: janela MAT/3m/1m
  visit_janela: 'mat',
  // Detalhe por consultor: janela MAT/3m/1m
  detail_janela: 'mat',
  // Visão Geral: janela MAT/3m/1m (KPIs e Resumo SF)
  overview_janela: 'mat',
  // Ausências — toggle MAT/3m/1m no ranking
  abs_janela: 'mat',
  // Ausências — filtro de arquétipo no deep dive (all/Local/Viagem Interna/Viagem Interestadual)
  aus_arquetipo: 'all',
  // Atingimento alvo: quarter
  alvo_quarter: null,
  // Resumo SF: janela MAT/3m/1m
  sf_janela: 'mat',
  setor_janela: 'mat',  // Cidade sede × Concentração: MAT/3m/1m
  // Filtro de tipo dos pares
  pair_tipo: 'all',
  // Drill-down: pares expandidos
  expanded_pairs: new Set()
};

// ============================================================================
// META INFO
// ============================================================================
function fillMeta(){
  const bu = (DATA.meta.bu || '—');
  const buPretty = bu.charAt(0) + bu.slice(1).toLowerCase();
  document.getElementById('m-bu').textContent = buPretty;
  document.getElementById('m-bu-title').textContent = buPretty;
  document.title = 'Healthcheck ' + buPretty + ' — MSD';
  document.getElementById('m-janela').textContent = DATA.meta.janela_ini + ' → ' + DATA.meta.janela_fim;
  document.getElementById('m-snapshot').textContent = (DATA.meta.snapshot_painel||'').slice(0,10);
  document.getElementById('m-ciclo').textContent = DATA.meta.ciclo_mccp || '—';
  document.getElementById('m-cons').textContent = DATA.kpis.n_consultores;
  document.getElementById('m-gerado').textContent = DATA.meta.gerado_em;

  // Banner de afastados (Onda 1)
  const afastados = getAfastadosGlobal();
  const banner = document.getElementById('afastados-banner');
  const listEl = document.getElementById('afastados-list');
  if(afastados.length && banner && listEl){
    listEl.innerHTML = afastados.map(c=>
      `<span class="afastados-list-item" title="${escapeHtml(c.afastado_motivo||'')} — ${escapeHtml(c.afastado_periodo||'')}">${escapeHtml(c.nome)}</span>`
    ).join('');
    banner.style.display = 'flex';
  }
}

// ============================================================================
// FILTROS HIERÁRQUICOS — GD → SF → Consultor (Item 11)
// ============================================================================
function fillFilters(){
  // GD
  const fgd = document.getElementById('fgd');
  const gds = Array.from(new Set(DATA.consultores.map(c=>c.gd_name).filter(Boolean))).sort();
  gds.forEach(g=>{
    const o=document.createElement('option'); o.value=g; o.textContent=g;
    fgd.appendChild(o);
  });
  fgd.addEventListener('change', e=>{
    ST.gd = e.target.value;
    refreshDependentFilters();
    renderAll();
  });

  populateSFAndConsultor();

  document.getElementById('fsf').addEventListener('change', e=>{
    ST.sales_force = e.target.value;
    refreshDependentFilters(true);  // só consultor depende de SF
    renderAll();
  });
  document.getElementById('fc').addEventListener('change', e=>{
    ST.consultor = e.target.value;
    renderAll();
  });
}

function refreshDependentFilters(onlyConsultor){
  if(!onlyConsultor){
    // Reset SF if not compatible with new GD
    const validSfs = new Set(getFilteredByGD().map(c=>c.sales_force).filter(Boolean));
    if(ST.sales_force!=='__all__' && !validSfs.has(ST.sales_force)){
      ST.sales_force = '__all__';
    }
  }
  populateSFAndConsultor();
  // Reset consultor if not in filtered list
  const validIsids = new Set(getFilteredConsultores(true).map(c=>c.ISID));
  if(ST.consultor!=='__all__' && !validIsids.has(ST.consultor)){
    ST.consultor = '__all__';
    document.getElementById('fc').value = '__all__';
  }
}

function populateSFAndConsultor(){
  // Sales Force options (filtradas por GD)
  const fsf = document.getElementById('fsf');
  const prev = ST.sales_force;
  fsf.innerHTML = '<option value="__all__">Todas</option>';
  const sfs = Array.from(new Set(getFilteredByGD().map(c=>c.sales_force).filter(Boolean))).sort();
  sfs.forEach(sf=>{
    const o=document.createElement('option'); o.value=sf; o.textContent=sf;
    fsf.appendChild(o);
  });
  fsf.value = prev;

  // Consultor options (filtradas por GD + SF)
  const fc = document.getElementById('fc');
  const prevC = ST.consultor;
  fc.innerHTML = '<option value="__all__">Todo o time</option>';
  const cons = getFilteredConsultores(true).slice().sort((a,b)=>a.nome.localeCompare(b.nome,'pt-BR'));
  cons.forEach(c=>{
    const o=document.createElement('option'); o.value=c.ISID;
    o.textContent = c.nome;
    fc.appendChild(o);
  });
  fc.value = prevC;
}

function getFilteredByGD(){
  if(ST.gd==='__all__') return DATA.consultores;
  return DATA.consultores.filter(c=>c.gd_name===ST.gd);
}

function getFilteredConsultores(ignoreConsultor){
  let arr = getFilteredByGD();
  if(ST.sales_force!=='__all__') arr = arr.filter(c=>c.sales_force===ST.sales_force);
  if(!ignoreConsultor && ST.consultor!=='__all__') arr = arr.filter(c=>c.ISID===ST.consultor);
  return arr;
}

// === NOVO: utilitários para tratar consultores AFASTADOS ===
// Política (conforme decisão do healthcheck):
//  - Tabela Detalhe: MANTÉM com tag visual "Afastado"
//  - Médias, medianas, histogramas, distribuições, rankings, correlações: EXCLUI
//  - Overlap par-a-par: mantém (marca o par)
function isAfastado(c){ return !!(c && c.afastado === true); }

// Para agregados/rankings/distribuições — use sempre esta função em vez de getFilteredAtivos
// === Helpers para Nome + CRM dos médicos (Onda 2 — fonte: relatorio_1030.csv) ===
function mdMeta(mdm){
  // Retorna {nome, crm, tipo, especialidade} ou objeto vazio se não houver match.
  // payload.medicos_meta é dict {mdm_id: {nome, crm, ...}}.
  if(!DATA.medicos_meta) return {nome:'', crm:'', tipo:'', especialidade:''};
  return DATA.medicos_meta[mdm] || {nome:'', crm:'', tipo:'', especialidade:''};
}
function mdNomeCrm(mdm){
  // Renderiza "Nome (CRM)" — útil quando aparece inline numa célula.
  const m = mdMeta(mdm);
  if(m.nome && m.crm) return `${m.nome} (${m.crm})`;
  if(m.nome) return m.nome;
  if(m.crm) return `CRM ${m.crm}`;
  return mdm;
}

// === Resolve painel do quarter com FALLBACK pro painel atual do consultor ===
// Quando o snapshot daquele quarter não tem o consultor (entrou depois, ou painel oficial
// só veio mais tarde), qc.painel_mdms vem vazio — e 100% das visitas aparecem "fora do painel".
// Esta função é a única fonte de verdade pra "painel daquele quarter".
function getPainelMdms(c, qc){
  if(qc && qc.painel_mdms && qc.painel_mdms.length > 0) return qc.painel_mdms;
  // Fallback 1: painel oficial atual do consultor
  if(c && c.mdms_painel && c.mdms_painel.length > 0) return c.mdms_painel;
  // Fallback 2: proxy 90d (só usado em pipeline, mas guardamos defensivo)
  if(c && c.mdms_proxy_90d && c.mdms_proxy_90d.length > 0) return c.mdms_proxy_90d;
  return [];
}

function getFilteredAtivos(ignoreConsultor){
  return getFilteredConsultores(ignoreConsultor).filter(c=>!isAfastado(c));
}

// Lista global (sem filtro de UI) dos afastados — pra banners e legendas
function getAfastadosGlobal(){
  return (DATA.consultores||[]).filter(isAfastado);
}

function resetFilters(){
  ST.gd='__all__'; ST.sales_force='__all__'; ST.consultor='__all__';
  document.getElementById('fgd').value='__all__';
  populateSFAndConsultor();
  renderAll();
}

// ============================================================================
// HELPERS
// ============================================================================
function fmt(v, dec){
  if(v===null||v===undefined||isNaN(v)) return '—';
  return Number(v).toLocaleString('pt-BR',{minimumFractionDigits:dec||0, maximumFractionDigits:dec||0});
}
function pct(v){ if(v===null||v===undefined||isNaN(v)) return '—'; return Number(v).toFixed(1)+'%'; }
function pctInt(v){ if(v===null||v===undefined||isNaN(v)) return '—'; return Math.round(Number(v))+'%'; }
function mean(arr){ if(!arr.length) return 0; return arr.reduce((a,b)=>a+(b||0),0)/arr.length; }
function sum(arr){ return arr.reduce((a,b)=>a+(b||0),0); }
function stoplight(state){
  const cls = (state==='ok')?'ok':(state==='warn')?'warn':(state==='bad')?'bad':'empty';
  return '<span class="stoplight '+cls+'"></span>';
}
function escapeHtml(s){
  return String(s||'').replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
}
// Converte "2024-01" -> "Jan/24"
function fmtMonth(ym){
  if(!ym) return '';
  const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const m = String(ym).match(/^(\d{4})-(\d{1,2})/);
  if(!m) return ym;
  const idx = parseInt(m[2],10)-1;
  if(idx<0||idx>11) return ym;
  return meses[idx] + '/' + m[1].slice(2);
}
// Corta série em ym <= último mês fechado (anterior ao snapshot)
function lastClosedMonth(){
  const snap = (DATA.meta && DATA.meta.snapshot_painel) ? String(DATA.meta.snapshot_painel) : '';
  const m = snap.match(/^(\d{4})-(\d{1,2})/);
  if(!m) return '9999-12';
  let y = parseInt(m[1],10), mo = parseInt(m[2],10) - 1;
  if(mo<1){ mo=12; y-=1; }
  return y + '-' + String(mo).padStart(2,'0');
}
function clipToCurrent(rows){
  const cut = lastClosedMonth();
  return rows.filter(r => r.ym && r.ym <= cut);
}
function nice(x){
  if(x<=0) return 1;
  const mag=Math.pow(10,Math.floor(Math.log10(x)));
  for(const m of [1,2,2.5,5,10]) if(m*mag>=x) return m*mag;
  return 10*mag;
}
// Status helpers usando simulador
function statusPainel(p){
  if(!p) return 'empty';
  if(p>=ST.sim_painel) return 'ok';
  if(p>=ST.sim_painel*0.9) return 'warn';
  return 'bad';
}
function statusVis(v){
  if(!v) return 'empty';
  if(v>=ST.sim_visdia) return 'ok';
  if(v>=ST.sim_visdia*0.85) return 'warn';
  return 'bad';
}
function statusAus(p){
  if(p===null||p===undefined) return 'empty';
  if(p<=15) return 'ok';
  if(p<=22) return 'warn';
  return 'bad';
}

// ============================================================================
// KPIs REATIVOS AO FILTRO (Items 12-16)
// ============================================================================
function computeAggregates(){
  const cs = getFilteredAtivos();
  const csPainel = cs.filter(c=>c.painel_size>0);

  // Selecionar campo de vis/dia, ausência e visitas conforme janela escolhida na Visão Geral
  const jan = ST.overview_janela || 'mat';
  const visField = jan === '3m'      ? 'vis_dia_3m'
                  : jan === '1m'      ? 'vis_dia_1m'
                  : jan === 'parcial' ? 'vis_dia_parcial'
                  : 'vis_dia_media';
  const ausField = jan === '3m'      ? 'pct_ausencia_3m'
                  : jan === '1m'      ? 'pct_ausencia_1m'
                  : jan === 'parcial' ? 'pct_ausencia_parcial'
                  : 'pct_ausencia';
  const visitasField = jan === '3m'      ? 'visitas_3m'
                       : jan === '1m'      ? 'visitas_1m'
                       : jan === 'parcial' ? 'visitas_parcial'
                       : 'visitas_12m';

  const csVis = cs.filter(c=>(c[visField]||0) > 0);
  const csAus = cs.filter(c=>c[ausField]!==null && c[ausField]!==undefined && c[ausField]>0);
  const csTrab = cs.filter(c=>c.dias_trabalhados_mes>0);
  const csMed = cs.filter(c=>c.medicos_unicos_mes>0);
  const csFreq = cs.filter(c=>c.freq_medico_mes>0);
  const csOvl = cs.filter(c=>c.pct_overlap_intra!==null);
  const csSet = cs.filter(c=>c.meses_no_setor!==null && c.meses_no_setor!==undefined);
  let medSet = null;
  if(csSet.length){
    const arr = csSet.map(c=>c.meses_no_setor).sort((a,b)=>a-b);
    medSet = arr[Math.floor(arr.length/2)];
  }
  return {
    cs, n: cs.length, janela: jan,
    painel_medio: csPainel.length? mean(csPainel.map(c=>c.painel_size)) : null,
    painel_n: csPainel.length,
    vis_dia_medio: csVis.length? mean(csVis.map(c=>c[visField])) : null,
    vis_dia_n: csVis.length,
    visitas_12m_total: sum(cs.map(c=>c[visitasField]||0)),
    medicos_unicos_mes_medio: csMed.length? mean(csMed.map(c=>c.medicos_unicos_mes)) : null,
    freq_medico_mes_medio: csFreq.length? mean(csFreq.map(c=>c.freq_medico_mes)) : null,
    pct_ausencia_medio: csAus.length? mean(csAus.map(c=>c[ausField])) : null,
    dias_trab_mes_medio: csTrab.length? mean(csTrab.map(c=>c.dias_trabalhados_mes)) : null,
    pct_em_campo: csTrab.length? mean(csTrab.map(c=>c.pct_trabalhados||0)) : null,
    overlap_intra_medio: csOvl.length? mean(csOvl.map(c=>c.pct_overlap_intra)) : null,
    meses_setor_mediano: medSet
  };
}

// Onda 4 — toggle janela na Visão Geral
function setOverviewJanela(j){
  ST.overview_janela = j;
  document.querySelectorAll('.overview-jan').forEach(b=>{
    b.classList.toggle('active', b.dataset.jan===j);
  });
  const info = document.getElementById('overview-jan-info');
  if(info){
    if(j === 'parcial'){
      const c0 = (DATA.consultores||[])[0];
      const dias = c0 ? c0.parcial_dias_decorridos : 0;
      const ym = c0 ? c0.parcial_ym : '';
      info.textContent = `Mês ${ym} · ${dias} dias úteis decorridos (parcial)`;
    } else {
      info.textContent = j === '3m' ? 'Últimos 3 meses fechados'
                       : j === '1m' ? 'Último mês fechado (mar/26 para visitas, abr/26 para painel)'
                       : 'MAT 12 meses fechados';
    }
  }
  renderKPIs();
  renderSF();
  renderHistograms();
}

function renderKPIs(){
  const A = computeAggregates();
  const meta = DATA.meta;
  const isSingle = ST.consultor!=='__all__';
  const subN = isSingle? 'consultor' : (A.n + ' consultores');
  const janSigla = A.janela === '3m' ? '3M'
                 : A.janela === '1m' ? '1M'
                 : A.janela === 'parcial' ? 'PARCIAL'
                 : 'MAT';
  const sigla = janSigla;

  // === GRID PRINCIPAL ===
  const items = [
    {
      lbl: isSingle? 'Consultor focado' : 'Consultores no recorte',
      val: isSingle? '1' : A.n,
      sub: isSingle? (A.cs[0]? A.cs[0].sales_force : '') :
           (ST.gd==='__all__'? 'Universo: ' + DATA.kpis.n_consultores : 'GD ' + ST.gd),
      cls: 'accent-navy'
    },
    {
      lbl: 'Painel médio (snapshot)',
      val: A.painel_medio!==null? fmt(A.painel_medio,1) : '—',
      sub: A.painel_n + ' com painel · faixa ' +
           (A.painel_medio!==null? (fmt(Math.min(...A.cs.filter(c=>c.painel_size>0).map(c=>c.painel_size)))+' → '+fmt(Math.max(...A.cs.filter(c=>c.painel_size>0).map(c=>c.painel_size)))) : '—'),
      cls: 'accent-purple'
    },
    {
      lbl: 'Visitas/dia (' + sigla + ')',
      val: A.vis_dia_medio!==null? fmt(A.vis_dia_medio,2) : '—',
      sub: A.vis_dia_n + ' com visita · ' + sigla + ' = ' + meta.janela_ini + ' → ' + meta.janela_fim,
      cls: 'accent-teal'
    },
    {
      lbl: 'Capacidade efetiva',
      val: A.dias_trab_mes_medio!==null? fmt(A.dias_trab_mes_medio,1) : '—',
      sub: 'dias em campo/mês · ' +
           (A.pct_ausencia_medio!==null? pct(A.pct_ausencia_medio) + ' fora <span class="tip" data-tip="' + ausenciaTooltipText() + '"></span>' : ''),
      cls: 'accent-warn'
    },
    {
      lbl: 'Overlap intra-time',
      val: A.overlap_intra_medio!==null? pct(A.overlap_intra_medio) : '—',
      sub: 'esperado <10%; cross-team é normal',
      cls: 'accent-purple'
    }
  ];

  // === Onda 5: KPIs sintéticos (IPT + Score Território) ===
  // Calcula agregados a partir dos campos pré-computados pelo processar.py
  const csKpi = getFilteredAtivos();
  const ipts = csKpi.map(c=>c.ipt).filter(v=>v!==null && v!==undefined);
  const iptMedio = ipts.length ? ipts.reduce((a,b)=>a+b,0)/ipts.length : null;
  const nInviavel = csKpi.filter(c=>c.ipt_flag==='inviavel').length;
  const nPressionado = csKpi.filter(c=>c.ipt_flag==='pressionado').length;
  const corIpt = iptMedio===null ? 'var(--ink3)' :
                 iptMedio < 0.85 ? 'var(--teal)' :
                 iptMedio < 1.00 ? 'var(--ink2)' :
                 iptMedio < 1.15 ? 'var(--warn)' :
                 'var(--danger)';
  const scores = csKpi.map(c=>c.score_territorio).filter(v=>v!==null && v!==undefined);
  const scoreMedio = scores.length ? scores.reduce((a,b)=>a+b,0)/scores.length : null;
  const nCritico = csKpi.filter(c=>c.score_territorio_status==='critico').length;
  const corScore = scoreMedio===null ? 'var(--ink3)' :
                   scoreMedio >= 80 ? 'var(--teal)' :
                   scoreMedio >= 60 ? 'var(--warn)' :
                   'var(--danger)';
  items.push({
    lbl: 'IPT — Pressão de target <span class="tip" data-tip="Índice de Pressão de Target: (Painel atual × freq alvo × cobertura alvo) ÷ capacidade efetiva mensal do perfil. <0,85=confortável · 0,85-1=no limite · 1-1,15=pressionado · >1,15=inviável."></span>',
    val: iptMedio===null ? '—' : `<span style="color:${corIpt};">${iptMedio.toFixed(2)}</span>`,
    sub: `${nInviavel} inviável · ${nPressionado} pressionado`,
    cls: 'accent-warn'
  });
  items.push({
    lbl: 'Score território (média) <span class="tip" data-tip="0-100, combinando overlap intra (35%), overlap cross (10%), viagem vs perfil (20%), % UF sede (15%) e delta painel atual×ideal (20%). ≥80=saudável · 60-79=atenção · <60=crítico."></span>',
    val: scoreMedio===null ? '—' : `<span style="color:${corScore};">${scoreMedio.toFixed(0)}</span>`,
    sub: `${nCritico} crítico${nCritico===1?'':'s'} de ${csKpi.length}`,
    cls: 'accent-purple'
  });

  document.getElementById('kpi-grid').innerHTML = items.map(it=>`
    <div class="kpi ${it.cls||''}">
      <div class="kpi-lbl">${it.lbl}</div>
      <div class="kpi-val">${it.val}</div>
      <div class="kpi-sub">${it.sub}</div>
    </div>`).join('');
}

// Calcula Total / Dentro Painel / Fora Painel deduplicando MDMs entre consultores do recorte
function computeMedicosUnicos(cs){
  const painel = new Set();
  const visitados = new Set();
  cs.forEach(c=>{
    (c.mdms_painel||[]).forEach(m=>painel.add(m));
    (c.mdms_visitados_mat||[]).forEach(m=>visitados.add(m));
  });
  let dentro=0, fora=0;
  visitados.forEach(m=>{
    if(painel.has(m)) dentro++; else fora++;
  });
  return {
    total: visitados.size,
    dentro_painel: dentro,
    fora_painel: fora,
    painel_total: painel.size,
  };
}

function ausenciaTooltipText(){
  return 'É a média do MAT (últimos 12 meses fechados): total de dias ausentes ÷ total de dias úteis no período. NÃO significa que X% dos consultores estão fora todo dia — é o tempo do consultor médio que ficou fora do campo somando o ano inteiro.';
}

// ============================================================================
// SIMULADOR (Itens 18-19)
// ============================================================================
// ============================================================================
// SIMULADOR DE CAPACIDADE — perfis Local / Vint / Vinter + meta universal
// ============================================================================
function initSimInputs(){
  // Onda 3 — IDs do novo modelo (Excel): desloc (dias/sem) + visdia + noshow + freq + alvo
  // Não há mais 'painel' como input — o painel ideal é a SAÍDA do cálculo.
  const ids = [
    'sim-desloc-local','sim-visdia-local','sim-noshow-local','sim-freq-local','sim-alvo-local',
    'sim-desloc-vint','sim-visdia-vint','sim-noshow-vint','sim-freq-vint','sim-alvo-vint',
    'sim-desloc-vinter','sim-visdia-vinter','sim-noshow-vinter','sim-freq-vinter','sim-alvo-vinter',
  ];
  ids.forEach(id=>{
    const el = document.getElementById(id);
    if(!el) return;
    el.addEventListener('input', ()=>renderSim());
  });
  renderSim();
}

function resetSimPerfis(){
  // Defaults Excel Simulacao_Cobertura: 0.5/0.75/1.5 desloc, 5 visdia, 10-15% noshow, 1 freq, 80% alvo
  const defaults = {
    'sim-desloc-local':0.5,  'sim-visdia-local':5,  'sim-noshow-local':10, 'sim-freq-local':1.0,  'sim-alvo-local':80,
    'sim-desloc-vint':0.75,  'sim-visdia-vint':5,   'sim-noshow-vint':12,  'sim-freq-vint':1.0,   'sim-alvo-vint':80,
    'sim-desloc-vinter':1.5, 'sim-visdia-vinter':5, 'sim-noshow-vinter':15,'sim-freq-vinter':1.0, 'sim-alvo-vinter':80,
  };
  Object.entries(defaults).forEach(([id,v])=>{
    const el=document.getElementById(id); if(el) el.value=v;
  });
  renderSim();
}

function getSimParams(){
  const get = (id, def)=>{
    const el=document.getElementById(id);
    if(!el) return def;
    const v = parseFloat(el.value);
    return isNaN(v) ? def : v;
  };
  return {
    local: {
      desloc:  get('sim-desloc-local', 0.5),
      visdia:  get('sim-visdia-local', 5),
      noshow:  get('sim-noshow-local', 10),  // %
      freq:    get('sim-freq-local', 1.0),
      alvo:    get('sim-alvo-local', 80),
    },
    vint: {
      desloc:  get('sim-desloc-vint', 0.75),
      visdia:  get('sim-visdia-vint', 5),
      noshow:  get('sim-noshow-vint', 12),
      freq:    get('sim-freq-vint', 1.0),
      alvo:    get('sim-alvo-vint', 80),
    },
    vinter: {
      desloc:  get('sim-desloc-vinter', 1.5),
      visdia:  get('sim-visdia-vinter', 5),
      noshow:  get('sim-noshow-vinter', 15),
      freq:    get('sim-freq-vinter', 1.0),
      alvo:    get('sim-alvo-vinter', 80),
    },
  };
}

function calcularCapacidadePerfil(perfil, p){
  // Modelo Excel Simulacao_Cobertura:
  //   Dias em campo/mês = 20 - (desloc_semanal × 4)
  //   Capacidade efetiva = dias × visdia × (1 - noshow)   ← gordura embutida
  //   Painel ideal = capacidade ÷ (freq × cobertura_alvo)
  //   Margem mensal pra no-show = dias × visdia × noshow  (visitas "compradas" como buffer)
  const semanas = 4;  // semanas por mês (referência Excel)
  const dias_uteis_mes = 20;
  const dias_campo_mes = Math.max(0, dias_uteis_mes - (p.desloc * semanas));
  const noshow_frac = (p.noshow || 0) / 100;
  const cobertura_frac = (p.alvo || 80) / 100;
  const freq = p.freq || 1.0;
  const visitas_brutas_mes = dias_campo_mes * p.visdia;
  const capacidade_efetiva_mes = visitas_brutas_mes * (1 - noshow_frac);
  // Painel ideal: capacidade efetiva mensal ÷ (freq mensal × cobertura)
  const painel_ideal = (freq > 0 && cobertura_frac > 0)
    ? capacidade_efetiva_mes / (freq * cobertura_frac)
    : 0;
  // Margem mensal pra no-show
  const margem_noshow_mes = visitas_brutas_mes * noshow_frac;
  // Médicos mínimos a visitar pra atingir cobertura
  const medicos_min_mes = painel_ideal * cobertura_frac;
  // Versão trimestral (compatibilidade com tela atual)
  const dias_campo_tri = dias_campo_mes * 3;
  const capacidade_visitas_tri = capacidade_efetiva_mes * 3;
  const visitas_necessarias_tri = painel_ideal * freq * 3;
  const cobertura_pct = visitas_necessarias_tri > 0
    ? Math.min(100, capacidade_visitas_tri / visitas_necessarias_tri * 100)
    : 0;
  return {
    // saídas principais (Excel)
    dias_campo_mes: Math.round(dias_campo_mes*10)/10,
    visitas_brutas_mes: Math.round(visitas_brutas_mes),
    capacidade_efetiva_mes: Math.round(capacidade_efetiva_mes),
    margem_noshow_mes: Math.round(margem_noshow_mes),
    painel_ideal: Math.round(painel_ideal),
    medicos_min_mes: Math.round(medicos_min_mes),
    // compatibilidade
    dias_campo_tri: Math.round(dias_campo_tri*10)/10,
    capacidade_visitas_tri: Math.round(capacidade_visitas_tri),
    visitas_necessarias_tri: Math.round(visitas_necessarias_tri),
    cobertura_pct: Math.round(cobertura_pct),
    gap_visitas: Math.round(capacidade_visitas_tri - visitas_necessarias_tri),
    // p.painel é deduzido (não existe mais como input — exibimos o painel_ideal)
    painel: Math.round(painel_ideal),
  };
}

// Benchmarks da indústria farmacêutica BR (oncologia/especialidade)
// Fontes: IQVIA Field Force 2023, Sindusfarma, padrão SFE indústria
const BENCH = {
  visdia: {min:5, max:7, label:'Vis/dia ind. farma 5-7'},
  painel: {min:80, max:150, label:'Painel oncologia 80-150'},
  freq:   {min:1, max:1.5, label:'Freq mensal 1-1,5'},
  cob_local:   {min:80, max:95, label:'Cobertura Local 80-95%'},
  cob_vint:    {min:70, max:85, label:'Cobertura V.Interna 70-85%'},
  cob_vinter:  {min:60, max:75, label:'Cobertura V.Inter 60-75%'},
};

// Tabela de benchmark — DESATIVADA (a pedido: Raissa removeu da Onda 3 do simulador)
function benchTable(p){
  return '';
}

// Histograma vertical de cobertura — estilo Visão Geral (5 faixas de 20% + linha do alvo)
function miniHistogramaPerfil(perfil_nome, alvo){
  const q = getAlvoQuarter ? getAlvoQuarter() : null;
  if(!q) return '';
  const cs = getFilteredAtivos().filter(c=>c.tipo_setor===perfil_nome);
  if(!cs.length){
    return '<div style="font-size:10.5px;color:var(--ink3);text-align:center;padding:8px;">Sem consultores deste perfil no recorte</div>';
  }
  const cobs = [];
  cs.forEach(c=>{
    const cob = calcCoberturaRealConsultor(c, q);
    if(cob !== null) cobs.push(cob);
  });
  if(!cobs.length){
    return '<div style="font-size:10.5px;color:var(--ink3);text-align:center;padding:8px;">Sem painel no quarter</div>';
  }
  // Buckets de 20% (0-20, 20-40, 40-60, 60-80, 80-100)
  const buckets = [
    {lo:0,  hi:20,  label:'0-20%',   n:0},
    {lo:20, hi:40,  label:'20-40%',  n:0},
    {lo:40, hi:60,  label:'40-60%',  n:0},
    {lo:60, hi:80,  label:'60-80%',  n:0},
    {lo:80, hi:101, label:'80-100%', n:0},
  ];
  cobs.forEach(c=>{
    const b = buckets.find(b=>c>=b.lo && c<b.hi);
    if(b) b.n++;
  });
  const max = Math.max(...buckets.map(b=>b.n), 1);
  const media = Math.round(cobs.reduce((a,b)=>a+b,0)/cobs.length);
  const atendem = cobs.filter(c=>c>=alvo).length;

  // SVG vertical estilo Visão Geral
  const w = 280, h = 140;
  const pad = {l:18, r:8, t:28, b:38};
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const slotW = innerW / buckets.length;
  const barW = slotW * 0.72;

  // Posição da linha do alvo (em % → x do gráfico)
  const alvoX = pad.l + (alvo/100) * innerW;
  // Posição da linha da média
  const mediaX = pad.l + (media/100) * innerW;

  let svg = '';
  buckets.forEach((b,i)=>{
    const x = pad.l + i*slotW + (slotW-barW)/2;
    // Limitar altura máxima a 92% da área útil pra deixar espaço pro número
    const bh = (b.n/max) * innerH * 0.92;
    const y = pad.t + innerH - bh;
    // Cor: faixa contendo o alvo = amarelo, acima = verde, abaixo = vermelho
    const meio = (b.lo + b.hi) / 2;
    const cor = meio >= alvo ? '#00857C' : meio >= alvo - 20 ? '#D4900A' : '#C8102E';
    svg += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" fill="${cor}" rx="2"/>`;
    if(b.n>0){
      svg += `<text x="${(x+barW/2).toFixed(1)}" y="${(y-4).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="700" fill="${cor}" font-family="Arial">${b.n}</text>`;
    }
    // Label x
    svg += `<text x="${(x+barW/2).toFixed(1)}" y="${(pad.t+innerH+11).toFixed(1)}" text-anchor="middle" font-size="8.5" fill="#566778" font-family="Arial">${b.label}</text>`;
  });
  // Linha do alvo
  svg += `<line x1="${alvoX.toFixed(1)}" y1="${pad.t-2}" x2="${alvoX.toFixed(1)}" y2="${pad.t+innerH+3}" stroke="#0C2340" stroke-width="1.5" stroke-dasharray="3,2"/>`;
  // Linha da média
  const distLabels = Math.abs(media - alvo);
  const desenhaMedia = distLabels > 3;
  if(desenhaMedia){
    svg += `<line x1="${mediaX.toFixed(1)}" y1="${pad.t-2}" x2="${mediaX.toFixed(1)}" y2="${pad.t+innerH+3}" stroke="#6B3FA0" stroke-width="1" stroke-dasharray="2,2"/>`;
  }
  // Labels — posicionar pra não colidirem
  const minPxLabel = 38;
  const distPx = Math.abs(alvoX - mediaX);
  let alvoLabelX = alvoX;
  let mediaLabelX = mediaX;
  let alvoLabelY = pad.t - 12;  // mais alto pra não colidir com número da barra
  let mediaLabelY = pad.t - 12;
  // Ajustar X dos labels pra não saírem do viewBox
  if(alvoLabelX < 20) alvoLabelX = 20;
  if(alvoLabelX > w - 20) alvoLabelX = w - 20;
  if(mediaLabelX < 20) mediaLabelX = 20;
  if(mediaLabelX > w - 20) mediaLabelX = w - 20;
  if(desenhaMedia && distPx < minPxLabel){
    // Empurra a média pra baixo
    mediaLabelY = pad.t + innerH + 22;
  }
  svg += `<text x="${alvoLabelX.toFixed(1)}" y="${alvoLabelY.toFixed(1)}" text-anchor="middle" font-size="9" font-weight="700" fill="#0C2340" font-family="Arial">alvo ${alvo}%</text>`;
  if(desenhaMedia){
    svg += `<text x="${mediaLabelX.toFixed(1)}" y="${mediaLabelY.toFixed(1)}" text-anchor="middle" font-size="9" font-weight="700" fill="#6B3FA0" font-family="Arial">média ${media}%</text>`;
  }

  return `
    <div style="background:#F9FBFC;border-top:1px solid var(--line);padding:8px 10px;margin-top:8px;border-radius:4px;">
      <div style="font-size:10.5px;color:var(--ink3);margin-bottom:2px;font-weight:600;">
        Distribuição real em ${labelQuarterPt(q.label)}:
      </div>
      <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">${svg}</svg>
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:2px;font-size:10.5px;">
        <span style="color:var(--ink3);">${cs.length} consultor(es) · ${cobs.length} com painel</span>
        <span style="font-weight:700;color:${atendem===cobs.length?'#00857C':atendem>=cobs.length*0.7?'#D4900A':'#C8102E'};">
          ${atendem}/${cobs.length} atendem ${alvo}%
        </span>
      </div>
    </div>`;
}

function renderSimPerfilCard(perfil, p){
  const r = calcularCapacidadePerfil(perfil, p);
  const perfil_nome_real = perfil==='local' ? 'Local' : perfil==='vint' ? 'Viagem Interna' : 'Viagem Interestadual';

  return `
    <div class="out-row">
      <span>Dias em campo/mês:</span><strong>${r.dias_campo_mes}</strong>
    </div>
    <div class="out-row">
      <span>Visitas brutas/mês <span style="font-size:9.5px;color:var(--ink3);">(dias × visdia)</span>:</span>
      <strong>${fmt(r.visitas_brutas_mes)}</strong>
    </div>
    <div class="out-row" style="color:var(--ink2);">
      <span>− Gordura no-show <span style="font-size:9.5px;color:var(--ink3);">(${p.noshow}%)</span>:</span>
      <strong style="color:var(--warn);">−${fmt(r.margem_noshow_mes)}</strong>
    </div>
    <div class="out-row" style="border-top:1px solid var(--line);padding-top:6px;margin-top:4px;">
      <span><strong>Capacidade efetiva/mês:</strong></span>
      <strong>${fmt(r.capacidade_efetiva_mes)} visitas</strong>
    </div>
    <div class="sim-cobertura ok" style="background:#E8F4F2;color:var(--ink);">
      <div style="font-size:11px;font-weight:600;opacity:0.85;">Painel ideal para esse perfil</div>
      <div class="out-num big" style="color:#00857C;">${r.painel_ideal}</div>
      <div style="font-size:10.5px;font-weight:600;opacity:0.7;">médicos · freq ${p.freq}×/mês · cobertura ${p.alvo}%</div>
    </div>
    <div style="margin-top:6px;padding:6px 9px;border:1px dashed var(--lineSt);border-radius:4px;text-align:center;background:#FFFEF8;font-size:10.5px;color:var(--ink2);line-height:1.4;">
      <div><strong style="color:#D4900A;">${r.medicos_min_mes}</strong> médicos visitados/mês = cobertura ${p.alvo}% atingida</div>
    </div>
    ${miniHistogramaPerfil(perfil_nome_real, p.alvo)}
  `;
}

function renderSim(){
  const params = getSimParams();
  // 1) Renderizar os 3 cards de perfil
  const elL = document.getElementById('sim-out-local');
  if(elL) elL.innerHTML = renderSimPerfilCard('local', params.local);
  const elV = document.getElementById('sim-out-vint');
  if(elV) elV.innerHTML = renderSimPerfilCard('vint', params.vint);
  const elI = document.getElementById('sim-out-vinter');
  if(elI) elI.innerHTML = renderSimPerfilCard('vinter', params.vinter);

  // 2) Capacidade por GD com meta universal
  renderCapacidadeGD(params);

  // 3) Quem atende o alvo
  renderAlvoQuarterToggle();
  renderAlvoPerfil(params);

  // 4) (Removido: Diagnóstico consultor a consultor — Comparação individual com cenário)
  // 5) Comparativo histórico
  renderHistComparativo(params);

  // 6) Painel ideal teórico
  renderPainelIdeal(params);

  // 7) (Removido: Calculadora de viagem por UF)
}

// ============================================================================
// ATINGIMENTO DO ALVO POR PERFIL
// ============================================================================
function getAlvoQuarter(){
  const qs = (DATA.consultores[0] && DATA.consultores[0].quarters) || [];
  if(!qs.length) return null;
  const sel = ST.alvo_quarter;
  return qs.find(q=>q.label===sel) || qs[qs.length-1];
}

function setAlvoQuarter(qlabel){
  ST.alvo_quarter = qlabel;
  document.querySelectorAll('#alvo-q-toggle button').forEach(b=>{
    b.classList.toggle('active', b.dataset.q===qlabel);
  });
  renderSim();
}

function renderAlvoQuarterToggle(){
  const qs = (DATA.consultores[0] && DATA.consultores[0].quarters) || [];
  if(!qs.length) return;
  const t = document.getElementById('alvo-q-toggle');
  if(!t || t.children.length) return;
  // Default: último Q fechado (Q-1 = penúltimo da lista)
  const idx_default = qs.length >= 2 ? qs.length - 2 : qs.length - 1;
  if(!ST.alvo_quarter) ST.alvo_quarter = qs[idx_default].label;
  t.innerHTML = qs.map((q,i)=>{
    const active = q.label===ST.alvo_quarter ? ' class="active"' : '';
    const sufixo = (i === qs.length - 1) ? ' (em andamento)' : '';
    return `<button${active} data-q="${q.label}" onclick="setAlvoQuarter('${q.label}')">${labelQuarterPt(q.label)}${sufixo}</button>`;
  }).join('');
}

function getAlvoPorPerfil(params){
  return {
    'Local': params.local.alvo,
    'Viagem Interna': params.vint.alvo,
    'Viagem Interestadual': params.vinter.alvo,
  };
}

function calcCoberturaRealConsultor(c, q){
  // Cobertura real = médicos visitados ∩ painel ÷ painel
  const qc = (c.quarters||[]).find(x=>x.label===q.label);
  if(!qc) return null;
  const painel = new Set(getPainelMdms(c, qc));
  if(painel.size === 0) return null;
  const visitados = new Set(qc.mdms||[]);
  let dentro = 0;
  visitados.forEach(m=>{ if(painel.has(m)) dentro++; });
  return Math.round(dentro / painel.size * 100);
}

function renderAlvoPerfil(params){
  const q = getAlvoQuarter();
  if(!q) return;
  const labelQ = labelQuarterPt(q.label);
  const alvos = getAlvoPorPerfil(params);
  const cs = getFilteredAtivos();

  // === 3 cards resumo por perfil ===
  const elResumo = document.getElementById('alvo-resumo-cards');
  if(elResumo){
    const cards = ['Local','Viagem Interna','Viagem Interestadual'].map(perfil=>{
      const consPerfil = cs.filter(c=>c.tipo_setor===perfil);
      const alvo = alvos[perfil];
      // Quantos atendem (cobertura real ≥ alvo)?
      let atendem = 0, total_com_dado = 0;
      consPerfil.forEach(c=>{
        const cob = calcCoberturaRealConsultor(c, q);
        if(cob !== null){
          total_com_dado++;
          if(cob >= alvo) atendem++;
        }
      });
      const pct_atendem = total_com_dado>0 ? Math.round(atendem/total_com_dado*100) : 0;
      const cor = pct_atendem >= 70 ? 'var(--teal)' : pct_atendem >= 40 ? 'var(--warn)' : 'var(--danger)';
      const tagCor = perfil==='Local' ? '#00857C' : perfil==='Viagem Interna' ? '#6B3FA0' : '#D4900A';
      return `
        <div class="card" style="border-left:4px solid ${tagCor};">
          <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:6px;">
            <span style="background:${tagCor};color:#fff;padding:2px 8px;border-radius:3px;font-weight:700;font-size:11px;">${perfil}</span>
            <span style="font-size:11px;color:var(--ink3);">alvo <strong>${alvo}%</strong></span>
          </div>
          <div style="font-size:11px;color:var(--ink3);margin-top:4px;">Atendem o alvo em ${labelQ}</div>
          <div class="card-num" style="color:${cor};font-size:28px;font-weight:800;margin:4px 0;">
            ${atendem}<span style="font-size:14px;color:var(--ink3);font-weight:500;"> / ${total_com_dado}</span>
          </div>
          <div style="font-size:12px;color:${cor};font-weight:700;">${pct_atendem}% do perfil</div>
          ${consPerfil.length > total_com_dado
            ? `<div style="font-size:10.5px;color:var(--ink3);font-style:italic;margin-top:3px;">${consPerfil.length-total_com_dado} consultor(es) sem painel no quarter</div>`
            : ''}
        </div>`;
    }).join('');
    elResumo.innerHTML = cards;
  }

  // === Tabela completa ===
  const tbody = document.querySelector('#tbl-alvo-perfil tbody');
  if(!tbody) return;
  const linhas = cs.map(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    const painel = getPainelMdms(c, qc);
    const visitados = qc ? (qc.mdms||[]) : [];
    const setP = new Set(painel);
    let dentro = 0;
    visitados.forEach(m=>{ if(setP.has(m)) dentro++; });
    const cobReal = painel.length>0 ? Math.round(dentro/painel.length*100) : null;
    const alvo = alvos[c.tipo_setor] || null;
    const delta = (cobReal!==null && alvo!==null) ? (cobReal - alvo) : null;
    let situacao;
    if(cobReal===null){
      situacao = '<span style="color:var(--ink3);">sem painel no quarter</span>';
    } else if(alvo===null){
      situacao = '<span style="color:var(--ink3);">perfil sem alvo</span>';
    } else if(cobReal >= alvo){
      situacao = '<span style="color:var(--teal);font-weight:700;">atende</span>';
    } else if(cobReal >= alvo * 0.85){
      situacao = '<span style="color:var(--warn);font-weight:700;">próximo</span>';
    } else {
      situacao = '<span style="color:var(--danger);font-weight:700;">abaixo</span>';
    }
    return {c, painel: painel.length, visitados: visitados.length, dentro, cobReal, alvo, delta, situacao};
  }).sort((a,b)=>{
    // Quem está mais abaixo do alvo primeiro
    if(a.delta===null && b.delta===null) return 0;
    if(a.delta===null) return 1;
    if(b.delta===null) return -1;
    return a.delta - b.delta;
  });

  tbody.innerHTML = linhas.map(r=>{
    const c = r.c;
    const corCob = r.cobReal===null ? 'var(--ink3)' :
                   (r.alvo===null || r.cobReal >= r.alvo) ? 'var(--teal)' :
                   r.cobReal >= r.alvo*0.85 ? 'var(--warn)' : 'var(--danger)';
    const deltaTxt = r.delta===null ? '—' : (r.delta>=0 ? '+' : '') + r.delta + 'pp';
    return `
    <tr>
      <td class="nm">${escapeHtml(c.nome)}</td>
      <td>${escapeHtml(c.sales_force||'')}</td>
      <td>${escapeHtml(c.gd_name||'—')}</td>
      <td>${escapeHtml(c.tipo_setor||'—')}</td>
      <td class="num">${fmt(r.painel)}</td>
      <td class="num">${fmt(r.visitados)}</td>
      <td class="num" style="color:${corCob};font-weight:700;">${r.cobReal===null?'—':r.cobReal+'%'}</td>
      <td class="num">${r.alvo===null?'—':r.alvo+'%'}</td>
      <td class="num" style="font-weight:700;color:${r.delta===null?'var(--ink3)':r.delta>=0?'var(--teal)':'var(--danger)'};">${deltaTxt}</td>
      <td>${r.situacao}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="10" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados no recorte.</td></tr>';
}

function exportAlvoPerfil(){
  const params = getSimParams();
  const q = getAlvoQuarter();
  if(!q) return;
  const alvos = getAlvoPorPerfil(params);
  const cs = getFilteredAtivos();
  const rows = cs.map(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    const painel = getPainelMdms(c, qc);
    const visitados = qc ? (qc.mdms||[]) : [];
    const setP = new Set(painel);
    let dentro = 0;
    visitados.forEach(m=>{ if(setP.has(m)) dentro++; });
    const cobReal = painel.length>0 ? Math.round(dentro/painel.length*100) : '';
    const alvo = alvos[c.tipo_setor] || '';
    let status = '';
    if(cobReal==='' || alvo==='') status = 'sem dado';
    else if(cobReal >= alvo) status = 'atende';
    else if(cobReal >= alvo*0.85) status = 'próximo';
    else status = 'abaixo';
    return [c.nome, c.sales_force, c.gd_name, c.tipo_setor,
            painel.length, visitados.length, dentro, cobReal, alvo, status];
  });
  downloadCsv('alvo_cobertura_'+q.label+'.csv',
    ['Consultor','SF','GD','Perfil','Painel ('+q.label+')','Visitados','Dentro painel',
     'Cobertura real (%)','Alvo (%)','Status'],
    rows);
}


function renderCapacidadeGD(params){
  const tbody = document.querySelector('#tbl-cap-gd tbody');
  if(!tbody) return;
  // Coberturas por perfil
  const cobL = calcularCapacidadePerfil('local', params.local).cobertura_pct;
  const cobV = calcularCapacidadePerfil('vint', params.vint).cobertura_pct;
  const cobI = calcularCapacidadePerfil('vinter', params.vinter).cobertura_pct;

  // Agregar consultores por GD respeitando filtro
  const cs = getFilteredAtivos();
  const byGd = {};
  cs.forEach(c=>{
    const gd = c.gd_name || '(sem GD)';
    if(!byGd[gd]) byGd[gd] = {gd, total:0, local:0, vint:0, vinter:0};
    byGd[gd].total++;
    if(c.tipo_setor==='Local') byGd[gd].local++;
    else if(c.tipo_setor==='Viagem Interna') byGd[gd].vint++;
    else if(c.tipo_setor==='Viagem Interestadual') byGd[gd].vinter++;
  });
  const linhas = Object.values(byGd).map(g=>{
    const tot = g.total || 1;
    const universal = Math.round((g.local*cobL + g.vint*cobV + g.vinter*cobI) / tot);
    return {...g, universal};
  }).sort((a,b)=>a.gd.localeCompare(b.gd,'pt-BR'));

  // Linha total (todos GDs do recorte)
  const totalRow = linhas.reduce((acc,r)=>({
    gd:'TOTAL', total:acc.total+r.total,
    local:acc.local+r.local, vint:acc.vint+r.vint, vinter:acc.vinter+r.vinter
  }), {gd:'TOTAL', total:0, local:0, vint:0, vinter:0});
  if(totalRow.total>0){
    totalRow.universal = Math.round((totalRow.local*cobL + totalRow.vint*cobV + totalRow.vinter*cobI)/totalRow.total);
  } else totalRow.universal = 0;

  const corCob = v => v>=100 ? 'var(--teal)' : v>=85 ? 'var(--warn)' : 'var(--danger)';

  const renderRow = (r, isTotal)=>{
    const cls = isTotal ? 'style="background:#F4F8FB;font-weight:700;border-top:2px solid var(--purple);"' : '';
    return `
    <tr ${cls}>
      <td class="nm">${escapeHtml(r.gd)}</td>
      <td class="num">${r.total}</td>
      <td class="num">${r.local}</td>
      <td class="num">${r.vint}</td>
      <td class="num">${r.vinter}</td>
      <td class="num" style="color:${r.local>0?corCob(cobL):'var(--ink3)'};">${r.local>0?cobL+'%':'—'}</td>
      <td class="num" style="color:${r.vint>0?corCob(cobV):'var(--ink3)'};">${r.vint>0?cobV+'%':'—'}</td>
      <td class="num" style="color:${r.vinter>0?corCob(cobI):'var(--ink3)'};">${r.vinter>0?cobI+'%':'—'}</td>
      <td class="num" style="color:${corCob(r.universal)};font-weight:800;">${r.universal}%</td>
    </tr>`;
  };
  tbody.innerHTML = linhas.map(r=>renderRow(r, false)).join('') +
                    (linhas.length>1 ? renderRow(totalRow, true) : '');
}

function renderDiagnosticoSim(params){
  const tbody = document.querySelector('#tbl-diagnostico tbody');
  if(!tbody) return;
  const cobL = calcularCapacidadePerfil('local', params.local).cobertura_pct;
  const cobV = calcularCapacidadePerfil('vint', params.vint).cobertura_pct;
  const cobI = calcularCapacidadePerfil('vinter', params.vinter).cobertura_pct;
  const cobPorPerfil = (perfil)=>{
    if(perfil==='Local') return cobL;
    if(perfil==='Viagem Interna') return cobV;
    if(perfil==='Viagem Interestadual') return cobI;
    return null;
  };
  const cs = getFilteredAtivos();
  const linhas = cs.map(c=>{
    const cob_esperada = cobPorPerfil(c.tipo_setor);
    const real = c.mccp_pct_cumprido;
    let diag = '—';
    if(cob_esperada===null || real===null || real===undefined){
      diag = '<span style="color:var(--ink3);">sem perfil/MCCP</span>';
    } else if(real >= cob_esperada){
      const dif = real - cob_esperada;
      diag = '<span style="color:var(--teal);font-weight:700;">acima do esperado</span> <span style="color:var(--ink3);">(+'+dif.toFixed(0)+'pp)</span>';
    } else if(real >= cob_esperada * 0.85){
      diag = '<span style="color:var(--warn);">próximo ao esperado</span>';
    } else {
      const dif = cob_esperada - real;
      diag = '<span style="color:var(--danger);font-weight:700;">abaixo</span> <span style="color:var(--ink3);">(−'+dif.toFixed(0)+'pp)</span>';
    }
    return {c, cob_esperada, real, diag};
  }).sort((a,b)=>{
    // Abaixo do esperado primeiro
    const da = (a.real!==null && a.cob_esperada!==null) ? (a.real - a.cob_esperada) : 999;
    const db = (b.real!==null && b.cob_esperada!==null) ? (b.real - b.cob_esperada) : 999;
    return da - db;
  });
  tbody.innerHTML = linhas.map(r=>{
    const c = r.c;
    return `
    <tr>
      <td class="nm">${escapeHtml(c.nome)}</td>
      <td>${escapeHtml(c.sales_force||'')}</td>
      <td>${escapeHtml(c.gd_name||'—')}</td>
      <td>${escapeHtml(c.tipo_setor||'—')}</td>
      <td class="num">${fmt(c.painel_size)}</td>
      <td class="num">${fmt(c.vis_dia_media,2)}</td>
      <td class="num">${fmt(c.dias_trabalhados_mes,1)}</td>
      <td class="num">${r.cob_esperada===null?'—':r.cob_esperada+'%'}</td>
      <td class="num">${r.real===null||r.real===undefined?'—':r.real.toFixed(0)+'%'}</td>
      <td>${r.diag}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="10" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados no recorte.</td></tr>';
}

function exportCapacidadeGD(){
  const params = getSimParams();
  const cobL = calcularCapacidadePerfil('local', params.local).cobertura_pct;
  const cobV = calcularCapacidadePerfil('vint', params.vint).cobertura_pct;
  const cobI = calcularCapacidadePerfil('vinter', params.vinter).cobertura_pct;
  const cs = getFilteredAtivos();
  const byGd = {};
  cs.forEach(c=>{
    const gd = c.gd_name || '(sem GD)';
    if(!byGd[gd]) byGd[gd] = {gd, total:0, local:0, vint:0, vinter:0};
    byGd[gd].total++;
    if(c.tipo_setor==='Local') byGd[gd].local++;
    else if(c.tipo_setor==='Viagem Interna') byGd[gd].vint++;
    else if(c.tipo_setor==='Viagem Interestadual') byGd[gd].vinter++;
  });
  const rows = Object.values(byGd).map(g=>{
    const universal = Math.round((g.local*cobL + g.vint*cobV + g.vinter*cobI) / Math.max(1,g.total));
    return [g.gd, g.total, g.local, g.vint, g.vinter, cobL, cobV, cobI, universal];
  });
  downloadCsv('capacidade_por_gd.csv',
    ['GD','Time','Local','V. Interna','V. Interestadual',
     'Cobertura Local (%)','Cobertura V.Interna (%)','Cobertura V.Inter (%)','Meta Universal (%)'],
    rows);
}

function exportDiagnostico(){
  const params = getSimParams();
  const cobL = calcularCapacidadePerfil('local', params.local).cobertura_pct;
  const cobV = calcularCapacidadePerfil('vint', params.vint).cobertura_pct;
  const cobI = calcularCapacidadePerfil('vinter', params.vinter).cobertura_pct;
  const cs = getFilteredAtivos();
  const rows = cs.map(c=>{
    let esp = null;
    if(c.tipo_setor==='Local') esp = cobL;
    else if(c.tipo_setor==='Viagem Interna') esp = cobV;
    else if(c.tipo_setor==='Viagem Interestadual') esp = cobI;
    const real = c.mccp_pct_cumprido;
    let status = '';
    if(esp===null || real===null || real===undefined) status = 'sem dado';
    else if(real >= esp) status = 'acima';
    else if(real >= esp*0.85) status = 'próximo';
    else status = 'abaixo';
    return [c.nome, c.sales_force, c.gd_name, c.tipo_setor,
            c.painel_size, c.vis_dia_media, c.dias_trabalhados_mes,
            esp, real, status];
  });
  downloadCsv('diagnostico_consultor.csv',
    ['Consultor','SF','GD','Perfil','Painel','Vis/dia','Trab./mês',
     'Capacidade esperada (%)','% MCCP cumprido','Status'],
    rows);
}

// ============================================================================
// CALCULADORA DE VIAGEM POR UF (Vint + Vinter)
// ============================================================================
// Estado das edições do gestor: ISID -> {uf: semanas_editadas}
const CALC_VIAGEM_EDITS = {};

function getDefaultsSemanasUf(c){
  // Default = % histórico dos últimos 12m × 4 semanas
  const ufs = (c.performance_por_uf||[]).filter(u=>u.uf && u.visitas>0);
  const total = ufs.reduce((s,u)=>s+u.visitas, 0);
  if(total === 0) return [];
  return ufs.map(u=>({
    uf: u.uf,
    pct: Math.round(u.visitas/total*100),
    semanas: Math.round((u.visitas/total*4)*10)/10,  // 1 casa decimal
  })).filter(x=>x.pct >= 1);  // descartar UFs com <1% (ruído)
}

function getSemanasUfEditadas(isid, defaultRow){
  // Retorna o que o gestor editou, ou default
  if(CALC_VIAGEM_EDITS[isid] && CALC_VIAGEM_EDITS[isid][defaultRow.uf] !== undefined){
    return CALC_VIAGEM_EDITS[isid][defaultRow.uf];
  }
  return defaultRow.semanas;
}

function setSemanaUf(isid, uf, valor){
  if(!CALC_VIAGEM_EDITS[isid]) CALC_VIAGEM_EDITS[isid] = {};
  CALC_VIAGEM_EDITS[isid][uf] = parseFloat(valor) || 0;
  // Recalcular só o total dessa linha + status
  recalcLinhaCalcViagem(isid);
}

function renderCalcViagem(){
  const tbody = document.querySelector('#tbl-calc-viagem tbody');
  if(!tbody) return;
  const cs = getFilteredAtivos().filter(c=>
    c.tipo_setor==='Viagem Interna' || c.tipo_setor==='Viagem Interestadual'
  );
  if(!cs.length){
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--ink3);padding:14px;">Sem consultores Vint/Vinter no recorte.</td></tr>';
    return;
  }
  // Uma linha por UF de cada consultor; última linha de cada consultor tem o total
  let html = '';
  cs.forEach((c, idxC)=>{
    const defaults = getDefaultsSemanasUf(c);
    if(!defaults.length){
      html += `<tr style="border-top:2px solid var(--lineSt);">
        <td class="nm" rowspan="1" style="vertical-align:top;">${escapeHtml(c.nome)}</td>
        <td style="vertical-align:top;">${escapeHtml(c.sales_force||'')}</td>
        <td style="vertical-align:top;">${escapeHtml(c.gd_name||'—')}</td>
        <td style="vertical-align:top;">${escapeHtml(c.tipo_setor||'')}</td>
        <td colspan="3" style="color:var(--ink3);font-style:italic;">Sem histórico de UFs</td>
      </tr>`;
      return;
    }
    // Total atual dele
    const total = defaults.reduce((s,d)=>s + (getSemanasUfEditadas(c.ISID, d) || 0), 0);
    const diff = Math.abs(total - 4);
    let statusTxt, statusCor;
    if(diff < 0.3){ statusTxt = 'OK'; statusCor = '#00857C'; }
    else if(total < 4){ statusTxt = 'faltam ' + (4-total).toFixed(1) + ' sem'; statusCor = '#D4900A'; }
    else { statusTxt = 'excede em ' + (total-4).toFixed(1) + ' sem'; statusCor = '#C8102E'; }

    defaults.forEach((d, idxU)=>{
      const isFirst = idxU === 0;
      const isLast = idxU === defaults.length - 1;
      const val = getSemanasUfEditadas(c.ISID, d);
      const bgRow = idxC % 2 === 0 ? '#fff' : '#FAFBFD';
      // Borda separadora entre consultores
      const borderTop = isFirst ? 'border-top:2px solid var(--lineSt);' : '';
      html += `<tr data-isid="${c.ISID}" data-uf="${d.uf}" style="background:${bgRow};${borderTop}">`;
      if(isFirst){
        // Células de identificação ocupam todas as linhas do consultor (rowspan)
        const rs = defaults.length;
        html += `<td class="nm" rowspan="${rs}" style="vertical-align:top;border-right:1px solid var(--line);">${escapeHtml(c.nome)}</td>`;
        html += `<td rowspan="${rs}" style="vertical-align:top;border-right:1px solid var(--line);font-size:11px;">${escapeHtml(c.sales_force||'')}</td>`;
        html += `<td rowspan="${rs}" style="vertical-align:top;border-right:1px solid var(--line);font-size:11px;">${escapeHtml(c.gd_name||'—')}</td>`;
        html += `<td rowspan="${rs}" style="vertical-align:top;border-right:1px solid var(--line);font-size:11px;">${escapeHtml(c.tipo_setor||'—')}</td>`;
      }
      html += `<td style="padding:5px 8px;font-weight:700;">${d.uf}</td>`;
      html += `<td class="num" style="color:var(--ink3);">${d.pct}%</td>`;
      html += `<td class="num"><input type="number" min="0" max="4" step="0.5" value="${val}" data-uf="${d.uf}"
        onchange="setSemanaUf('${c.ISID}','${d.uf}',this.value)"
        style="width:60px;padding:3px 6px;border:1px solid var(--lineSt);border-radius:3px;font-size:12px;text-align:center;" /></td>`;
      if(isFirst){
        // Status: rowspan na primeira linha, mas só preenchido na ÚLTIMA visualmente
        // Pra deixar bom na leitura, vou pôr na primeira mesmo
        html += `<td rowspan="${defaults.length}" style="vertical-align:middle;text-align:center;border-left:1px solid var(--line);background:#F9FBFC;">
          <div class="total-cell" style="font-size:14px;font-weight:800;color:var(--ink);">${total.toFixed(1)}</div>
          <div style="font-size:9.5px;color:var(--ink3);">semanas total</div>
          <div class="status-cell" style="margin-top:4px;font-size:11px;font-weight:700;color:${statusCor};">${statusTxt}</div>
        </td>`;
      }
      html += `</tr>`;
    });
  });
  tbody.innerHTML = html;
}

function recalcLinhaCalcViagem(isid){
  // Recalcular total e status pra um consultor
  const inputs = document.querySelectorAll(`#tbl-calc-viagem tr[data-isid="${isid}"] input[data-uf]`);
  let total = 0;
  inputs.forEach(i=>{ total += parseFloat(i.value) || 0; });
  const totalCell = document.querySelector(`#tbl-calc-viagem tr[data-isid="${isid}"] .total-cell`);
  const statusCell = document.querySelector(`#tbl-calc-viagem tr[data-isid="${isid}"] .status-cell`);
  if(totalCell) totalCell.textContent = total.toFixed(1);
  if(statusCell){
    const diff = Math.abs(total - 4);
    if(diff < 0.3){
      statusCell.textContent = 'OK';
      statusCell.style.color = '#00857C';
    } else if(total < 4){
      statusCell.textContent = 'faltam ' + (4-total).toFixed(1) + ' sem';
      statusCell.style.color = '#D4900A';
    } else {
      statusCell.textContent = 'excede em ' + (total-4).toFixed(1) + ' sem';
      statusCell.style.color = '#C8102E';
    }
  }
}

function resetCalcViagem(){
  // Limpar todas as edições
  Object.keys(CALC_VIAGEM_EDITS).forEach(k=>delete CALC_VIAGEM_EDITS[k]);
  renderCalcViagem();
}

function exportCalcViagem(){
  const cs = getFilteredAtivos().filter(c=>
    c.tipo_setor==='Viagem Interna' || c.tipo_setor==='Viagem Interestadual'
  );
  const rows = [];
  cs.forEach(c=>{
    const defaults = getDefaultsSemanasUf(c);
    if(!defaults.length){
      rows.push([c.nome, c.sales_force, c.gd_name, c.tipo_setor, '', '', '', '', '', 'Sem histórico']);
      return;
    }
    defaults.forEach(d=>{
      const semEditada = getSemanasUfEditadas(c.ISID, d);
      const editado = CALC_VIAGEM_EDITS[c.ISID] && CALC_VIAGEM_EDITS[c.ISID][d.uf] !== undefined ? 'sim' : 'não';
      rows.push([c.nome, c.sales_force, c.gd_name, c.tipo_setor,
                 d.uf, d.pct, d.semanas, semEditada, editado, '']);
    });
  });
  downloadCsv('calculadora_viagem_uf.csv',
    ['Consultor','SF','GD','Perfil','UF','% histórico','Semanas (default histórico)','Semanas (planejadas)','Editado pelo gestor','Obs'],
    rows);
}

// ============================================================================
// EXPORT EXCEL ÚNICO DO SIMULADOR (5 abas)
// ============================================================================
// ============================================================================
// PAINEL IDEAL TEÓRICO
// ============================================================================
function calcPainelIdealConsultor(c, params){
  // Painel ideal = (vis/dia × dias trab/mês) ÷ freq_mensal
  // = visitas/mês ÷ visitas necessárias por médico/mês
  let freq;
  if(c.tipo_setor === 'Local') freq = params.local.freq;
  else if(c.tipo_setor === 'Viagem Interna') freq = params.vint.freq;
  else if(c.tipo_setor === 'Viagem Interestadual') freq = params.vinter.freq;
  else freq = 1.0;
  const vd = c.vis_dia_media || 0;
  const dias = c.dias_trabalhados_mes || 0;
  if(vd <= 0 || dias <= 0 || freq <= 0) return null;
  return Math.round((vd * dias) / freq);
}

function renderPainelIdeal(params){
  const tbody = document.querySelector('#tbl-painel-ideal tbody');
  if(!tbody) return;
  const cs = getFilteredAtivos();
  const linhas = cs.map(c=>{
    const ideal = calcPainelIdealConsultor(c, params);
    const atual = c.painel_size || 0;
    if(ideal === null || atual === 0) return null;
    const delta = ideal - atual;
    return {c, atual, ideal, delta};
  }).filter(l=>l !== null)
    .sort((a,b)=>a.delta - b.delta);  // Mais negativos (sobrecarregados) primeiro

  if(!linhas.length){
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados suficientes pra cálculo.</td></tr>';
    return;
  }
  tbody.innerHTML = linhas.map(l=>{
    const c = l.c;
    // Status: sobrecarregado (delta negativo grande) / ideal (próximo de 0) / capacidade ociosa (positivo grande)
    let status, corStatus;
    const pctDelta = Math.abs(l.delta) / l.atual * 100;
    if(pctDelta < 10){
      status = 'dimensionamento adequado';
      corStatus = 'var(--teal)';
    } else if(l.delta < 0){
      status = 'sobrecarregado (painel grande para a capacidade)';
      corStatus = 'var(--danger)';
    } else {
      status = 'capacidade ociosa (cabe mais painel)';
      corStatus = 'var(--warn)';
    }
    return `
    <tr>
      <td class="nm">${escapeHtml(c.nome)}</td>
      <td>${escapeHtml(c.sales_force||'')}</td>
      <td>${escapeHtml(c.gd_name||'—')}</td>
      <td>${escapeHtml(c.tipo_setor||'—')}</td>
      <td class="num">${fmt(l.atual)}</td>
      <td class="num">${fmt(c.vis_dia_media,2)}</td>
      <td class="num">${fmt(c.dias_trabalhados_mes,1)}</td>
      <td class="num" style="font-weight:700;">${fmt(l.ideal)}</td>
      <td class="num" style="font-weight:700;color:${l.delta<0?'var(--danger)':l.delta>0?'var(--warn)':'var(--teal)'};">${l.delta>=0?'+':''}${l.delta}</td>
      <td style="color:${corStatus};font-size:11px;">${status}</td>
    </tr>`;
  }).join('');
}

function exportPainelIdeal(){
  const params = getSimParams();
  const cs = getFilteredAtivos();
  const rows = cs.map(c=>{
    const ideal = calcPainelIdealConsultor(c, params);
    const atual = c.painel_size || 0;
    if(ideal === null || atual === 0) return null;
    const delta = ideal - atual;
    const pctDelta = atual > 0 ? Math.abs(delta) / atual * 100 : 0;
    let status;
    if(pctDelta < 10) status = 'dimensionamento adequado';
    else if(delta < 0) status = 'sobrecarregado';
    else status = 'capacidade ociosa';
    return [c.nome, c.sales_force, c.gd_name, c.tipo_setor,
            atual, c.vis_dia_media, c.dias_trabalhados_mes, ideal, delta, status];
  }).filter(r=>r !== null);
  downloadCsv('painel_ideal_teorico.csv',
    ['Consultor','SF','GD','Perfil','Painel atual','Vis/dia','Dias trab./mês',
     'Painel ideal','Δ (ideal-atual)','Status'],
    rows);
}


function calcCobRealPerfilQuarter(perfil_nome, qlabel){
  // Média de cobertura real (visitados/painel do quarter) entre consultores do perfil
  const cs = getFilteredAtivos().filter(c=>c.tipo_setor===perfil_nome);
  const cobs = [];
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===qlabel);
    if(!qc) return;
    const painel = getPainelMdms(c, qc);
    if(!painel.length) return;
    const visitados = new Set(qc.mdms||[]);
    let dentro = 0;
    painel.forEach(m=>{ if(visitados.has(m)) dentro++; });
    cobs.push(Math.round(dentro / painel.length * 100));
  });
  if(!cobs.length) return null;
  const media = Math.round(cobs.reduce((a,b)=>a+b,0)/cobs.length);
  const atendem_n = (alvo) => cobs.filter(c=>c>=alvo).length;
  return {media, total:cobs.length, atendem_n};
}

function svgHistorico(perfil_nome, perfil_key, params, alvo){
  const qs = (DATA.consultores[0] && DATA.consultores[0].quarters) || [];
  if(qs.length === 0) return '<div style="color:var(--ink3);text-align:center;padding:14px;font-size:11px;">Sem quarters disponíveis</div>';

  // Cobertura simulada = capacidade calculada com os parâmetros atuais (fixa, todos os Q)
  const r = calcularCapacidadePerfil(perfil_key, params);
  const cob_simulada = r.cobertura_pct;

  // Cobertura real por quarter
  const dados = qs.map(q=>{
    const real = calcCobRealPerfilQuarter(perfil_nome, q.label);
    return {label: q.label, labelPt: labelQuarterPt(q.label), real: real};
  });

  // SVG
  const w = 280, h = 150;
  const pad = {l:30, r:14, t:24, b:32};
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  // Escala Y: 0-100%
  const yMax = 100;

  // Eixo Y (grade)
  let svg = '';
  for(let p of [0, 25, 50, 75, 100]){
    const y = pad.t + innerH - (p/yMax)*innerH;
    svg += `<line x1="${pad.l}" y1="${y}" x2="${pad.l+innerW}" y2="${y}" stroke="#E8EEF3" stroke-dasharray="2,2"/>`;
    svg += `<text x="${pad.l-4}" y="${y+3}" text-anchor="end" font-size="8" fill="#8A9BAD" font-family="Arial">${p}%</text>`;
  }

  // Linha do alvo (horizontal)
  const alvoY = pad.t + innerH - (alvo/yMax)*innerH;
  svg += `<line x1="${pad.l}" y1="${alvoY}" x2="${pad.l+innerW}" y2="${alvoY}" stroke="#D4900A" stroke-width="1.2" stroke-dasharray="4,2"/>`;
  svg += `<text x="${pad.l+innerW-2}" y="${alvoY-2}" text-anchor="end" font-size="8" font-weight="700" fill="#D4900A" font-family="Arial">alvo ${alvo}%</text>`;

  // Linha simulada (horizontal, pontilhada)
  const simY = pad.t + innerH - (cob_simulada/yMax)*innerH;
  svg += `<line x1="${pad.l}" y1="${simY}" x2="${pad.l+innerW}" y2="${simY}" stroke="#6B3FA0" stroke-width="1.5" stroke-dasharray="2,3"/>`;
  svg += `<text x="${pad.l+2}" y="${simY-2}" text-anchor="start" font-size="8" font-weight="700" fill="#6B3FA0" font-family="Arial">simulado ${cob_simulada}%</text>`;

  // Linha real (sólida) + pontos
  const slotW = innerW / Math.max(1, dados.length-1);  // espaço entre pontos
  const xs = dados.length===1 ? [pad.l + innerW/2] :
             dados.map((_,i)=>pad.l + i*slotW);
  // Detectar qual quarter é o atual (parcial)
  const idxAtual = dados.length - 1;  // último é o corrente
  let pathReal = '';
  let pontos = '';
  dados.forEach((d,i)=>{
    const x = xs[i];
    const isParcial = (i === idxAtual);
    if(d.real === null){
      svg += `<text x="${x}" y="${pad.t+innerH+14}" text-anchor="middle" font-size="8.5" fill="#566778" font-family="Arial">${d.labelPt}</text>`;
      svg += `<text x="${x}" y="${pad.t+innerH+24}" text-anchor="middle" font-size="8" fill="#C8102E" font-family="Arial" font-style="italic">s/dado</text>`;
      return;
    }
    const y = pad.t + innerH - (d.real/yMax)*innerH;
    if(pathReal === '') pathReal = `M ${x} ${y}`;
    else pathReal += ` L ${x} ${y}`;
    const cor = d.real >= alvo ? '#00857C' : d.real >= alvo*0.85 ? '#D4900A' : '#C8102E';
    // Ponto: círculo cheio se quarter fechado, anel se parcial
    if(isParcial){
      pontos += `<circle cx="${x}" cy="${y}" r="5" fill="#fff" stroke="${cor}" stroke-width="2" stroke-dasharray="2,1"/>`;
    } else {
      pontos += `<circle cx="${x}" cy="${y}" r="4" fill="${cor}" stroke="#fff" stroke-width="1.5"/>`;
    }
    pontos += `<text x="${x}" y="${y-9}" text-anchor="middle" font-size="9" font-weight="700" fill="${cor}" font-family="Arial">${d.real}%</text>`;
    // Label X
    const lblExtra = isParcial ? '*' : '';
    svg += `<text x="${x}" y="${pad.t+innerH+14}" text-anchor="middle" font-size="8.5" fill="#566778" font-family="Arial">${d.labelPt}${lblExtra}</text>`;
  });
  if(pathReal) svg += `<path d="${pathReal}" fill="none" stroke="#0C2340" stroke-width="2"/>`;
  svg += pontos;

  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">${svg}</svg>
    <div style="font-size:9.5px;color:var(--ink3);margin-top:2px;text-align:center;font-style:italic;">* quarter em andamento (parcial)</div>`;
}

function renderHistComparativo(params){
  const el = document.getElementById('hist-cards');
  if(!el) return;
  const perfis = [
    {nome:'Local',                  key:'local',  alvo: params.local.alvo,   p: params.local,  cor:'#00857C'},
    {nome:'Viagem Interna',         key:'vint',   alvo: params.vint.alvo,    p: params.vint,   cor:'#6B3FA0'},
    {nome:'Viagem Interestadual',   key:'vinter', alvo: params.vinter.alvo,  p: params.vinter, cor:'#D4900A'},
  ];
  el.innerHTML = perfis.map(per=>{
    const svg = svgHistorico(per.nome, per.key, per.p, per.alvo);
    return `
      <div class="card" style="border-top:4px solid ${per.cor};">
        <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:6px;">
          <span style="background:${per.cor};color:#fff;padding:2px 8px;border-radius:3px;font-weight:700;font-size:11px;">${per.nome}</span>
          <span style="font-size:11px;color:var(--ink3);">alvo <strong>${per.alvo}%</strong></span>
        </div>
        ${svg}
      </div>`;
  }).join('');
}

function exportHistComparativo(){
  const params = getSimParams();
  const qs = (DATA.consultores[0] && DATA.consultores[0].quarters) || [];
  const perfis = [
    {nome:'Local',                  key:'local',  p:params.local,  alvo:params.local.alvo},
    {nome:'Viagem Interna',         key:'vint',   p:params.vint,   alvo:params.vint.alvo},
    {nome:'Viagem Interestadual',   key:'vinter', p:params.vinter, alvo:params.vinter.alvo},
  ];
  const rows = [];
  perfis.forEach(per=>{
    const sim = calcularCapacidadePerfil(per.key, per.p).cobertura_pct;
    qs.forEach(q=>{
      const real = calcCobRealPerfilQuarter(per.nome, q.label);
      rows.push([
        per.nome,
        labelQuarterPt(q.label),
        per.alvo,
        sim,
        real ? real.media : '',
        real ? real.total : 0,
        real ? real.atendem_n(per.alvo) : 0,
      ]);
    });
  });
  downloadCsv('historico_simulado_vs_realizado.csv',
    ['Perfil','Quarter','Alvo %','Cobertura simulada %','Cobertura real média %','Consultores no perfil','Atendem alvo'],
    rows);
}

function exportSimulacaoCompleta(){
  const params = getSimParams();
  const q = getAlvoQuarter ? getAlvoQuarter() : null;
  const labelQ = q ? labelQuarterPt(q.label) : '—';
  const cobL = calcularCapacidadePerfil('local', params.local);
  const cobV = calcularCapacidadePerfil('vint', params.vint);
  const cobI = calcularCapacidadePerfil('vinter', params.vinter);

  // Exporta 5 arquivos CSV separados (renomear no Excel se quiser unificar)
  // Estratégia: usa downloadCsv() que não tem dependência externa

  // ---- 1: Inputs ----
  const inputsRows = [
    ['Frequência mensal MCCP', params.local.freq, params.vint.freq, params.vinter.freq, 'Indústria 1-1,5'],
    ['Painel alvo', params.local.painel, params.vint.painel, params.vinter.painel, 'Oncologia 80-150'],
    ['Visitas/dia (capacidade)', params.local.visdia, params.vint.visdia, params.vinter.visdia, 'Indústria 5-7'],
    ['Dias úteis em campo/mês', params.local.dias, '-', '-', ''],
    ['Tempo em trânsito/semana (dias)', '-', params.vint.perda, '-', ''],
    ['Viagens aéreas/mês', '-', '-', params.vinter.viagens, ''],
    ['Dias perdidos por viagem', '-', '-', params.vinter.perdidos, ''],
    ['Cobertura alvo (%)', params.local.alvo, params.vint.alvo, params.vinter.alvo, 'Indústria 60-95%'],
    ['---', '', '', '', ''],
    ['Dias em campo/mês (calc)', cobL.dias_campo_mes, cobV.dias_campo_mes, cobI.dias_campo_mes, ''],
    ['Capacidade visitas/tri (calc)', cobL.capacidade_visitas_tri, cobV.capacidade_visitas_tri, cobI.capacidade_visitas_tri, ''],
    ['Necessário visitas/tri (calc)', cobL.visitas_necessarias_tri, cobV.visitas_necessarias_tri, cobI.visitas_necessarias_tri, ''],
    ['Cobertura possível (%)', cobL.cobertura_pct, cobV.cobertura_pct, cobI.cobertura_pct, ''],
  ];
  downloadCsv('simulador_1_inputs.csv',
    ['Parâmetro','Local','V.Interna','V.Interestadual','Fonte/Benchmark'],
    inputsRows);

  // ---- 2: Capacidade por GD ----
  const cs = getFilteredAtivos();
  const byGd = {};
  cs.forEach(c=>{
    const gd = c.gd_name || '(sem GD)';
    if(!byGd[gd]) byGd[gd] = {gd, total:0, local:0, vint:0, vinter:0};
    byGd[gd].total++;
    if(c.tipo_setor==='Local') byGd[gd].local++;
    else if(c.tipo_setor==='Viagem Interna') byGd[gd].vint++;
    else if(c.tipo_setor==='Viagem Interestadual') byGd[gd].vinter++;
  });
  const gdRows = Object.values(byGd).sort((a,b)=>a.gd.localeCompare(b.gd,'pt-BR')).map(g=>{
    const universal = Math.round((g.local*cobL.cobertura_pct + g.vint*cobV.cobertura_pct + g.vinter*cobI.cobertura_pct) / Math.max(1,g.total));
    return [g.gd, g.total, g.local, g.vint, g.vinter, cobL.cobertura_pct, cobV.cobertura_pct, cobI.cobertura_pct, universal];
  });
  downloadCsv('simulador_2_capacidade_gd.csv',
    ['GD','Time','Local','V.Interna','V.Interestadual','Cob.Local %','Cob.V.Int %','Cob.V.Inter %','Meta Universal %'],
    gdRows);

  // ---- 3: Atingimento por consultor ----
  const alvos = {'Local':params.local.alvo, 'Viagem Interna':params.vint.alvo, 'Viagem Interestadual':params.vinter.alvo};
  const atRows = cs.map(c=>{
    const qc = q ? (c.quarters||[]).find(x=>x.label===q.label) : null;
    const painel = getPainelMdms(c, qc);
    const visitados = qc ? (qc.mdms||[]) : [];
    const setP = new Set(painel);
    let dentro = 0;
    visitados.forEach(m=>{ if(setP.has(m)) dentro++; });
    const cobReal = painel.length>0 ? Math.round(dentro/painel.length*100) : '';
    const alvo = alvos[c.tipo_setor] || '';
    let status = '';
    if(cobReal==='' || alvo==='') status = 'sem dado';
    else if(cobReal >= alvo) status = 'atende';
    else if(cobReal >= alvo*0.85) status = 'próximo';
    else status = 'abaixo';
    return [c.nome, c.sales_force, c.gd_name, c.tipo_setor, painel.length, visitados.length, dentro, cobReal, alvo, status];
  });
  downloadCsv('simulador_3_atingimento_'+(q?q.label:'NA')+'.csv',
    ['Consultor','SF','GD','Perfil','Painel Q','Visitados Q','Dentro painel','Cobertura real %','Alvo %','Status'],
    atRows);

  // ---- 4: Calculadora de viagem ----
  const csVnt = cs.filter(c=>c.tipo_setor==='Viagem Interna' || c.tipo_setor==='Viagem Interestadual');
  const cvRows = [];
  csVnt.forEach(c=>{
    const defaults = getDefaultsSemanasUf(c);
    if(!defaults.length){
      cvRows.push([c.nome, c.sales_force, c.gd_name, c.tipo_setor, '', '', '', '', 'Sem histórico']);
      return;
    }
    defaults.forEach(d=>{
      const semEditada = getSemanasUfEditadas(c.ISID, d);
      const editado = CALC_VIAGEM_EDITS[c.ISID] && CALC_VIAGEM_EDITS[c.ISID][d.uf] !== undefined ? 'sim' : 'não';
      cvRows.push([c.nome, c.sales_force, c.gd_name, c.tipo_setor, d.uf, d.pct, d.semanas, semEditada, editado]);
    });
  });
  downloadCsv('simulador_4_calc_viagem.csv',
    ['Consultor','SF','GD','Perfil','UF','% histórico MAT','Semanas default (histórico)','Semanas planejadas','Editado?'],
    cvRows);

  // ---- 5: Diagnóstico ----
  const diagRows = cs.map(c=>{
    let esp = null;
    if(c.tipo_setor==='Local') esp = cobL.cobertura_pct;
    else if(c.tipo_setor==='Viagem Interna') esp = cobV.cobertura_pct;
    else if(c.tipo_setor==='Viagem Interestadual') esp = cobI.cobertura_pct;
    const real = c.mccp_pct_cumprido;
    let st = '';
    if(esp===null || real===null || real===undefined) st = 'sem dado';
    else if(real >= esp) st = 'acima';
    else if(real >= esp*0.85) st = 'próximo';
    else st = 'abaixo';
    return [c.nome, c.sales_force, c.gd_name, c.tipo_setor, c.painel_size, c.vis_dia_media, c.dias_trabalhados_mes, esp, real, st];
  });
  downloadCsv('simulador_5_diagnostico.csv',
    ['Consultor','SF','GD','Perfil','Painel','Vis/dia','Trab./mês','Capacidade esperada %','MCCP cumprido %','Status'],
    diagRows);
}

// ============================================================================
// HEATMAP 2D — painel × ausência → cor = vis/dia
// ============================================================================
function renderHeatmap(){
  // Onda 3 — eixo Y trocado: painel_size → cobertura mensal % (médicos únicos/mês ÷ painel × 100)
  // Painel absoluto não compara bem entre tipos de setor; cobertura mensal é métrica universal.
  let cs = getFilteredAtivos().filter(c=>c.painel_size>0 && c.pct_ausencia!==null && c.vis_dia_media>0 && c.medicos_unicos_mes>0);
  if(ST.hm_setor && ST.hm_setor!=='all'){
    cs = cs.filter(c=>c.tipo_setor===ST.hm_setor);
  }
  // Calcula cobertura mensal % por consultor
  cs = cs.map(c=>Object.assign({}, c, {
    cob_mensal_pct: Math.min(100, (c.medicos_unicos_mes / c.painel_size) * 100)
  }));
  if(!cs.length){
    document.getElementById('svg-heatmap').innerHTML = '<div style="text-align:center;color:var(--ink3);padding:24px;">Sem dados no recorte.</div>';
    return;
  }
  // Bins de cobertura mensal (Y)
  const binsP = [
    {min:0,    max:30,   label:'<30%'},
    {min:30,   max:50,   label:'30-50%'},
    {min:50,   max:70,   label:'50-70%'},
    {min:70,   max:200,  label:'70%+'},
  ];
  const binsA = [
    {min:0,    max:10,   label:'até 10%'},
    {min:10,   max:20,   label:'10-20%'},
    {min:20,   max:30,   label:'20-30%'},
    {min:30,   max:999,  label:'30%+'},
  ];
  // Construir matriz — cor = média de % COBERTURA MENSAL do grupo (não vis/dia)
  // Raissa: dado pedido é % cobertura de painel, não média/dia.
  const matrix = binsP.map(()=>binsA.map(()=>({n:0, sum:0})));
  cs.forEach(c=>{
    const ip = binsP.findIndex(b=>c.cob_mensal_pct>=b.min && c.cob_mensal_pct<b.max);
    const ia = binsA.findIndex(b=>c.pct_ausencia>=b.min && c.pct_ausencia<b.max);
    if(ip>=0 && ia>=0){
      matrix[ip][ia].n += 1;
      matrix[ip][ia].sum += c.cob_mensal_pct;  // cor = cobertura mensal %
    }
  });
  // Achar min/max para escala de cor
  let vmin=Infinity, vmax=-Infinity;
  matrix.forEach(row=>row.forEach(cell=>{
    if(cell.n>0){
      const m = cell.sum/cell.n;
      if(m<vmin) vmin=m;
      if(m>vmax) vmax=m;
    }
  }));
  if(vmin===Infinity){ vmin=0; vmax=1; }
  if(vmax===vmin) vmax = vmin + 0.1;

  // Cor: gradiente vermelho → amarelo → verde
  function colorScale(v){
    const t = (v - vmin) / (vmax - vmin);  // 0..1
    // vermelho (#C8102E) → amarelo (#F0C419) → verde (#00857C)
    if(t < 0.5){
      const k = t/0.5;
      const r = Math.round(200 + (240-200)*k);
      const g = Math.round(16 + (196-16)*k);
      const b = Math.round(46 + (25-46)*k);
      return `rgb(${r},${g},${b})`;
    } else {
      const k = (t-0.5)/0.5;
      const r = Math.round(240 + (0-240)*k);
      const g = Math.round(196 + (133-196)*k);
      const b = Math.round(25 + (124-25)*k);
      return `rgb(${r},${g},${b})`;
    }
  }

  const w = 760, h = 380;
  const padL = 110, padR = 130, padT = 40, padB = 60;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const cellW = innerW / binsA.length;
  const cellH = innerH / binsP.length;

  // Renderizar células
  let cells = '', texts = '';
  for(let ip=binsP.length-1; ip>=0; ip--){  // inverter para painel maior em cima
    for(let ia=0; ia<binsA.length; ia++){
      const cell = matrix[ip][ia];
      const x = padL + ia*cellW;
      // Inverter: ip=0 fica embaixo, ip=last fica em cima
      const row_y = binsP.length - 1 - ip;
      const y = padT + row_y*cellH;
      const m = cell.n>0? cell.sum/cell.n : null;
      const color = cell.n===0? '#F4F7FA' : colorScale(m);
      cells += `<rect class="hm-cell" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${cellW.toFixed(1)}" height="${cellH.toFixed(1)}" fill="${color}"/>`;
      if(cell.n>0){
        // texto branco se cor escura, escuro se clara
        const t_n = (m - vmin) / (vmax - vmin);
        const fontColor = (t_n < 0.25 || t_n > 0.75)? '#fff' : '#0C2340';
        texts += `<text x="${(x+cellW/2).toFixed(1)}" y="${(y+cellH/2-2).toFixed(1)}" text-anchor="middle" font-size="14" font-weight="700" fill="${fontColor}" font-family="Arial">${m.toFixed(0)}%</text>`;
        texts += `<text x="${(x+cellW/2).toFixed(1)}" y="${(y+cellH/2+14).toFixed(1)}" text-anchor="middle" font-size="10" fill="${fontColor}" font-family="Arial">n=${cell.n}</text>`;
      } else {
        texts += `<text x="${(x+cellW/2).toFixed(1)}" y="${(y+cellH/2+4).toFixed(1)}" text-anchor="middle" font-size="10" fill="#B8C7D3" font-family="Arial">—</text>`;
      }
    }
  }

  // Labels do eixo Y (painel) - bottom to top: <80, 80-100, 100-120, 120+
  let yLabels='';
  for(let ip=0; ip<binsP.length; ip++){
    const row_y = binsP.length - 1 - ip;
    const y = padT + row_y*cellH + cellH/2 + 4;
    yLabels += `<text x="${padL-10}" y="${y}" text-anchor="end" font-size="11.5" font-weight="600" fill="#0C2340" font-family="Arial">${binsP[ip].label}</text>`;
  }
  let xLabels='';
  for(let ia=0; ia<binsA.length; ia++){
    const x = padL + ia*cellW + cellW/2;
    xLabels += `<text x="${x.toFixed(1)}" y="${(padT+innerH+20).toFixed(1)}" text-anchor="middle" font-size="11.5" font-weight="600" fill="#0C2340" font-family="Arial">${binsA[ia].label}</text>`;
  }
  // Títulos eixos
  const ylabTitle = `<text x="${padL-90}" y="${padT+innerH/2}" text-anchor="middle" font-size="11" font-weight="700" fill="#2E4D6B" font-family="Arial" transform="rotate(-90, ${padL-90}, ${padT+innerH/2})">Cobertura mensal (%)</text>`;
  const xlabTitle = `<text x="${padL+innerW/2}" y="${padT+innerH+45}" text-anchor="middle" font-size="11" font-weight="700" fill="#2E4D6B" font-family="Arial">% Ausência (MAT)</text>`;

  // Barra de legenda à direita (gradient + min/max)
  const legX = padL + innerW + 24;
  const legW = 22;
  const legH = innerH;
  const grad = `<defs><linearGradient id="hmgrad" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0%" stop-color="${colorScale(vmin)}"/>
    <stop offset="50%" stop-color="${colorScale((vmin+vmax)/2)}"/>
    <stop offset="100%" stop-color="${colorScale(vmax)}"/>
  </linearGradient></defs>`;
  const legend = `<rect x="${legX}" y="${padT}" width="${legW}" height="${legH}" fill="url(#hmgrad)"/>
    <text x="${legX+legW+6}" y="${padT+10}" font-size="10.5" fill="#0C2340" font-family="Arial">${vmax.toFixed(0)}%</text>
    <text x="${legX+legW+6}" y="${padT+legH/2+4}" font-size="10.5" fill="#0C2340" font-family="Arial">${((vmin+vmax)/2).toFixed(0)}%</text>
    <text x="${legX+legW+6}" y="${padT+legH-2}" font-size="10.5" fill="#0C2340" font-family="Arial">${vmin.toFixed(0)}%</text>
    <text x="${legX+legW/2}" y="${padT-12}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#2E4D6B" font-family="Arial">% Cob.</text>`;

  document.getElementById('svg-heatmap').innerHTML = `
    <div style="font-size:11px;color:var(--ink2);margin-bottom:6px;">
      ${cs.length} consultor${cs.length===1?'':'es'} no recorte${ST.hm_setor!=='all'? ' (setor '+ST.hm_setor+')' : ''} ·
      Cor = % cobertura mensal de painel do grupo (verde alta, vermelho baixa) · n = nº de consultores na célula
    </div>
    <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
      ${grad}${cells}${texts}${yLabels}${xLabels}${ylabTitle}${xlabTitle}${legend}
    </svg>`;
}


// ============================================================================
// HISTOGRAMA + GAUSS (Item 21)
// ============================================================================
function histBars(values, w, h, meta, color, fmtVal, binSize, metaLabel){
  if(!values.length){
    return '<svg viewBox="0 0 '+w+' '+h+'"><text x="50%" y="50%" text-anchor="middle" fill="#8A9BAD" font-family="Arial" font-size="13">Sem dados</text></svg>';
  }
  const mu = values.reduce((a,b)=>a+b,0)/values.length;
  const vmin = Math.min(...values), vmax = Math.max(...values);

  // Calcular bins: ~10-14 bins de tamanho redondo
  let bw = binSize;
  if(!bw){
    const range = Math.max(1, vmax - vmin);
    const approx = range / 12;
    // arredondar para múltiplo "limpo"
    const mag = Math.pow(10, Math.floor(Math.log10(approx)));
    for(const m of [1, 2, 2.5, 5, 10]){
      if(m * mag >= approx){ bw = m * mag; break; }
    }
    if(!bw) bw = 10 * mag;
  }
  const start = Math.floor(vmin / bw) * bw;
  const end = Math.ceil(vmax / bw) * bw;
  const nBins = Math.max(1, Math.round((end - start) / bw));
  const counts = new Array(nBins).fill(0);
  values.forEach(v=>{
    let i = Math.floor((v - start) / bw);
    if(i < 0) i = 0;
    if(i >= nBins) i = nBins - 1;
    counts[i] += 1;
  });
  const cMax = Math.max(...counts, 1);

  const pad = {l:38, r:18, t:34, b:42};
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const colW = innerW / nBins;
  const sx = v => pad.l + (v - start) / (end - start) * innerW;
  const sy = c => pad.t + innerH - (c / cMax) * innerH;

  // Barras
  let bars = '';
  let dataLabels = '';
  for(let i=0; i<nBins; i++){
    const x = pad.l + i * colW;
    const yTop = sy(counts[i]);
    const hBar = pad.t + innerH - yTop;
    if(counts[i] > 0){
      bars += `<rect x="${(x+1.5).toFixed(2)}" y="${yTop.toFixed(2)}" width="${(colW-3).toFixed(2)}" height="${hBar.toFixed(2)}" fill="${color}" opacity="0.78" rx="2"/>`;
      // rótulo de valor em cima
      dataLabels += `<text x="${(x + colW/2).toFixed(2)}" y="${(yTop - 4).toFixed(2)}" text-anchor="middle" font-size="10" font-weight="700" fill="${color}" font-family="Arial">${counts[i]}</text>`;
    }
  }

  // Ticks X — limites dos bins
  let xtks = '';
  const tickStep = Math.max(1, Math.ceil(nBins / 8));
  for(let i=0; i<=nBins; i+=tickStep){
    const v = start + i * bw;
    const x = pad.l + i * colW;
    xtks += `<text x="${x.toFixed(2)}" y="${(pad.t + innerH + 14).toFixed(2)}" text-anchor="middle" font-size="9.5" fill="#8A9BAD" font-family="Arial">${fmtVal? fmtVal(v) : v.toFixed(0)}</text>`;
  }

  // Linha média e meta
  let lines = '';
  if(mu >= start && mu <= end){
    const xMu = sx(mu);
    lines += `<line x1="${xMu}" y1="${pad.t-14}" x2="${xMu}" y2="${pad.t+innerH}" stroke="${color}" stroke-width="1.5" stroke-dasharray="2,2"/>`;
    lines += `<text x="${xMu}" y="${pad.t-18}" text-anchor="middle" font-size="10" font-weight="700" fill="${color}" font-family="Arial">média ${fmtVal? fmtVal(mu) : mu.toFixed(1)}</text>`;
  }
  if(meta !== null && meta !== undefined && meta >= start && meta <= end){
    const xMeta = sx(meta);
    // Se passou metaLabel ("Você"), usar laranja vivo; senão azul-escuro padrão
    const corMeta = metaLabel ? '#FF6900' : '#0C2340';
    const labelMeta = metaLabel ? `${metaLabel} ${fmtVal? fmtVal(meta) : meta}` : `meta ${fmtVal? fmtVal(meta) : meta}`;
    lines += `<line x1="${xMeta}" y1="${pad.t-14}" x2="${xMeta}" y2="${pad.t+innerH}" stroke="${corMeta}" stroke-width="3" stroke-dasharray="4,3"/>`;
    lines += `<text x="${xMeta}" y="${(pad.t + innerH - 4).toFixed(2)}" text-anchor="middle" font-size="10" font-weight="700" fill="${corMeta}" stroke="#fff" stroke-width="3" paint-order="stroke" font-family="Arial">${labelMeta}</text>`;
  }

  // Eixo Y simples
  const yAxis = `<text x="${pad.l - 6}" y="${pad.t + 4}" text-anchor="end" font-size="9.5" fill="#8A9BAD" font-family="Arial">${cMax}</text>
                 <text x="${pad.l - 6}" y="${(pad.t + innerH).toFixed(2)}" text-anchor="end" font-size="9.5" fill="#8A9BAD" font-family="Arial">0</text>`;

  // Legenda eixo
  const xLabel = `<text x="${(pad.l + innerW/2).toFixed(2)}" y="${(h - 6).toFixed(2)}" text-anchor="middle" font-size="10" fill="#566778" font-family="Arial">cada barra agrupa faixas de ${bw} — altura = nº de consultores na faixa</text>`;

  const info = `<text x="${pad.l+innerW-4}" y="${pad.t-4}" text-anchor="end" font-size="10" fill="#8A9BAD" font-family="Arial">N=${values.length}</text>`;

  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
    <line x1="${pad.l}" y1="${pad.t+innerH}" x2="${pad.l+innerW}" y2="${pad.t+innerH}" stroke="#A8C4D4"/>
    ${bars}${dataLabels}${xtks}${lines}${info}${yAxis}${xLabel}
  </svg>`;
}

// ============================================================================
// SCATTER TEMPO DE CASA × COBERTURA MENSAL — curva de aprendizado
// ============================================================================
function renderVariabilidade(){
  const el = document.getElementById('kpi-variabilidade');
  if(!el) return;
  const cs = getFilteredAtivos().filter(c=>
    c.cv_vis_dia !== null && c.cv_vis_dia !== undefined &&
    c.vis_dia_media > 0  // só consultores ativos
  );
  if(cs.length < 5){
    el.innerHTML = '<div style="text-align:center;color:var(--ink3);padding:24px;grid-column:span 2;">Pontos insuficientes no recorte.</div>';
    return;
  }
  // Enriquecer com CV de cobertura mensal (calculado das séries do consultor)
  const seriesByISID = {};
  (DATA.series_consultor||[]).forEach(r=>{
    (seriesByISID[r.ISID] = seriesByISID[r.ISID] || []).push(r);
  });
  const csEnriched = cs.map(c=>{
    const arr = (seriesByISID[c.ISID]||[]).slice(-12);
    let cobSerie = [];
    if(c.painel_size > 0){
      cobSerie = arr.filter(r=>r.medicos > 0).map(r=>(r.medicos / c.painel_size) * 100);
    }
    let cobMedia = null, cobCV = null;
    if(cobSerie.length >= 3){
      cobMedia = cobSerie.reduce((s,v)=>s+v,0) / cobSerie.length;
      const std = Math.sqrt(cobSerie.reduce((s,v)=>s+(v-cobMedia)**2,0) / cobSerie.length);
      cobCV = cobMedia > 0 ? (std / cobMedia) * 100 : null;
    }
    return Object.assign({}, c, {cob_mensal_media: cobMedia, cob_mensal_cv: cobCV});
  });

  const sorted = [...csEnriched].sort((a,b)=>b.cv_vis_dia - a.cv_vis_dia);
  const instaveis = sorted.slice(0, 5);
  const consistentes = sorted.slice(-5).reverse();

  const cobTag = (c)=>{
    if(c.cob_mensal_media === null || c.cob_mensal_cv === null){
      return '<span style="color:var(--ink3);">—</span>';
    }
    const cor = c.cob_mensal_cv < 15 ? 'var(--teal)' :
                c.cob_mensal_cv < 30 ? 'var(--ink2)' : 'var(--warn)';
    return `<span style="color:var(--ink);font-weight:600;">${c.cob_mensal_media.toFixed(0)}%</span>
            <span style="color:${cor};font-size:10px;">±${c.cob_mensal_cv.toFixed(0)}%</span>`;
  };

  const renderLista = (lista, titulo, eyebrowColor, descricao) => `
    <div class="card" style="border-top:4px solid ${eyebrowColor};">
      <div class="card-title" style="color:${eyebrowColor};">${titulo}</div>
      <div style="font-size:11px;color:var(--ink3);margin-bottom:10px;">${descricao}</div>
      <table style="width:100%;font-size:11.5px;border-collapse:collapse;">
        <thead>
          <tr style="background:rgba(0,0,0,0.03);">
            <th style="text-align:left;padding:5px 6px;font-weight:600;color:var(--ink3);">Consultor</th>
            <th style="text-align:left;padding:5px 6px;font-weight:600;color:var(--ink3);font-size:10.5px;">SF</th>
            <th style="text-align:right;padding:5px 6px;font-weight:600;color:var(--ink3);" title="Coef. variação de vis/dia">CV vis/dia</th>
            <th style="text-align:right;padding:5px 6px;font-weight:600;color:var(--ink3);" title="Cobertura mensal média ± CV (variação) — se varia, o painel está instável mês a mês">Cob mensal ±CV</th>
          </tr>
        </thead>
        <tbody>
        ${lista.map(c=>`
          <tr style="border-top:1px solid var(--line);">
            <td style="padding:5px 6px;font-weight:600;color:var(--ink);">${escapeHtml(c.nome)}</td>
            <td style="padding:5px 6px;color:var(--ink2);font-size:10.5px;">${escapeHtml(c.sales_force||'')}</td>
            <td style="padding:5px 6px;text-align:right;font-weight:700;color:${eyebrowColor};">${c.cv_vis_dia.toFixed(0)}%</td>
            <td style="padding:5px 6px;text-align:right;">${cobTag(c)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  const guia = `
    <div style="grid-column:span 2;background:#F4F8FB;border-left:3px solid var(--purple);padding:10px 14px;margin-bottom:10px;font-size:11.5px;color:var(--ink2);line-height:1.5;">
      <strong style="color:var(--purple);">Como ler as duas variáveis juntas:</strong>
      CV alto de vis/dia <strong>+ cobertura mensal varia muito</strong> (±30%+) = painel inteiro instável, o consultor não replica a cobertura mês a mês.
      CV alto de vis/dia <strong>+ cobertura mensal estável</strong> (±&lt;15%) = ritmo varia mas o painel é coberto consistente (provável alternância entre viagens longas e dias locais).
      CV baixo + cobertura estável = candidato a benchmark.
    </div>`;

  el.innerHTML = guia +
    renderLista(instaveis, '⚠ Top 5 mais instáveis', '#C8102E',
      'CV alto de vis/dia. Veja se a cobertura mensal também varia (sinal de painel mal absorvido).') +
    renderLista(consistentes, '✓ Top 5 mais consistentes', '#00857C',
      'CV baixo. Se a cobertura mensal também é estável, são referência de boas práticas.');
}
function renderTendencia(){
  const el = document.getElementById('kpi-tendencia');
  if(!el) return;
  // Filtros de qualidade:
  // - slope disponível

  // - vis_dia_media > 0 (consultor ativo no MAT)
  // - visitas_3m > 0 (consultor não está em afastamento longo)
  //   Consultor sem visita há 3m+ não pode estar "em alta", mesmo que o slope histórico aponte isso
  // Onda 1: usa slope_vis_dia_6m (janela 6m) em vez de slope_vis_dia (MAT 12m).
  //   Captura melhor o momento atual, mas mantém robustez (≥5 pontos > 3 pontos puros).
  //   Afastados (Mariana, Cecchim, Adriano) já estão fora via getFilteredAtivos.
  const excluidos = [];
  const cs = getFilteredAtivos().filter(c=>{
    if(c.slope_vis_dia_6m === null || c.slope_vis_dia_6m === undefined) return false;
    if(!(c.vis_dia_media > 0)) return false;
    if(!(c.visitas_3m > 0)){
      excluidos.push(c.nome);
      return false;
    }
    return true;
  });
  if(cs.length < 5){
    el.innerHTML = '<div style="text-align:center;color:var(--ink3);padding:24px;grid-column:span 2;">Pontos insuficientes no recorte.</div>';
    return;
  }
  const sorted = [...cs].sort((a,b)=>b.slope_vis_dia_6m - a.slope_vis_dia_6m);
  const alta = sorted.slice(0, 10).filter(c=>c.slope_vis_dia_6m > 0);
  const queda = sorted.slice(-10).reverse().filter(c=>c.slope_vis_dia_6m < 0);

  // Sparkline mostrando série de 6 meses, com os 3 últimos em destaque vermelho
  function sparkline(serie){
    if(!serie || serie.length < 6) return '<span style="color:var(--ink3);font-size:10px;">—</span>';
    const W = 70, H = 22, PAD = 2;
    const max = Math.max(...serie, 0.1);
    const min = Math.min(...serie, 0);
    const range = Math.max(max - min, 0.5);
    const x = (i)=> PAD + (i/(serie.length-1)) * (W - 2*PAD);
    const y = (v)=> H - PAD - ((v-min)/range) * (H - 2*PAD);
    const ptos = serie.map((v,i)=>`${x(i)},${y(v)}`).join(' ');
    // path completo cinza
    const pBase = serie.map((v,i)=>`${i===0?'M':'L'}${x(i)} ${y(v)}`).join(' ');
    // path dos 3 últimos vermelho
    const last3 = serie.slice(-3);
    const startIdx = serie.length - 3;
    const pLast = last3.map((v,i)=>`${i===0?'M':'L'}${x(startIdx+i)} ${y(v)}`).join(' ');
    const dots = serie.map((v,i)=>{
      const isLast3 = i >= startIdx;
      return `<circle cx="${x(i)}" cy="${y(v)}" r="${isLast3?2:1.5}" class="${isLast3?'spark-pt-3m':'spark-pt-6m'}"/>`;
    }).join('');
    return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
      <path d="${pBase}" class="spark-6m-base"/>
      <path d="${pLast}" class="spark-3m-highlight"/>
      ${dots}
    </svg>`;
  }

  const renderLista = (lista, titulo, eyebrowColor, icone, descricao) => {
    if(!lista.length){
      return `<div class="card" style="border-top:4px solid ${eyebrowColor};">
        <div class="card-title" style="color:${eyebrowColor};">${icone} ${titulo}</div>
        <div style="font-size:11px;color:var(--ink3);margin-top:8px;font-style:italic;">Sem consultores no recorte.</div>
      </div>`;
    }
    // Detecta a janela média usada (3, 4, 5 ou 6 meses) — informa explicitamente o usuário
    const windowsUsadas = lista.map(c=>c.slope_window_n||0).filter(n=>n>0);
    const maxWin = windowsUsadas.length ? Math.max(...windowsUsadas) : 6;
    const minWin = windowsUsadas.length ? Math.min(...windowsUsadas) : 6;
    const windowLabel = minWin === maxWin ? `${maxWin} meses` : `${minWin}-${maxWin} meses`;
    return `
    <div class="card" style="border-top:4px solid ${eyebrowColor};">
      <div class="card-title" style="color:${eyebrowColor};">${icone} ${titulo}</div>
      <div style="font-size:11px;color:var(--ink3);margin-bottom:10px;">${descricao}</div>
      <table style="width:100%;font-size:11.5px;border-collapse:collapse;">
        <thead>
          <tr style="background:rgba(0,0,0,0.03);">
            <th style="text-align:left;padding:5px 6px;font-weight:600;color:var(--ink3);">Consultor</th>
            <th style="text-align:left;padding:5px 6px;font-weight:600;color:var(--ink3);font-size:10.5px;">SF</th>
            <th style="text-align:right;padding:5px 6px;font-weight:600;color:var(--ink3);" title="Inclinação da regressão linear de vis/dia">Slope (${windowLabel})</th>
            <th style="text-align:center;padding:5px 6px;font-weight:600;color:var(--ink3);">Série</th>
            <th style="text-align:right;padding:5px 6px;font-weight:600;color:var(--ink3);" title="Vis/dia média dos últimos 3 meses">Vis/dia 3m</th>
          </tr>
        </thead>
        <tbody>
        ${lista.map(c=>`
          <tr style="border-top:1px solid var(--line);">
            <td style="padding:5px 6px;font-weight:600;color:var(--ink);">${escapeHtml(c.nome)}</td>
            <td style="padding:5px 6px;color:var(--ink2);font-size:10.5px;">${escapeHtml(c.sales_force||'')}</td>
            <td style="padding:5px 6px;text-align:right;font-weight:700;color:${eyebrowColor};">${c.slope_vis_dia_6m>=0?'+':''}${c.slope_vis_dia_6m.toFixed(3)}</td>
            <td style="padding:5px 6px;text-align:center;">${sparkline(c.vd_6m_serie)}</td>
            <td style="padding:5px 6px;text-align:right;color:var(--ink2);">${(c.vd_3m_media||0).toFixed(2)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      <div style="font-size:10px;color:var(--ink3);margin-top:6px;font-style:italic;">
        Slope = variação de vis/dia/mês na janela disponível (${windowLabel}). Ideal: 6 meses fechados. ${maxWin < 6 ? `<strong style="color:var(--warn);">Atenção: poucos meses históricos carregados</strong> — slope sujeito a ruído.` : ''}
        ${maxWin >= 6 ? '· <span style="color:#C8102E;">●</span> últimos 3 meses em destaque · <span style="color:#8A9BAD;">●</span> 3 meses anteriores' : ''}
      </div>
    </div>`;
  };

  const blocoExcluidos = excluidos.length > 0
    ? `<div style="grid-column:span 2;background:#F4F8FB;border-left:3px solid #6B3FA0;padding:8px 12px;margin-bottom:10px;font-size:11px;color:var(--ink2);line-height:1.5;">
         <strong style="color:var(--purple);">${excluidos.length} consultor(es) excluído(s)</strong> sem visitas nos últimos 3 meses (não dá pra classificar tendência):
         <span style="color:var(--ink3);">${excluidos.map(escapeHtml).join(' · ')}</span>
       </div>` : '';

  el.innerHTML = blocoExcluidos +
    renderLista(alta, 'Top 10 em alta (6m)', '#00857C', '↑',
      'Slope positivo nos últimos 6 meses. Ritmo crescendo.') +
    renderLista(queda, 'Top 10 em queda (6m)', '#C8102E', '↓',
      'Slope negativo nos últimos 6 meses. Ritmo caindo. Investigar afastamentos, fadiga ou problemas de rotina.');
}
function renderCurvaAprendizado(){
  // Substitui o scatter antigo por 3 blocos: leitura pronta + quadrante 2×2 + tabela detalhada
  const cs = getFilteredAtivos().filter(c=>
    c.meses_no_setor !== null && c.meses_no_setor !== undefined &&
    c.painel_size > 0 && c.medicos_unicos_mes > 0
  );

  const elLeit = document.getElementById('curva-leitura');
  const elQuad = document.getElementById('curva-quadrante');
  const elDet  = document.getElementById('curva-detalhe');
  if(!elLeit || !elQuad || !elDet) return;

  if(cs.length < 5){
    elLeit.innerHTML = '<div class="card"><div style="text-align:center;color:var(--ink3);padding:24px;">Pontos insuficientes no recorte.</div></div>';
    elQuad.innerHTML = '';
    elDet.innerHTML = '';
    return;
  }

  // Calcular cobertura mensal de cada consultor
  const pts = cs.map(c=>({
    c,
    meses: c.meses_no_setor,
    cob: Math.round(c.medicos_unicos_mes / c.painel_size * 100),
  }));

  // Cobertura mediana do recorte (corte performance)
  const cobsOrdenadas = pts.map(p=>p.cob).sort((a,b)=>a-b);
  const mediana = cobsOrdenadas.length % 2 === 0
    ? Math.round((cobsOrdenadas[cobsOrdenadas.length/2-1] + cobsOrdenadas[cobsOrdenadas.length/2])/2)
    : cobsOrdenadas[Math.floor(cobsOrdenadas.length/2)];

  // ============================================================================
  // BLOCO 1 — Leitura pronta + faixas
  // ============================================================================
  const faixas = [
    {label:'0-12m',    nome:'Novato (até 1 ano)',  ini:0,  fim:12,  cor:'#6B3FA0'},
    {label:'12-36m',   nome:'Em consolidação',     ini:12, fim:36,  cor:'#0C2340'},
    {label:'36-72m',   nome:'Veterano (3-6 anos)', ini:36, fim:72,  cor:'#00857C'},
    {label:'72m+',     nome:'Senior (6+ anos)',    ini:72, fim:999, cor:'#D4900A'},
  ];
  const faixasComDados = faixas.map(f=>{
    const grupo = pts.filter(p=>p.meses >= f.ini && p.meses < f.fim);
    const cobMed = grupo.length ? Math.round(grupo.reduce((a,b)=>a+b.cob,0)/grupo.length) : null;
    return {...f, n:grupo.length, cobMed};
  });

  // Síntese: comparar primeira faixa não-vazia com a mais experiente
  const fComDados = faixasComDados.filter(f=>f.n>0);
  let sintese = '';
  if(fComDados.length >= 2){
    const novato = fComDados[0];
    const senior = fComDados[fComDados.length-1];
    const dif = senior.cobMed - novato.cobMed;
    if(Math.abs(dif) < 5){
      sintese = `<strong>O time atinge produtividade plena rapidamente.</strong> A cobertura mensal é praticamente igual entre <strong>${novato.label}</strong> (${novato.cobMed}%) e <strong>${senior.label}</strong> (${senior.cobMed}%) — sem ramp-up significativo.`;
    } else if(dif > 0){
      sintese = `<strong>Existe curva de aprendizado.</strong> Consultores de <strong>${novato.label}</strong> têm ${novato.cobMed}% de cobertura, enquanto <strong>${senior.label}</strong> atinge ${senior.cobMed}% (+${dif}pp). Tempo de casa contribui para performance.`;
    } else {
      sintese = `<strong>Veteranos estão abaixo dos novatos.</strong> <strong>${novato.label}</strong>: ${novato.cobMed}% · <strong>${senior.label}</strong>: ${senior.cobMed}% (${dif}pp). Investigar fadiga ou painéis sobredimensionados nos veteranos.`;
    }
  } else {
    sintese = `Análise limitada — apenas uma faixa de tempo com dados suficientes no recorte.`;
  }

  const miniCards = faixasComDados.map(f=>{
    if(f.n === 0){
      return `<div class="card" style="border-top:3px solid ${f.cor};opacity:0.5;">
        <div style="font-size:10.5px;color:var(--ink3);letter-spacing:.05em;text-transform:uppercase;">${f.label}</div>
        <div style="font-size:12px;color:var(--ink2);margin:6px 0 8px;">${f.nome}</div>
        <div style="font-size:24px;font-weight:700;color:var(--ink3);">—</div>
        <div style="font-size:11px;color:var(--ink3);">sem consultores</div>
      </div>`;
    }
    return `<div class="card" style="border-top:3px solid ${f.cor};">
      <div style="font-size:10.5px;color:var(--ink3);letter-spacing:.05em;text-transform:uppercase;">${f.label}</div>
      <div style="font-size:12px;color:var(--ink2);margin:6px 0 8px;">${f.nome}</div>
      <div style="font-size:24px;font-weight:700;color:${f.cor};">${f.cobMed}%</div>
      <div style="font-size:11px;color:var(--ink3);">${f.n} consultor(es) · cobertura média</div>
    </div>`;
  }).join('');

  elLeit.innerHTML = `
    <div class="card" style="background:linear-gradient(135deg, #F4F8FB 0%, #EFEDF7 100%);border-left:4px solid var(--purple);margin-bottom:14px;">
      <div style="font-size:11px;letter-spacing:.1em;color:var(--purple);text-transform:uppercase;font-weight:700;margin-bottom:6px;">Leitura do time</div>
      <div style="font-size:14px;color:var(--ink);line-height:1.55;">${sintese}</div>
    </div>
    <div class="split2" style="grid-template-columns:repeat(4, 1fr);">${miniCards}</div>
  `;

  // ============================================================================
  // BLOCO 2 — Quadrante 2×2
  // ============================================================================
  // Limiares: tempo 12m (novato/veterano) · performance: mediana do recorte
  const novatos     = pts.filter(p=>p.meses <  12);
  const veteranos   = pts.filter(p=>p.meses >= 12);
  const novatoAcima = novatos.filter(p=>p.cob >= mediana);
  const novatoAbaixo= novatos.filter(p=>p.cob <  mediana);
  const vetAcima    = veteranos.filter(p=>p.cob >= mediana);
  const vetAbaixo   = veteranos.filter(p=>p.cob <  mediana);

  const renderQuadrante = (lista, titulo, eyebrow, cor, descricao) => {
    if(!lista.length){
      return `<div class="card" style="border-top:4px solid ${cor};opacity:0.5;">
        <div style="font-size:10.5px;color:${cor};letter-spacing:.08em;text-transform:uppercase;font-weight:700;margin-bottom:6px;">${eyebrow}</div>
        <div style="font-size:14px;font-weight:700;color:var(--ink);margin-bottom:6px;">${titulo}</div>
        <div style="font-size:11px;color:var(--ink3);line-height:1.5;margin-bottom:10px;">${descricao}</div>
        <div style="font-size:11px;color:var(--ink3);font-style:italic;">Nenhum consultor neste grupo no recorte atual.</div>
      </div>`;
    }
    const top = [...lista].sort((a,b)=>b.cob - a.cob).slice(0, 8);
    return `<div class="card" style="border-top:4px solid ${cor};">
      <div style="font-size:10.5px;color:${cor};letter-spacing:.08em;text-transform:uppercase;font-weight:700;margin-bottom:6px;">${eyebrow}</div>
      <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:6px;">
        <div style="font-size:14px;font-weight:700;color:var(--ink);">${titulo}</div>
        <div style="font-size:18px;font-weight:700;color:${cor};">${lista.length}</div>
      </div>
      <div style="font-size:11px;color:var(--ink3);line-height:1.5;margin-bottom:10px;">${descricao}</div>
      <div style="font-size:11.5px;color:var(--ink);line-height:1.6;">
        ${top.map(p=>`<div style="border-top:1px solid var(--line);padding:4px 0;">
          <span style="font-weight:600;">${escapeHtml(p.c.nome)}</span>
          <span style="float:right;color:${cor};font-weight:700;">${p.cob}%</span>
          <div style="font-size:10px;color:var(--ink3);">${p.meses.toFixed(0)}m no setor · ${escapeHtml(p.c.sales_force||'')}</div>
        </div>`).join('')}
        ${lista.length > 8 ? `<div style="margin-top:6px;font-size:10px;color:var(--ink3);font-style:italic;">+ ${lista.length - 8} consultor(es) — ver detalhe expandido</div>` : ''}
      </div>
    </div>`;
  };

  elQuad.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:8px;">
      ${renderQuadrante(novatoAcima, 'Novato performando', '↗ destaque positivo', '#00857C',
        `Menos de 12m no setor com cobertura ≥${mediana}%. Candidatos a reconhecimento e replicação.`)}
      ${renderQuadrante(vetAcima, 'Veterano benchmark', '★ referência', '#0C2340',
        `12m+ no setor com cobertura ≥${mediana}%. Use como referência de boas práticas.`)}
    </div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;">
      ${renderQuadrante(novatoAbaixo, 'Novato em ramp-up', '⏱ acompanhar', '#D4900A',
        `Menos de 12m no setor com cobertura <${mediana}%. Esperado durante adaptação — acompanhar evolução.`)}
      ${renderQuadrante(vetAbaixo, 'Veterano abaixo da curva', '⚠ investigar', '#C8102E',
        `12m+ no setor com cobertura <${mediana}%. Investigar painéis sobredimensionados, fadiga ou rotina ineficiente.`)}
    </div>
    <div style="font-size:10.5px;color:var(--ink3);margin-top:10px;font-style:italic;text-align:center;">
      Cortes: 12 meses (novato/veterano) · mediana do recorte (${mediana}%) para acima/abaixo da curva
    </div>
  `;

  // ============================================================================
  // BLOCO 3 — Tabela detalhada (colapsada)
  // ============================================================================
  const sorted = [...pts].sort((a,b)=>b.cob - a.cob);
  elDet.innerHTML = `
    <table style="width:100%;font-size:11.5px;border-collapse:collapse;">
      <thead>
        <tr style="background:rgba(0,0,0,0.03);">
          <th style="text-align:left;padding:6px 8px;font-weight:600;color:var(--ink3);">Consultor</th>
          <th style="text-align:left;padding:6px 8px;font-weight:600;color:var(--ink3);">SF</th>
          <th style="text-align:left;padding:6px 8px;font-weight:600;color:var(--ink3);">GD</th>
          <th style="text-align:left;padding:6px 8px;font-weight:600;color:var(--ink3);">Perfil setor</th>
          <th style="text-align:right;padding:6px 8px;font-weight:600;color:var(--ink3);">Tempo (m)</th>
          <th style="text-align:right;padding:6px 8px;font-weight:600;color:var(--ink3);">Painel</th>
          <th style="text-align:right;padding:6px 8px;font-weight:600;color:var(--ink3);">Únicos/mês</th>
          <th style="text-align:right;padding:6px 8px;font-weight:600;color:var(--ink3);">Cobertura</th>
          <th style="text-align:left;padding:6px 8px;font-weight:600;color:var(--ink3);">Classificação</th>
        </tr>
      </thead>
      <tbody>
        ${sorted.map(p=>{
          const novato = p.meses < 12;
          const acima = p.cob >= mediana;
          let classif = '', cor = 'var(--ink3)';
          if(novato && acima)  { classif = '↗ Novato performando'; cor = '#00857C'; }
          else if(novato)      { classif = '⏱ Novato em ramp-up';  cor = '#D4900A'; }
          else if(acima)       { classif = '★ Veterano benchmark'; cor = '#0C2340'; }
          else                 { classif = '⚠ Veterano abaixo';    cor = '#C8102E'; }
          return `<tr style="border-top:1px solid var(--line);">
            <td style="padding:5px 8px;font-weight:600;">${escapeHtml(p.c.nome)}</td>
            <td style="padding:5px 8px;color:var(--ink2);">${escapeHtml(p.c.sales_force||'')}</td>
            <td style="padding:5px 8px;color:var(--ink2);">${escapeHtml(p.c.gd_name||'—')}</td>
            <td style="padding:5px 8px;color:var(--ink2);">${escapeHtml(p.c.tipo_setor||'—')}</td>
            <td style="padding:5px 8px;text-align:right;">${p.meses.toFixed(0)}</td>
            <td style="padding:5px 8px;text-align:right;">${p.c.painel_size}</td>
            <td style="padding:5px 8px;text-align:right;">${p.c.medicos_unicos_mes.toFixed(1)}</td>
            <td style="padding:5px 8px;text-align:right;font-weight:700;color:${cor};">${p.cob}%</td>
            <td style="padding:5px 8px;font-size:10.5px;color:${cor};">${classif}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
    <div style="text-align:right;margin-top:10px;">
      <button class="btn-exp" onclick="exportCurvaAprendizado()">↓ Exportar CSV</button>
    </div>
  `;
  aplicarSortEmTodasTabelas();
}

// Toggle do detalhe expandido
function toggleCurvaDetalhe(){
  const el = document.getElementById('curva-detalhe');
  const btn = document.getElementById('btn-curva-detalhe');
  if(!el || !btn) return;
  const visible = el.style.display !== 'none';
  el.style.display = visible ? 'none' : 'block';
  btn.innerHTML = visible
    ? '▸ Ver detalhe expandido (todos os consultores)'
    : '▾ Ocultar detalhe expandido';
}

// Export CSV
function exportCurvaAprendizado(){
  const cs = getFilteredAtivos().filter(c=>
    c.meses_no_setor !== null && c.meses_no_setor !== undefined &&
    c.painel_size > 0 && c.medicos_unicos_mes > 0
  );
  const pts = cs.map(c=>({c, meses:c.meses_no_setor, cob:Math.round(c.medicos_unicos_mes/c.painel_size*100)}));
  const cobsOrd = pts.map(p=>p.cob).sort((a,b)=>a-b);
  const mediana = cobsOrd.length % 2 === 0
    ? Math.round((cobsOrd[cobsOrd.length/2-1] + cobsOrd[cobsOrd.length/2])/2)
    : cobsOrd[Math.floor(cobsOrd.length/2)];
  const rows = pts.sort((a,b)=>b.cob - a.cob).map(p=>{
    const novato = p.meses < 12;
    const acima = p.cob >= mediana;
    let classif = '';
    if(novato && acima)  classif = 'Novato performando';
    else if(novato)      classif = 'Novato em ramp-up';
    else if(acima)       classif = 'Veterano benchmark';
    else                 classif = 'Veterano abaixo';
    return [p.c.nome, p.c.sales_force, p.c.gd_name, p.c.tipo_setor,
            p.meses.toFixed(0), p.c.painel_size, p.c.medicos_unicos_mes.toFixed(1),
            p.cob, classif];
  });
  downloadCsv('curva_aprendizado.csv',
    ['Consultor','SF','GD','Perfil','Tempo (m)','Painel','Únicos/mês','Cobertura %','Classificação'],
    rows);
}


function renderHistograms(){
  const csFilt = getFilteredAtivos();
  const isSingleConsultor = ST.consultor!=='__all__';

  // Decidir o que mostrar:
  // - Se um único consultor: peers da SF dele (Brasil inteiro), com linha vertical do consultor + linha média
  // - Senão: distribuição dos consultores filtrados
  let valsPainel, valsVis, subPainel, subVis, mePainel, meVis;
  if(isSingleConsultor && csFilt.length===1){
    const c = csFilt[0];
    const sf = c.sales_force;
    // Peers: todos os consultores da mesma SF (independente de GD/filtro)
    const peers = DATA.consultores.filter(x=>x.sales_force===sf);
    valsPainel = peers.map(p=>p.painel_size).filter(v=>v>0);
    valsVis = peers.map(p=>p.vis_dia_media).filter(v=>v>0);
    mePainel = c.painel_size;
    meVis = c.vis_dia_media;
    subPainel = `${peers.length} consultor${peers.length===1?'':'es'} da SF ${sf} (Brasil) · linha laranja = ${c.nome.split(' ')[0]} · linha tracejada = média da SF`;
    subVis = subPainel;
  } else {
    valsPainel = csFilt.map(c=>c.painel_size).filter(v=>v>0);
    valsVis = csFilt.map(c=>c.vis_dia_media).filter(v=>v>0);
    mePainel = null;
    meVis = null;
    subPainel = valsPainel.length + ' consultores · cada barra agrupa quantos têm painel naquela faixa · linha tracejada = média';
    subVis = valsVis.length + ' consultores · cada barra agrupa quantos atingem aquela média de visitas/dia · linha tracejada = média';
  }
  document.getElementById('hist-painel-sub').textContent = subPainel;
  document.getElementById('hist-vis-sub').textContent = subVis;
  document.getElementById('svg-hist-painel').innerHTML =
    histBars(valsPainel, 460, 240, mePainel, '#6B3FA0', v=>v.toFixed(0), 10, isSingleConsultor? 'Você' : null);
  document.getElementById('svg-hist-visitas').innerHTML =
    histBars(valsVis, 460, 240, meVis, '#D4900A', v=>v.toFixed(1), 0.5, isSingleConsultor? 'Você' : null);
}

// ============================================================================
// TABELA SALES FORCE (Itens 20, 22) — centralizada + condicional
// ============================================================================
function renderSF(){
  // Esconder bloco se consultor único selecionado
  const block = document.getElementById('sf-block');
  if(ST.consultor!=='__all__'){
    block.style.display='none';
    return;
  } else {
    block.style.display='';
  }

  // Onda 4 — usa janela global da Visão Geral (overview_janela)
  // Mapeia 'parcial' → vis_dia_parcial / pct_ausencia_parcial
  const j = ST.overview_janela || ST.sf_janela || 'mat';
  const visKey = j==='1m'      ? 'vis_dia_1m'
                : j==='3m'      ? 'vis_dia_3m'
                : j==='parcial' ? 'vis_dia_parcial'
                : 'vis_dia_media';
  const ausKey = j==='1m'      ? 'pct_ausencia_1m'
                : j==='3m'      ? 'pct_ausencia_3m'
                : j==='parcial' ? 'pct_ausencia_parcial'
                : 'pct_ausencia';
  const labelJ = j==='1m'      ? 'último mês'
                : j==='3m'      ? 'últimos 3m'
                : j==='parcial' ? 'mês parcial'
                : 'MAT 12m';
  // Atualizar header
  const th = document.getElementById('sf-th-visdia');
  if(th) setThLabel(th, 'Visitas/dia (' + labelJ + ')');
  const thA = document.getElementById('sf-th-ausencia');
  if(thA) setThLabel(thA, '% Ausência (' + labelJ + ')');

  // Agregar SFs considerando filtro GD + EXCLUIR AFASTADOS (Onda 4 — Raissa)
  const cs = getFilteredByGD().filter(c=>!isAfastado(c));
  const bySf = {};
  cs.forEach(c=>{
    const k = c.sales_force || '(sem SF)';
    if(!bySf[k]) bySf[k] = {sales_force:k, list:[]};
    bySf[k].list.push(c);
  });
  const sfs = Object.values(bySf).map(g=>{
    const csP = g.list.filter(c=>c.painel_size>0);
    const csV = g.list.filter(c=>(c[visKey]||0)>0);
    const csA = g.list.filter(c=>(c[ausKey]||0)>0);
    return {
      sales_force: g.sales_force,
      n: g.list.length,
      painel_medio: csP.length? mean(csP.map(c=>c.painel_size)) : null,
      vis_dia_medio: csV.length? mean(csV.map(c=>c[visKey])) : null,
      pct_ausencia_medio: csA.length? mean(csA.map(c=>c[ausKey])) : null,
      n_viagem_inter: g.list.filter(c=>c.tipo_setor==='Viagem Interestadual').length,
      n_viagem_intra: g.list.filter(c=>c.tipo_setor==='Viagem Interna').length,
      n_local: g.list.filter(c=>c.tipo_setor==='Local').length
    };
  }).sort((a,b)=>b.n - a.n);  // DESC por nº de consultores (Raissa)

  const tbody = document.querySelector('#tbl-sf tbody');
  tbody.innerHTML = sfs.map(r=>`
    <tr>
      <td class="nm">${escapeHtml(r.sales_force)}</td>
      <td class="num">${r.n}</td>
      <td class="num">${r.painel_medio!==null? fmt(r.painel_medio,1) : '—'}</td>
      <td class="num">${r.vis_dia_medio!==null? fmt(r.vis_dia_medio,2) : '—'}</td>
      <td class="num">${r.pct_ausencia_medio!==null? pct(r.pct_ausencia_medio) : '—'}</td>
      <td class="num">${r.n_viagem_inter}</td>
      <td class="num">${r.n_viagem_intra}</td>
      <td class="num">${r.n_local}</td>
    </tr>`).join('');
  aplicarSortEmTodasTabelas();
}

function setSfJanela(j){
  ST.sf_janela = j;
  document.querySelectorAll('#sf-janela-toggle button').forEach(b=>{
    b.classList.toggle('active', b.dataset.jan===j);
  });
  renderSF();
}

function setSetorJanela(j){
  ST.setor_janela = j;
  document.querySelectorAll('#setor-jan-toggle button').forEach(b=>{
    b.classList.toggle('active', b.dataset.jan===j);
  });
  renderSetor();
}

// Onda 2 — toggle MAT/3m/1m da tabela Detalhe
function setDetailJanela(j){
  ST.detail_janela = j;
  document.querySelectorAll('.detail-jan').forEach(b=>{
    b.classList.toggle('active', b.dataset.jan===j);
  });
  // Atualiza labels dos headers afetados
  const thVis = document.getElementById('th-vis-dia');
  const thVisitas = document.getElementById('th-visitas');
  const thAus = document.getElementById('th-ausencia');
  if(j === '3m'){
    if(thVis) setThLabel(thVis, 'Vis/dia (3m)');
    if(thVisitas) setThLabel(thVisitas, 'Visitas (3m)');
    if(thAus) setThLabel(thAus, '% Ausência (3m)');
  } else if(j === '1m'){
    if(thVis) setThLabel(thVis, 'Vis/dia (1m)');
    if(thVisitas) setThLabel(thVisitas, 'Visitas (1m)');
    if(thAus) setThLabel(thAus, '% Ausência (1m)');
  } else {
    if(thVis) setThLabel(thVis, 'Vis/dia (MAT)');
    if(thVisitas) setThLabel(thVisitas, 'Visitas (MAT)');
    if(thAus) setThLabel(thAus, '% Ausência (MAT)');
  }
  renderDetail();
}

// ============================================================================
// DETAIL TABLE
// ============================================================================
function statusTooltip(kind){
  if(kind==='painel') return 'Painel ' + ST.sim_painel + ' = verde · ≥' + Math.round(ST.sim_painel*0.9) + ' = amarelo · < = vermelho';
  if(kind==='vis')    return 'Vis/dia ' + ST.sim_visdia.toFixed(1) + ' = verde · ≥' + (ST.sim_visdia*0.85).toFixed(1) + ' = amarelo · < = vermelho';
  if(kind==='aus')    return 'Ausência ≤15% verde · ≤22% amarelo · >22% vermelho';
  return '';
}

function statusIcons(c){
  const sP = statusPainel(c.painel_size);
  const sV = statusVis(c.vis_dia_media);
  const sA = statusAus(c.pct_ausencia);
  const m = {ok:'s-ok', warn:'s-warn', bad:'s-bad', empty:'s-empty'};
  return `<span class="status-cell">
    <span class="${m[sP]}" data-tip="Painel ${c.painel_size||0} · ${statusTooltip('painel')}">■</span>
    <span class="${m[sV]}" data-tip="Vis/dia ${(c.vis_dia_media||0).toFixed(2)} · ${statusTooltip('vis')}">▲</span>
    <span class="${m[sA]}" data-tip="${c.pct_ausencia!==null? c.pct_ausencia.toFixed(1)+'%' : '—'} · ${statusTooltip('aus')}">●</span>
  </span>`;
}

function renderDetail(){
  // Atualiza legenda com metas atuais
  const lgMp = document.getElementById('lg-mp');
  const lgMv = document.getElementById('lg-mv');
  if(lgMp) lgMp.textContent = ST.sim_painel;
  if(lgMv) lgMv.textContent = ST.sim_visdia.toFixed(1);

  const cs = getFilteredConsultores().slice();
  cs.sort((a,b)=>{
    const va=a[ST.detail_sort], vb=b[ST.detail_sort];
    if(typeof va==='number' && typeof vb==='number') return ST.detail_dir*(va-vb);
    return ST.detail_dir*String(va||'').localeCompare(String(vb||''),'pt-BR');
  });
  const tbody = document.querySelector('#tbl-detail tbody');
  tbody.innerHTML = cs.map(c=>{
    const mccpFreqDisplay = c.mccp_q_disponivel===false
      ? `<span style="color:var(--ink3);" data-tip="Sem MCCP no quarter atual. Último ciclo: ${c.ultimo_ciclo_mccp||'—'}">—</span>`
      : fmt(c.mccp_freq_media_tri,2);
    const mccpPctDisplay = c.mccp_q_disponivel===false ? '—' : pct(c.mccp_pct_cumprido);
    const mccpPanelDisplay = c.mccp_q_disponivel===false ? '—' : fmt(c.mccp_panel);
    // Janela selecionada via toggle (Onda 2)
    const jan = ST.detail_janela || 'mat';
    let visDiaCell, visitasCell, ausenciaCell;
    if(jan === '3m'){
      visDiaCell   = fmt(c.vis_dia_3m, 2);
      visitasCell  = fmt(c.visitas_3m);
      ausenciaCell = pct(c.pct_ausencia_3m);
    } else if(jan === '1m'){
      visDiaCell   = fmt(c.vis_dia_1m, 2);
      visitasCell  = fmt(c.visitas_1m);
      ausenciaCell = pct(c.pct_ausencia_1m);
    } else {
      visDiaCell   = fmt(c.vis_dia_media, 2);
      visitasCell  = fmt(c.visitas_12m);
      ausenciaCell = pct(c.pct_ausencia);
    }
    // Cobertura mensal: méd. únicos/mês ÷ painel oficial
    const cobMensal = (c.painel_size > 0 && c.medicos_unicos_mes > 0)
      ? Math.round(c.medicos_unicos_mes / c.painel_size * 100) : null;
    const corCobMensal = cobMensal === null ? 'var(--ink3)' :
                         cobMensal >= 70 ? 'var(--teal)' :
                         cobMensal >= 50 ? 'var(--ink2)' :
                         'var(--warn)';
    // Tag visual de afastado
    const tagAfastado = isAfastado(c)
      ? `<span class="tag-afastado" title="${escapeHtml(c.afastado_motivo||'')} — ${escapeHtml(c.afastado_periodo||'')}">Afastado</span>`
      : '';
    // Tag visual MCCP não publicado (em vez de mostrar "0" ou "—" sem contexto)
    const mccpPanelCell = c.mccp_q_disponivel===false
      ? `<span class="tag-mccp-na" title="${escapeHtml(c.mccp_motivo_indisponivel||'MCCP Q corrente não publicado')}">MCCP n/d</span>`
      : fmt(c.mccp_panel);
    return `
    <tr${isAfastado(c) ? ' style="background:#FDF6E7;"' : ''}>
      <td class="nm">${escapeHtml(c.nome)}${tagAfastado}</td>
      <td>${escapeHtml(c.sales_force||'')}</td>
      <td>${escapeHtml(c.gd_name||'—')}</td>
      <td>${escapeHtml(c.tipo_setor||'—')}</td>
      <td class="num">${c.meses_no_setor!==null && c.meses_no_setor!==undefined? fmt(c.meses_no_setor,0) : '—'}</td>
      <td class="num">${fmt(c.painel_size)}</td>
      <td class="num">${visDiaCell}</td>
      <td class="num">${visitasCell}</td>
      <td class="num">${fmt(c.medicos_unicos_mes,1)}</td>
      <td class="num" style="color:${corCobMensal};font-weight:${cobMensal!==null?'700':'400'};">${cobMensal===null?'—':cobMensal+'%'}</td>
      <td class="num">${fmt(c.freq_medico_mes,2)}</td>
      <td class="num">${ausenciaCell}</td>
      <td class="num">${mccpPanelCell}</td>
      <td class="num">${mccpFreqDisplay}</td>
      <td class="num">${mccpPctDisplay}</td>
      <td class="num">${pct(c.pct_dentro_mccp)}</td>
      <td class="num">${pct(c.pct_overlap_intra)}</td>
      <td class="num">${pct(c.pct_overlap_cross_naoclass)}</td>
      <td class="num" style="font-weight:600;color:${
        c.turnover_pct_3m===null||c.turnover_pct_3m===undefined ? 'var(--ink3)' :
        c.turnover_flag==='estavel'     ? 'var(--teal)' :
        c.turnover_flag==='equilibrado' ? 'var(--ink2)' :
        c.turnover_flag==='rotativo'    ? 'var(--warn)' :
        c.turnover_flag==='volatil'     ? 'var(--danger)' : 'var(--ink3)'
      };" title="${
        c.turnover_flag==='estavel'     ? 'Estável: pouca rotação no painel' :
        c.turnover_flag==='equilibrado' ? 'Equilibrado: renovação saudável' :
        c.turnover_flag==='rotativo'    ? 'Rotativo: painel girando, atenção' :
        c.turnover_flag==='volatil'     ? 'Volátil: a cada mês um painel diferente' : ''
      }">${c.turnover_pct_3m===null||c.turnover_pct_3m===undefined ? '—' : c.turnover_pct_3m.toFixed(0)+'%'}</td>
    </tr>`;
  }).join('');
  document.getElementById('d-count').textContent = cs.length + ' consultor(es) exibido(s).';
  aplicarSortEmTodasTabelas();
}


// ============================================================================
// AUSÊNCIAS — médias mensais + composição + sazonalidade (Itens 23-26)
// ============================================================================
function renderAbsence(){
  // Onda 4 — filtro de arquétipo (tipo_setor) aplicado em KPIs e composição.
  // Permite ver como o tempo se distribui pra cada perfil de deslocamento.
  let cs = getFilteredAtivos();
  const arq = ST.aus_arquetipo || 'all';
  if(arq !== 'all'){
    cs = cs.filter(c => c.tipo_setor === arq);
  }

  // Atualiza info à direita do filtro
  const infoEl = document.getElementById('aus-arq-info');
  if(infoEl){
    infoEl.textContent = `${cs.length} consultor${cs.length===1?'':'es'} no recorte${arq!=='all' ? ` · arquétipo ${arq}` : ''}`;
  }

  if(!cs.length){
    document.getElementById('abs-kpis').innerHTML = '<div style="grid-column:span 3;text-align:center;color:var(--ink3);padding:20px;">Sem consultores no recorte de arquétipo.</div>';
    document.getElementById('svg-abs-comp').innerHTML = '';
    renderAbsSazonalidade();
    renderAbsRanking(cs);
    return;
  }

  const meanKey = k => {
    const vs = cs.map(c=>c[k]).filter(v=>v!==null && v!==undefined);
    return vs.length? mean(vs) : 0;
  };
  // Snap pra fração de dia (0,25 / 0,5 / 0,75 / 1)
  const snap = v => {
    if(v===null||v===undefined||isNaN(v)) return 0;
    return Math.round(v*4)/4;
  };
  const items = [
    {lbl:'Tempo fora do campo (% MAT)', val: pct(meanKey('pct_ausencia')), sub:'Ausências totais ÷ dias úteis (MAT 12m)', cls:'danger'},
    {lbl:'Dias em campo / mês', val: fmt(meanKey('dias_trabalhados_mes'),1), sub:'Em média, por consultor', cls:'teal'},
    {lbl:'Tempo fora total / mês', val: fmt(meanKey('ausencia_mes'),1), sub:'Soma de todas as categorias abaixo', cls:'danger'},
    {lbl:'Viagem / mês', val: fmt(meanKey('viagem_mes'),1), sub:'Dias de deslocamento — análise-chave para setores multi-UF', extra_cls:'cat-viagem'},
    {lbl:'Reunião/escritório / mês', val: fmt(meanKey('reunioes_mes'),1), sub:'Reuniões fora do campo', extra_cls:'cat-produtiva'},
    {lbl:'Congresso / mês', val: fmt(meanKey('congressos_mes'),1), sub:'Congressos / simpósios', extra_cls:'cat-produtiva'},
    {lbl:'Treinamento / mês', val: fmt(meanKey('treinamento_mes'),1), sub:'Treinamentos formais', extra_cls:'cat-produtiva'},
    {lbl:'Gestão de território / mês', val: fmt(meanKey('gestao_mes'),1), sub:'Atividades administrativas do território', extra_cls:'cat-produtiva'},
    {lbl:'Pessoais / mês', val: fmt(snap(meanKey('pessoais_mes')),2), sub:'Férias, licenças, day off (snap 0,25/0,5/0,75/1)', extra_cls:'cat-pessoal'},
  ];
  document.getElementById('abs-kpis').innerHTML = items.map(it=>`
    <div class="card ${it.extra_cls||''}">
      <div class="card-title">${it.lbl}</div>
      <div class="card-num ${it.cls||''}">${it.val}</div>
      <div class="card-sub">${it.sub}</div>
    </div>`).join('');

  renderAbsComp(cs);
  renderAbsSazonalidade();
  renderAbsRanking(cs);
  aplicarSortEmTodasTabelas();
}

// Toggle de arquétipo no deep dive de ausências
function setAusArquetipo(arq){
  ST.aus_arquetipo = arq;
  document.querySelectorAll('.aus-arquetipo').forEach(b=>{
    b.classList.toggle('active', b.dataset.arq===arq);
  });
  renderAbsence();
}

function renderAbsComp(cs){
  // OPÇÃO B (escolha da Raissa): duas barras separadas com escalas próprias.
  // Gráfico A: "Em campo" sozinho (escala 0..20 dias)
  // Gráfico B: "Tempo fora" desmembrado por categoria (escala 0..max categoria)

  // Valores
  const inField = mean(cs.map(c=>c.trabalhados_mes||0).filter(v=>v!==null));
  const cats = [
    {key:'viagem_mes',     label:'Viagem',            color:'#D4900A', destaque:true},
    {key:'reunioes_mes',   label:'Reunião/escritório',color:'#6B3FA0'},
    {key:'congressos_mes', label:'Congresso',         color:'#9F7BBF'},
    {key:'treinamento_mes',label:'Treinamento',       color:'#6ECEB2'},
    {key:'gestao_mes',     label:'Gestão território', color:'#A8C4D4'},
    {key:'pessoais_mes',   label:'Pessoal/licença',   color:'#C8102E'},
  ];
  // Compatibilidade: payload antigo usava "deslocamento_mes"; novo usa "viagem_mes"
  const vals = cats.map(c=>{
    let key = c.key;
    let arr = cs.map(x=>x[key]).filter(v=>v!==null && v!==undefined);
    if(!arr.length && key==='viagem_mes'){
      arr = cs.map(x=>x.deslocamento_mes).filter(v=>v!==null && v!==undefined);
    }
    return {...c, val: arr.length? mean(arr) : 0};
  });
  const totalFora = vals.reduce((s,c)=>s+c.val,0);
  const totalDays = inField + totalFora;

  // Layout SVG: 2 painéis lado a lado
  const w = 920, h = 320;
  const padOuter = 16;
  const gap = 30;
  const colW = (w - 2*padOuter - gap) / 2;
  // Pad interno de cada painel
  const padL = 130, padR = 16, padT = 36, padB = 38;
  const innerW = colW - padL - padR;
  const innerH = h - padT - padB;

  // ===== Painel A: Em campo =====
  const Ax = padOuter;
  const niceMaxA = nice(Math.max(inField, totalDays)*1.05) || 20;
  // Grid eixo X
  let gridA = '', ticksA = '';
  for(let i=0;i<=4;i++){
    const v = niceMaxA * i / 4;
    const x = Ax + padL + (innerW * i / 4);
    gridA += `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT+innerH}" stroke="#E8EEF3" stroke-dasharray="2,3"/>`;
    ticksA += `<text x="${x}" y="${padT+innerH+15}" text-anchor="middle" font-size="9.5" fill="#8A9BAD" font-family="Arial">${v.toFixed(0)}</text>`;
  }
  const barY = padT + innerH/2 - 18;
  const barH = 36;
  const bwA = (inField/niceMaxA) * innerW;
  const barA = `<rect x="${Ax+padL}" y="${barY}" width="${bwA.toFixed(2)}" height="${barH}" fill="#00857C" rx="3"/>`;
  const lblA = `<text x="${Ax+padL-10}" y="${barY+barH/2+5}" text-anchor="end" font-size="12" font-weight="700" fill="#0C2340" font-family="Arial">Em campo</text>`;
  const valA = bwA > 80
    ? `<text x="${Ax+padL+bwA-8}" y="${barY+barH/2+5}" text-anchor="end" font-size="12" font-weight="700" fill="#fff" font-family="Arial">${fmt(inField,1)} dias</text>`
    : `<text x="${Ax+padL+bwA+6}" y="${barY+barH/2+5}" text-anchor="start" font-size="12" font-weight="700" fill="#00857C" font-family="Arial">${fmt(inField,1)} dias</text>`;
  const titA = `<text x="${Ax+padL+innerW/2}" y="${padT-12}" text-anchor="middle" font-size="11.5" font-weight="700" fill="#00857C" font-family="Arial">Em campo (dias produtivos)</text>`;
  const xLblA = `<text x="${Ax+padL+innerW/2}" y="${h-padOuter+2}" text-anchor="middle" font-size="10" fill="#566778" font-family="Arial">dias por mês — escala 0 a ${niceMaxA.toFixed(0)}</text>`;

  // ===== Painel B: Tempo fora desmembrado =====
  const Bx = padOuter + colW + gap;
  const maxCat = Math.max(...vals.map(v=>v.val), 0.1);
  const niceMaxB = nice(maxCat*1.15);
  const rowH = innerH / vals.length;
  const barHB = Math.min(22, rowH * 0.65);
  let gridB='', ticksB='';
  for(let i=0;i<=4;i++){
    const v = niceMaxB * i / 4;
    const x = Bx + padL + (innerW * i / 4);
    gridB += `<line x1="${x}" y1="${padT}" x2="${x}" y2="${padT+innerH}" stroke="#E8EEF3" stroke-dasharray="2,3"/>`;
    ticksB += `<text x="${x}" y="${padT+innerH+15}" text-anchor="middle" font-size="9.5" fill="#8A9BAD" font-family="Arial">${v.toFixed(1)}</text>`;
  }
  let barsB='', lblsB='', valsB='';
  vals.forEach((c,i)=>{
    const y = padT + i*rowH + (rowH-barHB)/2;
    const cy = y + barHB/2 + 4;
    const bw = (c.val/niceMaxB)*innerW;
    const stroke = c.destaque ? ' stroke="#0C2340" stroke-width="1.5"' : '';
    barsB += `<rect x="${Bx+padL}" y="${y}" width="${bw.toFixed(2)}" height="${barHB}" fill="${c.color}" rx="3"${stroke}/>`;
    const weight = c.destaque? '700' : '500';
    const labelExtra = c.destaque? ' ★' : '';
    lblsB += `<text x="${Bx+padL-10}" y="${cy}" text-anchor="end" font-size="11" font-weight="${weight}" fill="${c.destaque? '#0C2340' : '#566778'}" font-family="Arial">${c.label}${labelExtra}</text>`;
    const pctTxt = totalFora>0? ' ('+Math.round(c.val/totalFora*100)+'%)' : '';
    const txt = fmt(c.val,1) + ' dia' + (c.val===1?'':'s') + pctTxt;
    if(bw > 100){
      valsB += `<text x="${Bx+padL+bw-6}" y="${cy}" text-anchor="end" font-size="10.5" font-weight="700" fill="#fff" font-family="Arial">${txt}</text>`;
    } else {
      valsB += `<text x="${Bx+padL+bw+5}" y="${cy}" text-anchor="start" font-size="10.5" font-weight="700" fill="${c.color}" font-family="Arial">${txt}</text>`;
    }
  });
  const titB = `<text x="${Bx+padL+innerW/2}" y="${padT-12}" text-anchor="middle" font-size="11.5" font-weight="700" fill="#C8102E" font-family="Arial">Tempo fora do campo (por categoria)</text>`;
  const xLblB = `<text x="${Bx+padL+innerW/2}" y="${h-padOuter+2}" text-anchor="middle" font-size="10" fill="#566778" font-family="Arial">dias por mês — escala 0 a ${niceMaxB.toFixed(1)}</text>`;

  document.getElementById('svg-abs-comp').innerHTML = `
    <div style="font-size:12px;color:var(--ink2);margin-bottom:8px;">
      <strong>${fmt(totalDays,1)}</strong> dias úteis por mês em média (${cs.length} consultor${cs.length===1?'':'es'} no recorte) ·
      <strong style="color:#00857C">${fmt(inField,1)}</strong> em campo +
      <strong style="color:#C8102E">${fmt(totalFora,1)}</strong> fora
      <span style="color:var(--ink3);font-size:11px;">· ★ = categoria-foco (Viagem)</span>
    </div>
    <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
      ${gridA}<line x1="${Ax+padL}" y1="${padT}" x2="${Ax+padL}" y2="${padT+innerH}" stroke="#A8C4D4"/>
      ${barA}${lblA}${valA}${titA}${ticksA}${xLblA}
      ${gridB}<line x1="${Bx+padL}" y1="${padT}" x2="${Bx+padL}" y2="${padT+innerH}" stroke="#A8C4D4"/>
      ${barsB}${lblsB}${valsB}${titB}${ticksB}${xLblB}
    </svg>`;
}

function renderAbsSazonalidade(){
  // Onda 4 — Reformulado: BARRAS COM DATA LABELS em vez de scatter.
  // Agrupa consultores em faixas de ausência e mostra média de cobertura por faixa.
  // Cliente entende melhor barra+rotulo que scatter+regressão.
  const host = document.getElementById('svg-aus-cob-scatter') || document.getElementById('svg-abs-saz');
  const leiHost = document.getElementById('aus-cob-leitura');
  if(!host) return;
  const cs = getFilteredAtivos().filter(c=>
    c.painel_size > 0 &&
    c.medicos_unicos_mes > 0 &&
    c.pct_ausencia !== null && c.pct_ausencia !== undefined
  );
  if(cs.length < 5){
    host.innerHTML = '<div style="text-align:center;color:var(--ink3);padding:20px;">Pontos insuficientes para o filtro atual.</div>';
    if(leiHost) leiHost.innerHTML = '';
    return;
  }
  // Calcula cobertura por consultor
  const pts = cs.map(c=>({
    nome: c.nome, sf: c.sales_force||'',
    aus: c.pct_ausencia,
    cob: Math.min(100, (c.medicos_unicos_mes/c.painel_size)*100),
  }));
  // Faixas de ausência
  const faixas = [
    {min:0,  max:10, label:'até 10%'},
    {min:10, max:20, label:'10-20%'},
    {min:20, max:30, label:'20-30%'},
    {min:30, max:999, label:'30%+'},
  ];
  const grupos = faixas.map(f=>{
    const inFaixa = pts.filter(p=>p.aus>=f.min && p.aus<f.max);
    const cobs = inFaixa.map(p=>p.cob);
    return {
      label: f.label,
      n: inFaixa.length,
      cobMedia: cobs.length ? cobs.reduce((a,b)=>a+b,0)/cobs.length : 0,
      ausMedia: inFaixa.length ? inFaixa.reduce((s,p)=>s+p.aus,0)/inFaixa.length : 0,
    };
  });

  const w = 720, h = 380, padL = 70, padR = 30, padT = 30, padB = 60;
  const yMax = 100;  // cobertura é %
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const nGr = grupos.length;
  const bandW = innerW / nGr;
  const barW = bandW * 0.55;

  // Grid + ticks Y
  let grid='', ytL='';
  for(let i=0;i<=5;i++){
    const yv = (yMax * i)/5;
    const py = padT + innerH - (yv/yMax)*innerH;
    grid += `<line x1="${padL}" y1="${py}" x2="${w-padR}" y2="${py}" stroke="#EAEDEF"/>`;
    ytL += `<text x="${padL-8}" y="${py+4}" font-size="10" fill="#3D4047" text-anchor="end" font-weight="600">${yv.toFixed(0)}%</text>`;
  }

  // Barras + data labels
  let bars='', xLabels='', dataLabels='', nLabels='';
  grupos.forEach((g, i)=>{
    const cx = padL + bandW*i + bandW/2;
    const yBar = padT + innerH - (g.cobMedia/yMax)*innerH;
    const hBar = (g.cobMedia/yMax)*innerH;
    const cor = g.cobMedia >= 60 ? '#00857C' : g.cobMedia >= 40 ? '#D4900A' : '#C8102E';
    bars += `<rect x="${cx-barW/2}" y="${yBar}" width="${barW}" height="${hBar}" fill="${cor}" fill-opacity="0.85" stroke="${cor}" stroke-width="1">
              <title>${g.label} — Cobertura média: ${g.cobMedia.toFixed(1)}% (${g.n} consultor${g.n===1?'':'es'})</title>
            </rect>`;
    // Data label em cima da barra (cobertura)
    if(g.n > 0){
      dataLabels += `<text x="${cx}" y="${yBar-7}" font-size="13" font-weight="700" fill="${cor}" text-anchor="middle">${g.cobMedia.toFixed(0)}%</text>`;
      nLabels += `<text x="${cx}" y="${padT+innerH-4}" font-size="10" font-weight="600" fill="#fff" text-anchor="middle">n=${g.n}</text>`;
    }
    xLabels += `<text x="${cx}" y="${h-padB+18}" font-size="11.5" fill="#3D4047" font-weight="600" text-anchor="middle">${g.label}</text>`;
  });

  // Eixos
  const axes = `
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${h-padB}" stroke="#1B1F23" stroke-width="1.2"/>
    <line x1="${padL}" y1="${h-padB}" x2="${w-padR}" y2="${h-padB}" stroke="#1B1F23" stroke-width="1.2"/>
    <text x="${w/2}" y="${h-12}" font-size="11.5" font-weight="700" fill="#3D4047" text-anchor="middle">Faixa de % ausência (MAT 12m)</text>
    <text x="18" y="${padT+innerH/2}" font-size="11.5" font-weight="700" fill="#3D4047" text-anchor="middle" transform="rotate(-90 18 ${padT+innerH/2})">% Cobertura de painel mensal (média da faixa)</text>`;

  host.innerHTML = `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
    ${grid}${bars}${dataLabels}${nLabels}${axes}${ytL}${xLabels}
  </svg>`;

  // Leitura interpretativa
  const grNonEmpty = grupos.filter(g=>g.n>0);
  if(grNonEmpty.length >= 2){
    const cobMax = grNonEmpty[0].cobMedia;
    const cobMin = grNonEmpty[grNonEmpty.length-1].cobMedia;
    const queda = cobMax - cobMin;
    let texto;
    if(queda > 15){
      texto = `<strong style="color:var(--warn);">Há sinal de impacto:</strong> consultores com ausência ${grNonEmpty[grNonEmpty.length-1].label} cobrem em média <strong>${cobMin.toFixed(0)}%</strong> do painel, enquanto os com ausência ${grNonEmpty[0].label} cobrem <strong>${cobMax.toFixed(0)}%</strong>. Queda de ${queda.toFixed(0)} pontos percentuais entre as faixas extremas.`;
    } else if(queda > 5){
      texto = `<strong style="color:var(--ink2);">Impacto moderado:</strong> diferença de ${queda.toFixed(0)}pp entre a faixa de menor ausência (${cobMax.toFixed(0)}% de cobertura) e a maior (${cobMin.toFixed(0)}%).`;
    } else {
      texto = `<strong>Sem padrão claro:</strong> cobertura mensal se mantém parecida entre as faixas de ausência (variação ${queda.toFixed(0)}pp). Outros fatores devem explicar a cobertura.`;
    }
    if(leiHost) leiHost.innerHTML = texto;
  }
}
function renderAbsRanking(cs){
  // Onda 4 — janela MAT/3m/1m via toggle
  const j = ST.abs_janela || 'mat';
  const pctKey = j==='1m' ? 'pct_ausencia_1m' : j==='3m' ? 'pct_ausencia_3m' : 'pct_ausencia';
  // Atualiza header da coluna %
  const thPct = document.getElementById('abs-th-pct');
  if(thPct) setThLabel(thPct, j==='1m' ? '% Aus. (1m)' : j==='3m' ? '% Aus. (3m)' : '% Aus. (MAT)');

  // Filtra consultores com ausência > 0 na janela escolhida
  const filt = cs.filter(c=>c[pctKey] !== null && c[pctKey] !== undefined);
  // Sort DESC pela % de ausência da janela (default ranking)
  const sorted = filt.slice().sort((a,b)=>(b[pctKey]||0) - (a[pctKey]||0)).slice(0, 30);
  const tbody = document.querySelector('#tbl-absence tbody');
  tbody.innerHTML = sorted.map(c=>`
    <tr>
      <td class="nm" style="cursor:pointer;" onclick="focusConsultor('${c.ISID}')">${escapeHtml(c.nome)}</td>
      <td>${escapeHtml(c.sales_force||'')}</td>
      <td>${escapeHtml(c.gd_name||'—')}</td>
      <td class="num">${fmt(c.trabalhados_mes,1)}</td>
      <td class="num">${fmt(c.ausencia_mes,1)}</td>
      <td class="num">${fmt(c.viagem_mes||c.deslocamento_mes,1)}</td>
      <td class="num">${fmt(c.reunioes_mes,1)}</td>
      <td class="num">${fmt(c.congressos_mes,1)}</td>
      <td class="num">${fmt(c.treinamento_mes,1)}</td>
      <td class="num">${fmt(c.gestao_mes,1)}</td>
      <td class="num">${fmt(c.pessoais_mes,1)}</td>
      <td class="num">${pct(c[pctKey])}</td>
    </tr>`).join('') || '<tr><td colspan="12" style="text-align:center;color:var(--ink3);padding:14px;">Sem consultores no filtro.</td></tr>';
}

function setAbsJanela(j){
  ST.abs_janela = j;
  document.querySelectorAll('.abs-jan').forEach(b=>{
    b.classList.toggle('active', b.dataset.jan===j);
  });
  renderAbsRanking(getFilteredAtivos());
}

// Onda 4 — Toggle de tipo de setor no heatmap (botões antes não disparavam nada)
function setHeatmapSetor(s){
  ST.hm_setor = s;
  document.querySelectorAll('.setor-hm').forEach(b=>{
    b.classList.toggle('active', b.dataset.setor===s);
  });
  renderHeatmap();
}

function focusConsultor(isid){
  ST.consultor = isid;
  document.getElementById('fc').value = isid;
  renderAll();
}


// ============================================================================
// SVG LINE com data labels (Items 27-28)
// ============================================================================
function svgLine(rows, valKey, xKey, w, h, color, label, fmtFn, showLabels, highlightDrop){
  if(!rows.length){
    return '<svg viewBox="0 0 '+w+' '+h+'"><text x="50%" y="50%" text-anchor="middle" fill="#8A9BAD" font-family="Arial" font-size="13">Sem dados</text></svg>';
  }
  const pad = {l:46, r:24, t:22, b:42};
  const innerW = w-pad.l-pad.r, innerH = h-pad.t-pad.b;
  const vmax = nice(Math.max(...rows.map(r=>r[valKey]||0))*1.12) || 1;
  const stepX = rows.length>1? innerW/(rows.length-1) : 0;
  let grid='';
  for(let i=0;i<=4;i++){
    const y = pad.t + innerH*i/4;
    const v = vmax*(1-i/4);
    grid += `<line x1="${pad.l}" y1="${y}" x2="${pad.l+innerW}" y2="${y}" stroke="#D6E4ED"/>`;
    grid += `<text x="${pad.l-6}" y="${y+3}" text-anchor="end" font-size="9.5" fill="#8A9BAD" font-family="Arial">${fmtFn? fmtFn(v) : v.toFixed(0)}</text>`;
  }
  // X labels — proteção contra colagem (distância mínima)
  let xLabels='';
  const labelStep = Math.max(1, Math.ceil(rows.length/8));
  const minPxX = 42;
  const candXIdx = [];
  rows.forEach((r,i)=>{
    if(i%labelStep===0 || i===rows.length-1) candXIdx.push(i);
  });
  const keepX = new Set();
  let lastKeptXX = Infinity;
  for(let j=candXIdx.length-1; j>=0; j--){
    const i = candXIdx[j];
    const xPos = pad.l + i*stepX;
    if(lastKeptXX - xPos >= minPxX || j===candXIdx.length-1){
      keepX.add(i); lastKeptXX = xPos;
    }
  }
  rows.forEach((r,i)=>{
    if(!keepX.has(i)) return;
    const x = pad.l + i*stepX;
    xLabels += `<text x="${x.toFixed(2)}" y="${pad.t+innerH+16}" text-anchor="middle" font-size="10" fill="#566778" font-family="Arial">${fmtMonth(r[xKey])}</text>`;
  });
  // Path
  let pts = rows.map((r,i)=>{
    const x = pad.l + i*stepX;
    const y = pad.t + innerH - ((r[valKey]||0)/vmax)*innerH;
    return [x,y,r[valKey]];
  });
  const path = 'M' + pts.map(p=>p[0]+','+p[1]).join(' L');
  const area = path + ` L${pts[pts.length-1][0]},${pad.t+innerH} L${pts[0][0]},${pad.t+innerH} Z`;
  let dots = pts.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="${color}" stroke="#fff" stroke-width="1"/>`).join('');

  // Highlight da maior queda mês-a-mês (Item 13 da revisão Raissa)
  let dropMarker = '';
  if(highlightDrop && pts.length >= 2){
    let maxDropPct = 0, dropIdx = -1;
    for(let i=1; i<pts.length; i++){
      const prev = pts[i-1][2] || 0;
      const curr = pts[i][2] || 0;
      if(prev > 0){
        const dropPct = (prev - curr) / prev;
        if(dropPct > maxDropPct){ maxDropPct = dropPct; dropIdx = i; }
      }
    }
    if(dropIdx >= 0 && maxDropPct >= 0.05){
      const p = pts[dropIdx];
      const prevVal = pts[dropIdx-1][2] || 0;
      const dropAbs = prevVal - (p[2]||0);
      dropMarker = `
        <circle cx="${p[0].toFixed(2)}" cy="${p[1].toFixed(2)}" r="7" fill="none" stroke="#C8102E" stroke-width="2"/>
        <circle cx="${p[0].toFixed(2)}" cy="${p[1].toFixed(2)}" r="11" fill="none" stroke="#C8102E" stroke-width="1" opacity="0.4"/>
        <text x="${p[0].toFixed(2)}" y="${(p[1]+22).toFixed(2)}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#C8102E" font-family="Arial">↓ ${(maxDropPct*100).toFixed(0)}% (${fmtFn? fmtFn(dropAbs) : dropAbs.toFixed(1)})</text>`;
    }
  }
  // Data labels — com proteção contra colagem (distância mínima entre labels)
  let dataLabels='';
  if(showLabels!==false){
    const lblStep = Math.max(1, Math.ceil(rows.length/12));
    const minPxBetween = 30; // distância mínima em px do viewBox
    let lastLabelX = -Infinity;
    // 1ª passada: índices candidatos no step natural + último
    const candIdx = [];
    pts.forEach((p,i)=>{
      if(i%lblStep===0 || i===pts.length-1) candIdx.push(i);
    });
    // 2ª passada: pinta de trás pra frente garantindo distância
    // (Prioriza o último ponto — mais importante — e vai voltando)
    const keep = new Set();
    let lastKeptX = Infinity;
    for(let j=candIdx.length-1; j>=0; j--){
      const i = candIdx[j];
      const x = pts[i][0];
      if(lastKeptX - x >= minPxBetween || j===candIdx.length-1){
        keep.add(i); lastKeptX = x;
      }
    }
    pts.forEach((p,i)=>{
      if(!keep.has(i)) return;
      const txt = fmtFn? fmtFn(p[2]) : (p[2]||0).toFixed(1);
      const offsetY = p[1] < 28 ? 14 : -7;
      dataLabels += `<text x="${p[0].toFixed(2)}" y="${(p[1]+offsetY).toFixed(2)}" text-anchor="middle" font-size="9.5" font-weight="700" fill="${color}" font-family="Arial">${txt}</text>`;
    });
  }
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
    ${grid}
    <path d="${area}" fill="${color}" opacity="0.10"/>
    <path d="${path}" stroke="${color}" stroke-width="2" fill="none"/>
    ${dots}${dropMarker}${dataLabels}${xLabels}
  </svg>`;
}

// ============================================================================
// TIMELINE
// ============================================================================
function renderTimeline(){
  // Onda 3: incluir REVISITAS junto com únicos no segundo gráfico (mesmo SVG, 2 séries)
  // Revisitas/mês = (visitas - médicos únicos)  ← total de visitas "extras" ao mesmo médico
  let visdiaRows, medRows, ausRows, revisitaRows, visTotalRows;
  if(ST.gd==='__all__' && ST.sales_force==='__all__' && ST.consultor==='__all__'){
    const visTeam = DATA.series_team.visitas || [];
    visdiaRows = visTeam.map(r=>({ym:r.ym, val:r.vis_dia_team||0}));
    medRows = visTeam.map(r=>({ym:r.ym, val:r.medicos_unicos_time||0}));
    visTotalRows = visTeam.map(r=>({ym:r.ym, val:r.visitas||r.visitas_time||0}));
    ausRows = (DATA.series_team.ausencia||[]).map(r=>({ym:r.ym, val:r.pct_ausencia||0}));
  } else {
    const isids = new Set(getFilteredAtivos().map(c=>c.ISID));
    const filt = DATA.series_consultor.filter(r=>isids.has(r.ISID) && r.ym);
    const byYm = {};
    filt.forEach(r=>{
      if(!byYm[r.ym]) byYm[r.ym] = {ym:r.ym, visitas:0, dias_ativos:0, medicos:0, ausencia:0, uteis:0};
      byYm[r.ym].visitas += (r.visitas||0);
      byYm[r.ym].dias_ativos += (r.dias_ativos||0);
      byYm[r.ym].medicos += (r.medicos||r.medicos_unicos||0);
      byYm[r.ym].ausencia += (r.ausencia||0);
      byYm[r.ym].uteis += (r.uteis||0);
    });
    const arr = Object.values(byYm).sort((a,b)=>a.ym.localeCompare(b.ym));
    visdiaRows = arr.map(o=>({ym:o.ym, val: o.dias_ativos? o.visitas/o.dias_ativos : 0}));
    medRows = arr.map(o=>({ym:o.ym, val: o.medicos}));
    visTotalRows = arr.map(o=>({ym:o.ym, val: o.visitas}));
    ausRows = arr.map(o=>({ym:o.ym, val: o.uteis? o.ausencia/o.uteis*100 : 0}));
  }
  // Cortar séries em meses fechados
  visdiaRows = clipToCurrent(visdiaRows).filter(r=>r.val>0);
  medRows = clipToCurrent(medRows).filter(r=>r.val>0);
  visTotalRows = clipToCurrent(visTotalRows).filter(r=>r.val>0);
  ausRows = clipToCurrent(ausRows).filter(r=>r.val!==null && r.val!==undefined);

  // Revisitas: visitas - únicos. Pareia por ym.
  const medByYm = {}; medRows.forEach(r=>{ medByYm[r.ym] = r.val; });
  revisitaRows = visTotalRows
    .filter(r=>medByYm[r.ym] !== undefined)
    .map(r=>({ym:r.ym, val: Math.max(0, r.val - medByYm[r.ym])}));

  document.getElementById('svg-tl-visdia').innerHTML =
    svgLine(visdiaRows, 'val', 'ym', 460, 240, '#00857C', 'Visitas por dia ativo', v=>v.toFixed(1), true, true);

  // Segundo gráfico: duas linhas (únicos em roxo + revisitas em laranja pontilhado), eixo único
  document.getElementById('svg-tl-medicos').innerHTML = renderLineDuo(
    medRows, revisitaRows, 460, 260,
    'Médicos únicos vs Revisitas'
  );

  // Leitura conjunta vis/dia × únicos × revisitas (correlação Pearson)
  renderRevisitaLeitura(visdiaRows, medRows, revisitaRows);

  // Gráfico combinado: Cobertura mensal de painel × % Ausência (eixos duplos)
  renderCobAusTemporal();

  // Scatter painel × ausência
  renderScatter();
}

// Renderiza duas linhas no mesmo SVG (únicos sólida + revisitas pontilhada)
// Onda 4 — Refeito como BARRAS SOBREPOSTAS com data labels e % revisita.
// Cliente entendia mal as duas linhas; barras explicam melhor a relação visitas/únicos.
function renderLineDuo(rowsA, rowsB, w, h, title){
  // rowsA = únicos por mês (sólido), rowsB = revisitas por mês (sobreposto)
  const padL = 56, padR = 20, padT = 26, padB = 50;
  const allYm = [...new Set([...rowsA.map(r=>r.ym), ...rowsB.map(r=>r.ym)])].sort().slice(-12);
  if(allYm.length < 2) return '<div style="text-align:center;color:var(--ink3);padding:24px;">Histórico insuficiente.</div>';
  const aMap = {}; rowsA.forEach(r=>{ aMap[r.ym]=r.val; });
  const bMap = {}; rowsB.forEach(r=>{ bMap[r.ym]=r.val; });
  // Para cada mês: total visitas = únicos + revisitas
  const data = allYm.map(ym=>{
    const u = aMap[ym] || 0;
    const r = bMap[ym] || 0;
    return {ym, unicos:u, revisitas:r, total: u+r, pctRev: (u+r)>0 ? (r/(u+r))*100 : 0};
  });
  const maxVal = Math.max(...data.map(d=>d.total), 1);
  const yMax = Math.ceil(maxVal/100)*100 || maxVal;
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const bandW = innerW / data.length;
  const barW = bandW * 0.62;

  // Grid + ticks
  let grid='', ytL='';
  for(let i=0;i<=4;i++){
    const yv = (yMax*i)/4;
    const py = padT + innerH - (yv/yMax)*innerH;
    grid += `<line x1="${padL}" y1="${py}" x2="${w-padR}" y2="${py}" stroke="#EAEDEF"/>`;
    ytL += `<text x="${padL-6}" y="${py+4}" font-size="10" fill="#3D4047" text-anchor="end">${Math.round(yv)}</text>`;
  }

  // Barras + data labels
  let bars='', labels='', pctLabels='', xLabels='';
  data.forEach((d,i)=>{
    const cx = padL + bandW*i + bandW/2;
    // Barra grande (TOTAL = únicos + revisitas) — sólida em roxo claro
    const yTotal = padT + innerH - (d.total/yMax)*innerH;
    const hTotal = (d.total/yMax)*innerH;
    bars += `<rect x="${cx-barW/2}" y="${yTotal}" width="${barW}" height="${hTotal}" fill="#6B3FA0" fill-opacity="0.85" stroke="#4A2872" stroke-width="0.8">
              <title>${d.ym} — ${d.total} visitas totais (${d.unicos} únicas + ${d.revisitas} revisitas)</title>
            </rect>`;
    // Barra de revisitas sobreposta (laranja semi-transparente, alinhada à base)
    const yRev = padT + innerH - (d.revisitas/yMax)*innerH;
    const hRev = (d.revisitas/yMax)*innerH;
    bars += `<rect x="${cx-barW/2}" y="${yRev}" width="${barW}" height="${hRev}" fill="#D4900A" fill-opacity="0.85" stroke="#8C5E00" stroke-width="0.8">
              <title>${d.ym} — ${d.revisitas} revisitas (${d.pctRev.toFixed(0)}% das visitas)</title>
            </rect>`;
    // Data label: total em cima
    labels += `<text x="${cx}" y="${yTotal-4}" font-size="11" font-weight="700" fill="#3D4047" text-anchor="middle">${d.total}</text>`;
    // % de revisita dentro da barra de revisita (se couber)
    if(hRev > 18){
      pctLabels += `<text x="${cx}" y="${yRev + hRev/2 + 3}" font-size="10" font-weight="700" fill="#fff" text-anchor="middle">${d.pctRev.toFixed(0)}%</text>`;
    }
    xLabels += `<text x="${cx}" y="${h-padB+14}" font-size="9.5" fill="#3D4047" text-anchor="middle" transform="rotate(-35 ${cx} ${h-padB+14})">${d.ym}</text>`;
  });

  // Eixos
  const axes = `
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${h-padB}" stroke="#1B1F23"/>
    <line x1="${padL}" y1="${h-padB}" x2="${w-padR}" y2="${h-padB}" stroke="#1B1F23"/>`;
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
    ${grid}${bars}${labels}${pctLabels}${axes}${ytL}${xLabels}
  </svg>
  <div class="legend" style="margin-top:6px;">
    <div class="legend-item"><span class="legend-sw" style="background:#6B3FA0"></span>Visitas totais (únicas + revisitas)</div>
    <div class="legend-item"><span class="legend-sw" style="background:#D4900A"></span>Revisitas (com % do total dentro da barra)</div>
  </div>`;
}

function renderRevisitaLeitura(visdiaRows, medRows, revisitaRows){
  const lh = document.getElementById('tl-revisita-leitura');
  if(!lh) return;
  // Calcula correlação Pearson de vis/dia com únicos e com revisitas
  const allYm = [...new Set([...visdiaRows.map(r=>r.ym), ...medRows.map(r=>r.ym), ...revisitaRows.map(r=>r.ym)])].sort();
  const visMap = {}; visdiaRows.forEach(r=>{ visMap[r.ym]=r.val; });
  const medMap = {}; medRows.forEach(r=>{ medMap[r.ym]=r.val; });
  const revMap = {}; revisitaRows.forEach(r=>{ revMap[r.ym]=r.val; });
  const pairs = allYm.filter(y=>visMap[y]!==undefined && medMap[y]!==undefined && revMap[y]!==undefined);
  if(pairs.length < 5){ lh.innerHTML = ''; return; }

  const pearson = (xs, ys) => {
    const n = xs.length;
    const mx = xs.reduce((a,b)=>a+b,0)/n;
    const my = ys.reduce((a,b)=>a+b,0)/n;
    let sxx=0, syy=0, sxy=0;
    for(let i=0;i<n;i++){ sxx+=(xs[i]-mx)**2; syy+=(ys[i]-my)**2; sxy+=(xs[i]-mx)*(ys[i]-my); }
    return (sxx>0 && syy>0) ? sxy / Math.sqrt(sxx*syy) : 0;
  };
  const vis = pairs.map(y=>visMap[y]);
  const med = pairs.map(y=>medMap[y]);
  const rev = pairs.map(y=>revMap[y]);
  const rUnico = pearson(vis, med);
  const rRev = pearson(vis, rev);

  // Taxa média de revisita
  const visTotal = pairs.map(y=>medMap[y] + revMap[y]);
  const taxa = visTotal.reduce((a,b)=>a+b,0) > 0
    ? rev.reduce((a,b)=>a+b,0) / visTotal.reduce((a,b)=>a+b,0) * 100
    : 0;

  let veredito;
  if(rUnico > 0.6 && rRev < 0.3){
    veredito = `<strong style="color:var(--teal);">Vis/dia cresce junto com médicos únicos</strong> — quando o consultor sobe o ritmo, ele atinge mais médicos diferentes. Cobertura saudável.`;
  } else if(rRev > 0.6 && rUnico < 0.3){
    veredito = `<strong style="color:var(--warn);">Vis/dia cresce junto com revisitas, não com únicos</strong> — quando o ritmo sobe, é por revisitar os mesmos médicos. Risco de "trabalho falso" pra meta de vis/dia.`;
  } else if(rUnico > 0.4 && rRev > 0.4){
    veredito = `<strong style="color:var(--ink2);">Vis/dia sobe acompanhando os dois</strong> — esforço se distribui entre alcançar novos e revisitar os mesmos. Padrão típico.`;
  } else {
    veredito = `Vis/dia não tem correlação clara com nenhum dos dois — sinal de séries curtas, variação irregular, ou que outros fatores (ausência, dias úteis) dominam.`;
  }
  lh.innerHTML = `
    <strong>Diagnóstico:</strong>
    correlação vis/dia × únicos = ${rUnico.toFixed(2)} ·
    correlação vis/dia × revisitas = ${rRev.toFixed(2)} ·
    taxa média de revisita = ${taxa.toFixed(0)}% das visitas totais.
    <br>${veredito}`;
}

// Calcula série mensal: cobertura mensal MÉDIA (por consultor) e ausência MÉDIA por mês.
// Cobertura por consultor = medicos_visitados_no_mes / painel_size (snapshot atual).
// Sem double-counting de overlap.
function renderCobAusTemporal(){
  // Onda 4 — Refeito: COLUNAS (cobertura) + LINHA (ausência) com data labels.
  // Substitui a versão com 2 linhas que confundia o cliente.
  const host = document.getElementById('svg-cob-aus-temporal');
  if(!host) return;
  const cs = getFilteredAtivos();
  const cByISID = {};
  cs.forEach(c=>{ cByISID[c.ISID] = c; });
  const filt = (DATA.series_consultor||[]).filter(r=>cByISID[r.ISID] && r.ym);
  const byYm = {};
  filt.forEach(r=>{
    const c = cByISID[r.ISID];
    if(!c || !(c.painel_size > 0)) return;
    if(!byYm[r.ym]) byYm[r.ym] = {ym:r.ym, cobSum:0, cobN:0, ausSum:0, uteisSum:0};
    const cob = Math.min(100, (r.medicos / c.painel_size) * 100);
    if(r.medicos > 0){
      byYm[r.ym].cobSum += cob;
      byYm[r.ym].cobN += 1;
    }
    byYm[r.ym].ausSum += (r.ausencia || 0);
    byYm[r.ym].uteisSum += (r.uteis || 0);
  });
  let arr = Object.values(byYm).sort((a,b)=>a.ym.localeCompare(b.ym));
  arr = arr.map(o=>({
    ym: o.ym,
    cob: o.cobN > 0 ? o.cobSum / o.cobN : null,
    aus: o.uteisSum > 0 ? (o.ausSum / o.uteisSum) * 100 : null,
  }));
  arr = clipToCurrent(arr).filter(r=>r.cob !== null && r.aus !== null).slice(-12);
  if(arr.length < 3){
    host.innerHTML = '<div style="text-align:center;color:var(--ink3);padding:20px;">Histórico insuficiente para o filtro atual.</div>';
    const lh = document.getElementById('cob-aus-leitura');
    if(lh) lh.innerHTML = '';
    return;
  }

  const w = 820, h = 360, padL = 60, padR = 60, padT = 38, padB = 56;
  const cobMax = 100, ausMax = Math.max(50, Math.ceil(Math.max(...arr.map(r=>r.aus))/5)*5);
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const bandW = innerW / arr.length;
  const barW = bandW * 0.55;
  const yCob = (v)=> padT + innerH - (v/cobMax) * innerH;
  const yAus = (v)=> padT + innerH - (v/ausMax) * innerH;

  // Grid
  let grid='', ytL='', ytR='';
  for(let i=0;i<=5;i++){
    const py = padT + i*innerH/5;
    const cobV = cobMax - i*cobMax/5;
    const ausV = ausMax - i*ausMax/5;
    grid += `<line x1="${padL}" y1="${py}" x2="${w-padR}" y2="${py}" stroke="#EAEDEF"/>`;
    ytL += `<text x="${padL-8}" y="${py+4}" font-size="10" fill="#00857C" text-anchor="end" font-weight="600">${cobV.toFixed(0)}%</text>`;
    ytR += `<text x="${w-padR+8}" y="${py+4}" font-size="10" fill="#C8102E" text-anchor="start" font-weight="600">${ausV.toFixed(0)}%</text>`;
  }

  // Barras cobertura + data labels
  let bars='', barLabels='', ausPath='', ausDots='', ausLabels='', xLabels='';
  arr.forEach((r,i)=>{
    const cx = padL + bandW*i + bandW/2;
    const yBar = yCob(r.cob);
    const hBar = (r.cob/cobMax) * innerH;
    bars += `<rect x="${cx-barW/2}" y="${yBar}" width="${barW}" height="${hBar}" fill="#00857C" fill-opacity="0.85" stroke="#005F58" stroke-width="0.8">
              <title>${r.ym} — Cobertura ${r.cob.toFixed(1)}%</title>
            </rect>`;
    barLabels += `<text x="${cx}" y="${yBar-4}" font-size="10.5" font-weight="700" fill="#005F58" text-anchor="middle">${r.cob.toFixed(0)}%</text>`;
    xLabels += `<text x="${cx}" y="${h-padB+14}" font-size="9.5" fill="#3D4047" text-anchor="middle" transform="rotate(-35 ${cx} ${h-padB+14})">${r.ym}</text>`;
    // Linha de ausência
    const xPt = cx;
    const yPt = yAus(r.aus);
    if(i === 0) ausPath += `M${xPt} ${yPt}`;
    else ausPath += ` L${xPt} ${yPt}`;
    ausDots += `<circle cx="${xPt}" cy="${yPt}" r="3.5" fill="#C8102E" stroke="#fff" stroke-width="1.5"><title>${r.ym} — Ausência ${r.aus.toFixed(1)}%</title></circle>`;
    ausLabels += `<text x="${xPt}" y="${yPt-9}" font-size="10" font-weight="700" fill="#C8102E" text-anchor="middle">${r.aus.toFixed(0)}%</text>`;
  });

  // Eixos
  const axes = `
    <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${h-padB}" stroke="#1B1F23"/>
    <line x1="${w-padR}" y1="${padT}" x2="${w-padR}" y2="${h-padB}" stroke="#1B1F23"/>
    <line x1="${padL}" y1="${h-padB}" x2="${w-padR}" y2="${h-padB}" stroke="#1B1F23"/>
    <text x="${padL-44}" y="${padT-12}" font-size="11" fill="#00857C" font-weight="700">% Cobertura</text>
    <text x="${w-padR+8}" y="${padT-12}" font-size="11" fill="#C8102E" font-weight="700">% Ausência</text>`;

  host.innerHTML = `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
    ${grid}${bars}${barLabels}
    <path d="${ausPath}" stroke="#C8102E" stroke-width="2.5" fill="none"/>
    ${ausDots}${ausLabels}${axes}${ytL}${ytR}${xLabels}
  </svg>
  <div class="legend" style="margin-top:6px;">
    <div class="legend-item"><span class="legend-sw" style="background:#00857C"></span>Cobertura mensal de painel (barra, eixo esquerdo)</div>
    <div class="legend-item"><span class="legend-sw" style="background:#C8102E"></span>% Ausência de campo (linha, eixo direito)</div>
  </div>`;

  // Correlação Pearson temporal
  const cobs = arr.map(r=>r.cob), auss = arr.map(r=>r.aus);
  const n = arr.length;
  const meanC = cobs.reduce((a,b)=>a+b,0)/n;
  const meanA = auss.reduce((a,b)=>a+b,0)/n;
  let sCC=0, sAA=0, sCA=0;
  for(let i=0;i<n;i++){
    sCC += (cobs[i]-meanC)**2;
    sAA += (auss[i]-meanA)**2;
    sCA += (cobs[i]-meanC)*(auss[i]-meanA);
  }
  const r = (sCC>0 && sAA>0) ? sCA / Math.sqrt(sCC*sAA) : 0;
  const corStr = r < -0.5 ? 'forte e negativa (ausência puxa cobertura pra baixo)' :
                 r < -0.3 ? 'moderada e negativa' :
                 r < -0.1 ? 'fraca' :
                 r >  0.1 ? 'positiva (ausência e cobertura sobem juntas — atípico)' :
                 'praticamente nula';
  const lh = document.getElementById('cob-aus-leitura');
  if(lh){
    lh.innerHTML = `<strong>Correlação temporal:</strong> ${r.toFixed(2)} (${corStr}).
      Avaliada nos últimos ${n} meses. Quando a barra de cobertura encolhe junto com o pico de ausência no mesmo mês, há sinal de impacto direto.`;
  }
}

function renderScatter(){
  // Item 16 (crítica): trocar scatter (cliente não lê) por barras pareadas + ranking
  // Métrica correta apontada pela Raissa: ausência impacta visitas/dia, não painel
  const cs = getFilteredAtivos().filter(c=>c.vis_dia_media>0 && c.pct_ausencia!==null);
  if(!cs.length){
    document.getElementById('svg-scatter').innerHTML = '<div style="text-align:center;color:var(--ink3);padding:24px;">Sem dados para o filtro atual.</div>';
    return;
  }

  // Agrupar consultores em 4 faixas de ausência e calcular vis/dia média de cada faixa
  const bins = [
    {min:0,    max:10,   label:'até 10%',  cor:'#00857C'},
    {min:10,   max:20,   label:'10–20%',   cor:'#6ECEB2'},
    {min:20,   max:30,   label:'20–30%',   cor:'#D4900A'},
    {min:30,   max:9999, label:'30%+',     cor:'#C8102E'},
  ];
  bins.forEach(b=>{
    const inB = cs.filter(c=>c.pct_ausencia>=b.min && c.pct_ausencia<b.max);
    b.n = inB.length;
    b.visdia = inB.length? mean(inB.map(c=>c.vis_dia_media)) : 0;
    b.painel = inB.length? mean(inB.filter(c=>c.painel_size>0).map(c=>c.painel_size)) : 0;
  });

  // Pearson r entre ausência e vis/dia
  const xs = cs.map(c=>c.pct_ausencia);
  const ys = cs.map(c=>c.vis_dia_media);
  const n = cs.length;
  const mx = mean(xs), my = mean(ys);
  let num=0, sx2=0, sy2=0;
  for(let i=0;i<n;i++){ num += (xs[i]-mx)*(ys[i]-my); sx2 += Math.pow(xs[i]-mx,2); sy2 += Math.pow(ys[i]-my,2); }
  const r = (Math.sqrt(sx2)*Math.sqrt(sy2))? num/(Math.sqrt(sx2)*Math.sqrt(sy2)) : 0;

  // Renderizar: barras verticais com vis/dia médio por faixa de ausência + nº de consultores
  const w = 900, h = 320;
  const pad = {l:60, r:30, t:36, b:60};
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const vmax = nice(Math.max(...bins.map(b=>b.visdia))*1.20) || 1;
  const stepX = innerW / bins.length;
  const barW = stepX * 0.55;

  let grid='', yTicks='';
  for(let i=0; i<=4; i++){
    const y = pad.t + innerH*i/4;
    const v = vmax*(1-i/4);
    grid += `<line x1="${pad.l}" y1="${y}" x2="${pad.l+innerW}" y2="${y}" stroke="#E8EEF3"/>`;
    yTicks += `<text x="${pad.l-6}" y="${y+3}" text-anchor="end" font-size="10" fill="#8A9BAD" font-family="Arial">${v.toFixed(1)}</text>`;
  }

  let bars='', barLabels='', xLabels='';
  bins.forEach((b,i)=>{
    const x = pad.l + i*stepX + (stepX-barW)/2;
    const bh = b.visdia>0? (b.visdia/vmax)*innerH : 0;
    const y = pad.t + innerH - bh;
    if(bh>0){
      bars += `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${bh.toFixed(2)}" fill="${b.cor}" rx="3"/>`;
      barLabels += `<text x="${(x+barW/2).toFixed(2)}" y="${(y-6).toFixed(2)}" text-anchor="middle" font-size="13" font-weight="700" fill="${b.cor}" font-family="Arial">${b.visdia.toFixed(2)}</text>`;
      barLabels += `<text x="${(x+barW/2).toFixed(2)}" y="${(y-22).toFixed(2)}" text-anchor="middle" font-size="10" fill="#566778" font-family="Arial">vis/dia</text>`;
    }
    xLabels += `<text x="${(x+barW/2).toFixed(2)}" y="${(pad.t+innerH+18).toFixed(2)}" text-anchor="middle" font-size="11" font-weight="700" fill="#0C2340" font-family="Arial">${b.label}</text>`;
    xLabels += `<text x="${(x+barW/2).toFixed(2)}" y="${(pad.t+innerH+34).toFixed(2)}" text-anchor="middle" font-size="10" fill="#8A9BAD" font-family="Arial">${b.n} consultor${b.n===1?'':'es'}</text>`;
  });

  const xAxisLbl = `<text x="${(pad.l+innerW/2).toFixed(2)}" y="${(h-8).toFixed(2)}" text-anchor="middle" font-size="11" font-weight="700" fill="#0C2340" font-family="Arial">Faixa de ausência (% do tempo)</text>`;
  const title = `<text x="${pad.l}" y="${pad.t-12}" font-size="11" font-weight="700" fill="#0C2340" font-family="Arial">Visitas/dia médio em cada faixa de ausência</text>`;

  // Diagnóstico textual baseado em r
  let interpretacao = '';
  if(r < -0.3) interpretacao = `<strong>Há correlação inversa relevante (r = ${r.toFixed(2)}):</strong> quem se ausenta mais entrega menos visitas por dia ativo. Isso confirma que ausência impacta produtividade.`;
  else if(r < -0.1) interpretacao = `<strong>Correlação inversa leve (r = ${r.toFixed(2)}):</strong> a relação existe mas é fraca — outros fatores explicam mais.`;
  else if(Math.abs(r) <= 0.1) interpretacao = `<strong>Sem correlação clara (r = ${r.toFixed(2)}):</strong> ausência e visitas/dia parecem independentes no recorte atual.`;
  else interpretacao = `<strong>Correlação positiva atípica (r = ${r.toFixed(2)}):</strong> revisar — esperaríamos o inverso.`;

  document.getElementById('svg-scatter').innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
      ${grid}${title}${bars}${barLabels}${xLabels}${yTicks}
      <line x1="${pad.l}" y1="${pad.t+innerH}" x2="${pad.l+innerW}" y2="${pad.t+innerH}" stroke="#A8C4D4"/>
      ${xAxisLbl}
    </svg>
    <div style="font-size:12px;color:var(--ink2);margin-top:10px;line-height:1.6;">
      ${interpretacao}<br>
      <span style="color:var(--ink3);font-size:11px;">${n} consultores avaliados. Comparar com sua expectativa: se ausência alta produz mesma média de visitas/dia, o cara está "comprimindo" o tempo em campo — pode ser real (eficiência) ou ruído (erro de lançamento de ausência).</span>
    </div>`;
}


// ============================================================================
// OVERLAP — cross-team boxes (Item 31), intra-time table (Items 30,17), pairs (32-34)
// ============================================================================
function renderOverlap(){
  const cs = getFilteredConsultores();
  // Cross-team: caixas por categoria (Item 31)
  const totMed = sum(cs.map(c=>c.medicos_visit_12m||0));
  const totExcl = sum(cs.map(c=>c.exclusivos||0));
  const totIntra = sum(cs.map(c=>c.shared_intra||0));
  const totCoer = sum(cs.map(c=>c.shared_cross_coer||0));
  const totIncoer = sum(cs.map(c=>c.shared_cross_incoer||0));
  const totNaoClass = sum(cs.map(c=>c.shared_cross_naoclass||0));
  // Médias percentuais
  const csFilt = cs.filter(c=>c.medicos_visit_12m>0);
  const mPctExcl = mean(csFilt.map(c=>c.pct_exclusivos||0));
  const mPctIntra = mean(csFilt.map(c=>c.pct_overlap_intra||0));
  const mPctCoer = mean(csFilt.map(c=>c.pct_overlap_cross_coer||0));
  const mPctIncoer = mean(csFilt.map(c=>c.pct_overlap_cross_incoer||0));
  const mPctNaoClass = mean(csFilt.map(c=>c.pct_overlap_cross_naoclass||0));

  const sigla = DATA.meta.janela_label || 'MAT';
  const boxes = [
    {lbl:'Exclusivos', val: pct(mPctExcl), sub: fmt(totExcl) + ' médicos · só visitado pelo consultor', cls:'exclusivo'},
    {lbl:'Cross-team coerente', val: '—', sub: 'aguardando mapeamento de SFs coerentes (MSD)', cls:'coer'},
    {lbl:'Cross-team incoerente', val: '—', sub: 'aguardando mapeamento de SFs coerentes (MSD)', cls:'incoer'},
    {lbl:'Cross-team (todos)', val: pct(mPctNaoClass), sub: fmt(totNaoClass) + ' médicos · soma de coerente + incoerente', cls:'naoclass'},
  ];
  document.getElementById('cat-grid').innerHTML = boxes.map(b=>`
    <div class="cat-box ${b.cls}">
      <div class="cat-lbl">${b.lbl}</div>
      <div class="cat-val">${b.val}</div>
      <div class="cat-sub">${b.sub}</div>
    </div>`).join('') + `
    <div style="grid-column:1 / -1;font-size:11px;color:var(--ink3);margin-top:6px;line-height:1.5;">
      Período: ${sigla}. Universo no filtro: ${fmt(totMed)} médicos visitados (soma dos painéis de ${csFilt.length} consultor(es)). Overlap intra-time médio: <strong style="color:var(--danger);">${pct(mPctIntra)}</strong> — detalhado abaixo.
    </div>`;

  // Intra-time table — Onda 4: seção removida, mas mantemos a lógica defensiva
  // caso o DOM exista (build de transição). Se não existir, ignora silenciosamente.
  const tbodyI = document.querySelector('#tbl-overlap-intra tbody');
  if(tbodyI){
    const csIntra = cs.filter(c=>c.medicos_visit_12m>0)
                      .slice().sort((a,b)=>{
                        const va=a[ST.intra_sort], vb=b[ST.intra_sort];
                        if(typeof va==='number' && typeof vb==='number') return ST.intra_dir*(va-vb);
                        return ST.intra_dir*String(va||'').localeCompare(String(vb||''),'pt-BR');
                      });
    tbodyI.innerHTML = csIntra.map(c=>{
      const cor = c.pct_overlap_intra>=20? 'var(--danger)' : c.pct_overlap_intra>=10? 'var(--warn)' : 'var(--teal)';
      return `
      <tr>
        <td class="nm" style="cursor:pointer;" onclick="focusConsultor('${c.ISID}')">${escapeHtml(c.nome)}</td>
        <td>${escapeHtml(c.sales_force||'')}</td>
        <td>${escapeHtml(c.gd_name||'—')}</td>
        <td class="num">${fmt(c.medicos_visit_12m)}</td>
        <td class="num">${fmt(c.shared_intra)}</td>
        <td class="num" style="color:${cor};font-weight:700;">${pct(c.pct_overlap_intra)}</td>
        <td class="num">${fmt(c.exclusivos)}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--ink3);padding:14px;">Sem consultores no filtro.</td></tr>';
  }

  // Pares
  renderPairs();
  aplicarSortEmTodasTabelas();
}

function setPairFilter(t){
  ST.pair_tipo = t;
  document.querySelectorAll('#btn-tipo-todos,#btn-tipo-intra,#btn-tipo-cross').forEach(b=>{
    b.style.background = '#fff'; b.style.color = 'var(--ink2)';
  });
  const map = {'all':'btn-tipo-todos', 'intra':'btn-tipo-intra', 'cross':'btn-tipo-cross'};
  const el = document.getElementById(map[t]);
  if(el){ el.style.background = 'var(--ink)'; el.style.color = '#fff'; }
  renderPairs();
}

function renderPairs(){
  let pairs = DATA.pares_overlap.slice();
  if(ST.pair_tipo==='intra') pairs = pairs.filter(p=>p.tipo==='intra-time' || p.tipo==='intra');
  else if(ST.pair_tipo==='cross') pairs = pairs.filter(p=>p.tipo==='cross-team');
  // Filtros por GD/SF/Consultor
  const validIsids = new Set(getFilteredConsultores(true).map(c=>c.ISID));
  pairs = pairs.filter(p=>validIsids.has(p.A) && validIsids.has(p.B));
  if(ST.consultor!=='__all__') pairs = pairs.filter(p=>p.A===ST.consultor || p.B===ST.consultor);
  // Ordenar por % mesmo dia DESC (mais coordenação suspeita primeiro)
  pairs.sort((a,b)=>(b.pct_mesmo_dia||0)-(a.pct_mesmo_dia||0));

  const tbody = document.querySelector('#tbl-pairs tbody');
  if(!pairs.length){
    tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;color:var(--ink3);padding:14px;">Nenhum par com sobreposição no filtro atual.</td></tr>';
    return;
  }
  tbody.innerHTML = pairs.map((p,idx)=>{
    const key = p.A+'_'+p.B;
    const expanded = ST.expanded_pairs.has(key);
    const tipoTag = (p.tipo==='intra-time' || p.tipo==='intra')
      ? '<span class="tag bad">Intra-time</span>'
      : '<span class="tag neutral">Cross-team</span>';
    const pctCor = p.pct_min>=20? 'var(--danger)' : p.pct_min>=10? 'var(--warn)' : 'var(--ink2)';
    // Padrão de visita: cor por classificação
    let padraoTag;
    const padrao = p.padrao_visita || 'Distribuídos';
    if(padrao==='Coordenação suspeita'){
      padraoTag = '<span class="flag-tag" style="background:#C8102E;color:#fff;font-size:10px;">Visita em dupla — revisar</span>';
    } else if(padrao==='Atenção'){
      padraoTag = '<span class="flag-tag" style="background:#D4900A;color:#fff;font-size:10px;">Acompanhar</span>';
    } else {
      padraoTag = '<span class="flag-tag" style="background:#00857C;color:#fff;font-size:10px;">Distribuídos</span>';
    }
    const corMd = (p.pct_mesmo_dia||0)>=30 ? 'var(--danger)' : (p.pct_mesmo_dia||0)>=10 ? 'var(--warn)' : 'var(--teal)';
    const mainRow = `
      <tr>
        <td class="nm">${escapeHtml(p.A_nome||p.A)}</td>
        <td>${escapeHtml(p.A_sf||'—')}</td>
        <td class="nm">${escapeHtml(p.B_nome||p.B)}</td>
        <td>${escapeHtml(p.B_sf||'—')}</td>
        <td>${tipoTag}</td>
        <td class="num">${fmt(p.A_total)}</td>
        <td class="num">${fmt(p.B_total)}</td>
        <td class="num">${fmt(p.shared)}</td>
        <td class="num" style="color:${pctCor};font-weight:700;">${pct(p.pct_min)}</td>
        <td class="num">${fmt(p.medicos_mesmo_dia_n||p.mesmo_dia||0)}</td>
        <td class="num" style="color:${corMd};font-weight:700;">${pct(p.pct_mesmo_dia||0)}</td>
        <td>${padraoTag}</td>
        <td><button class="btn-secondary btn-exp-sm" onclick="togglePair('${escapeHtml(key)}')">${expanded? 'Ocultar' : 'Ver médicos'}</button></td>
      </tr>`;
    if(!expanded) return mainRow;
    // Drill-down: lista de médicos compartilhados
    const medicos = (DATA.pares_medicos_detail||[]).filter(m=>m.A===p.A && m.B===p.B);
    const drillRows = medicos.map(m=>`
      <tr>
        <td>${escapeHtml(m.MDM||'—')}</td>
        <td>${escapeHtml(m.medico_crm||'—')}</td>
        <td>${escapeHtml(m.medico_nome||'(sem nome)')}</td>
        <td>${escapeHtml(m.esp1||'—')}</td>
        <td class="num">${fmt(m.visitas_A)}</td>
        <td class="num">${fmt(m.visitas_B)}</td>
      </tr>`).join('');
    const drillBody = medicos.length
      ? `<table class="drill-table">
          <thead><tr><th>MDM</th><th>CRM</th><th>Nome</th><th>Especialidade</th><th class="num">Visitas A</th><th class="num">Visitas B</th></tr></thead>
          <tbody>${drillRows}</tbody></table>`
      : '<div style="color:var(--ink3);padding:8px;">Lista detalhada não disponível para este par (limite da amostra exportada).</div>';
    return mainRow + `
      <tr class="drill-row">
        <td colspan="13" class="drill-cell">
          <div class="drill-inner">
            <div class="drill-title">Médicos compartilhados (${medicos.length})</div>
            ${drillBody}
          </div>
        </td>
      </tr>`;
  }).join('');
  aplicarSortEmTodasTabelas();
}

function togglePair(key){
  if(ST.expanded_pairs.has(key)) ST.expanded_pairs.delete(key);
  else ST.expanded_pairs.add(key);
  renderPairs();
}

// ============================================================================
// TAB SWITCHING
// ============================================================================
function setTab(t){
  ST.tab = t;
  document.querySelectorAll('.vista').forEach(v=>v.classList.remove('active'));
  document.getElementById('vista-'+t).classList.add('active');
  document.querySelectorAll('#tab-toggle button').forEach(b=>{
    b.classList.toggle('active', b.dataset.tab===t);
  });
}

// ============================================================================
// SORT BINDING
// ============================================================================
function bindSort(theadSel, stateSortKey, stateDirKey, renderFn){
  document.querySelectorAll(theadSel+' th[data-col]').forEach(th=>{
    th.addEventListener('click', ()=>{
      const c = th.dataset.col;
      if(ST[stateSortKey]===c) ST[stateDirKey] = -ST[stateDirKey];
      else {
        ST[stateSortKey] = c;
        ST[stateDirKey] = th.classList.contains('num')? -1 : 1;
      }
      document.querySelectorAll(theadSel+' th[data-col]').forEach(t=>{
        t.classList.remove('sa','sd');
        if(t.dataset.col===ST[stateSortKey]) t.classList.add(ST[stateDirKey]===-1?'sd':'sa');
      });
      renderFn();
    });
  });
}

// ============================================================================
// SORT UNIVERSAL — funciona em qualquer tabela manipulando o DOM diretamente
// Não depende de re-render: reorganiza as linhas que já estão no tbody.
// Usar via bindSortDOM(tableId) — torna toda <th> sortável (exceto onde data-nosort).
// ============================================================================
// Helper para atualizar label de TH sem destruir atributos de sort nem o span.sort-arrow
function setThLabel(th, newLabel){
  if(!th) return;
  const arrow = th.querySelector('.sort-arrow');
  th.textContent = newLabel;
  if(arrow) th.appendChild(arrow);
  // data-sort-table e data-sort-idx são atributos do elemento — NÃO são apagados por textContent
  // mas o span.sort-arrow é filho e sim é apagado — por isso re-anexamos acima
}

function bindSortDOM(tableId){
  const tbl = document.getElementById(tableId);
  if(!tbl) return;
  // Pega só a ÚLTIMA linha do thead — tabelas com grouped header (tbl-detail) têm 2 linhas
  const lastHeaderRow = tbl.querySelector('thead tr:last-child');
  if(!lastHeaderRow) return;
  const ths = lastHeaderRow.querySelectorAll('th');
  if(!ths.length) return;
  // Estado por tabela
  if(!window.__SORT_STATE) window.__SORT_STATE = {};
  if(!window.__SORT_STATE[tableId]) window.__SORT_STATE[tableId] = {col:-1, dir:1};
  // Registrar listener de clique em cada th (com __sortBound para não duplicar)
  ths.forEach((th, idx)=>{
    if(th.dataset.nosort === 'true') return;
    th.style.cursor = 'pointer';
    th.setAttribute('data-sort-idx', idx);
    if(!th.querySelector('.sort-arrow')){
      const arrow = document.createElement('span');
      arrow.className = 'sort-arrow';
      arrow.textContent = '⇅';
      th.appendChild(arrow);
    }
    if(!th.__sortBound){
      th.addEventListener('click', (ev)=>{
        if(ev.target && ev.target.classList && ev.target.classList.contains('tip')) return;
        sortTableByCol(tableId, idx);
      });
      th.__sortBound = true;
    }
  });
  const state = window.__SORT_STATE[tableId];
  // Sort DEFAULT DESC na primeira coluna numérica significativa
  if(state.col < 0){
    const DEFAULT_SORT_COL = {
      'tbl-sf':                   1,
      'tbl-detail':                7,
      'tbl-visit-sf':              2,
      'tbl-visit-cons':            6,
      'tbl-medicos-fora-painel':   3,
      'tbl-medicos-parados':       4,
      'tbl-absence':               11,
      'tbl-setor':                 7,
      'tbl-pairs':                 4,
      'tbl-perf-uf':               2,
      'tbl-painel-ideal':          3,
      'tbl-alvo-perfil':           2,
    };
    if(DEFAULT_SORT_COL[tableId] !== undefined){
      const idx = DEFAULT_SORT_COL[tableId];
      if(idx >= 0 && idx < ths.length){
        state.col = idx;
        state.dir = -1;
        sortTableByColInternal(tableId, idx, -1);
      }
    }
  } else {
    sortTableByColInternal(tableId, state.col, state.dir);
  }
}

function sortTableByCol(tableId, colIdx){
  const state = window.__SORT_STATE[tableId];
  let dir;
  if(state.col === colIdx){
    dir = -state.dir;
  } else {
    // Detectar se coluna é numérica olhando a 1ª célula
    const tbl = document.getElementById(tableId);
    const sampleRow = tbl ? tbl.querySelector('tbody tr') : null;
    let isNum = false;
    if(sampleRow){
      const cell = sampleRow.cells[colIdx];
      if(cell){
        const txt = cell.textContent.trim();
        if(/^[+-]?[\d.,]+%?$/.test(txt) || cell.classList.contains('num')) isNum = true;
      }
    }
    dir = isNum ? -1 : 1;
  }
  state.col = colIdx;
  state.dir = dir;
  sortTableByColInternal(tableId, colIdx, dir);
}

// Versão interna: ordena sem mexer no estado (usada também ao restaurar sort após render)
function sortTableByColInternal(tableId, colIdx, dir){
  const tbl = document.getElementById(tableId);
  if(!tbl) return;
  const tbody = tbl.querySelector('tbody');
  if(!tbody) return;

  // Atualizar setinhas no header
  tbl.querySelectorAll('thead th[data-sort-idx]').forEach(th=>{
    const arr = th.querySelector('.sort-arrow');
    if(!arr) return;
    if(parseInt(th.dataset.sortIdx) === colIdx){
      arr.textContent = dir === 1 ? '▲' : '▼';
      arr.style.color = '#5FE5DC';
      arr.style.opacity = '1';
      arr.style.fontWeight = '700';
      th.style.background = '#005F58';
    } else {
      arr.textContent = '⇅';
      arr.style.color = '';
      arr.style.opacity = '';
      arr.style.fontWeight = '';
      th.style.background = '';
    }
  });

  // Ordenar
  const rows = Array.from(tbody.querySelectorAll('tr'));
  if(rows.length === 0) return;
  const parseCell = (txt) => {
    txt = (txt || '').trim();
    if(txt === '' || txt === '—' || txt === '-' || txt === 'N/A') return {n: -Infinity, s: ''};
    let cleaned = txt.replace(/%/g, '').replace(/\s/g, '');
    cleaned = cleaned.replace(/^R\$/i, '').replace(/(m|d|pts|pp)$/i, '');
    // PT-BR: vírgula é decimal, ponto é milhar → ex: "1.234,56" → "1234.56"
    if(/\d,\d/.test(cleaned)) {
      cleaned = cleaned.replace(/\./g, '').replace(',', '.');
    } else {
      cleaned = cleaned.replace(/,/g, '.');
    }
    const num = parseFloat(cleaned);
    if(!isNaN(num) && /^[+-]?[\d.]+$/.test(cleaned)) return {n: num, s: txt.toLowerCase()};
    return {n: NaN, s: txt.toLowerCase()};
  };
  rows.sort((a, b)=>{
    const ca = a.cells[colIdx];
    const cb = b.cells[colIdx];
    const pa = parseCell(ca ? ca.textContent : '');
    const pb = parseCell(cb ? cb.textContent : '');
    if(!isNaN(pa.n) && !isNaN(pb.n)){
      return (pa.n - pb.n) * dir;
    }
    if(pa.s < pb.s) return -1 * dir;
    if(pa.s > pb.s) return  1 * dir;
    return 0;
  });
  rows.forEach(r=>tbody.appendChild(r));
}

// Aplica sort universal em todas as tabelas com tbody (executado após renderizar tudo)

function aplicarSortEmTodasTabelas(){
  const ids = [
    'tbl-sf','tbl-detail','tbl-visit-sf','tbl-visit-cons',
    'tbl-medicos-parados','tbl-medicos-fora-painel','tbl-visit-mccp',
    'tbl-cap-gd','tbl-alvo-perfil','tbl-painel-ideal','tbl-diagnostico',
    'tbl-calc-viagem','tbl-absence','tbl-setor','tbl-perf-uf',
    'tbl-overlap-intra','tbl-pairs'
  ];
  ids.forEach(id => bindSortDOM(id));
}

// ============================================================================
// RENDER ALL
// ============================================================================
function renderAll(){
  renderKPIs();
  renderSim();
  renderHistograms();
  renderSF();
  renderCurvaAprendizado();
  renderDetail();
  renderVariabilidade();
  renderVisitation();
  renderAbsence();
  renderSetor();
  renderTimeline();
  renderTendencia();
  renderHeatmap();
  renderOverlap();
  // Aplicar sort universal em todas as tabelas DEPOIS de renderizar
  // (algumas são criadas dinamicamente, então precisa ser depois)
  aplicarSortEmTodasTabelas();
}

// ============================================================================
// EXPORTS
// ============================================================================

// Export mês-a-mês para a seção Variabilidade — permite ao usuário ver
// a série temporal que justifica CV de vis/dia e CV de cobertura mensal.
function exportVariabilidadeMensal(){
  const cs = getFilteredAtivos();
  const seriesByISID = {};
  (DATA.series_consultor||[]).forEach(r=>{
    (seriesByISID[r.ISID] = seriesByISID[r.ISID] || []).push(r);
  });
  const rows = [];
  cs.forEach(c=>{
    const arr = (seriesByISID[c.ISID] || []).slice().sort((a,b)=>a.ym.localeCompare(b.ym));
    // últimos 12 meses (MAT)
    const arr12 = arr.slice(-12);
    // estatísticas resumidas
    const vd = arr12.filter(r=>r.vis_dia > 0).map(r=>r.vis_dia);
    const meanVD = vd.length ? vd.reduce((a,b)=>a+b,0)/vd.length : 0;
    const stdVD = vd.length ? Math.sqrt(vd.reduce((s,v)=>s+(v-meanVD)**2,0)/vd.length) : 0;
    const cvVD = meanVD > 0 ? (stdVD/meanVD*100) : 0;
    // cobertura mensal por mês
    let cobSerie = [];
    if(c.painel_size > 0){
      cobSerie = arr12.filter(r=>r.medicos > 0).map(r=>({ym:r.ym, cob:(r.medicos/c.painel_size)*100}));
    }
    const cobVals = cobSerie.map(r=>r.cob);
    const meanCob = cobVals.length ? cobVals.reduce((a,b)=>a+b,0)/cobVals.length : 0;
    const stdCob = cobVals.length ? Math.sqrt(cobVals.reduce((s,v)=>s+(v-meanCob)**2,0)/cobVals.length) : 0;
    const cvCob = meanCob > 0 ? (stdCob/meanCob*100) : 0;
    // Uma linha por consultor x mês — formato longo, fácil de filtrar e cruzar no Excel
    arr12.forEach(r=>{
      const cob = c.painel_size > 0 && r.medicos > 0 ? (r.medicos/c.painel_size)*100 : null;
      rows.push([
        c.nome, c.ISID, c.sales_force, c.gd_name||'', c.tipo_setor||'',
        r.ym,
        r.visitas || 0,
        r.medicos || r.medicos_unicos || 0,
        r.dias_ativos || 0,
        (r.vis_dia || 0).toFixed(2),
        cob !== null ? cob.toFixed(1) : '',
        c.painel_size || 0,
        cvVD.toFixed(1),
        cvCob ? cvCob.toFixed(1) : '',
      ]);
    });
  });
  downloadCsv('variabilidade_mes_a_mes.csv',
    ['Consultor','ISID','Sales Force','GD','Setor','Mês (YYYY-MM)',
     'Visitas no mês','Médicos únicos','Dias ativos','Vis/dia',
     '% Cobertura mensal','Painel atual',
     'CV vis/dia 12m (%)','CV cobertura mensal 12m (%)'],
    rows);
}

function exportDetalhe(){
  const cs = getFilteredConsultores();
  const headers = ['Consultor','ISID','Sales Force','GD','Setor','Meses no setor',
    'UF','Cidade','Painel atual','Painel mensal','% Cobertura mensal','Visitas/dia MAT','Visitas MAT',
    'Médicos únicos/mês','Freq/médico/mês','Dias trab/mês','% Ausência',
    'MCCP Painel','MCCP Freq/Tri','MCCP % Cumprido','% Dentro MCCP','% Fora MCCP',
    '% Overlap intra-time','% Overlap cross coerente','% Overlap cross incoerente',
    'Tendência vis/dia','Slope vis/dia','Meses ativos','Admissão',
    'Turnover painel (%)','Turnover flag','Turnover meses analisados'];
  const rows = cs.map(c=>{
    const cobMensal = (c.painel_size > 0 && c.medicos_unicos_mes > 0)
      ? Math.round(c.medicos_unicos_mes / c.painel_size * 100) : '';
    return [c.nome, c.ISID, c.sales_force, c.gd_name, c.tipo_setor, c.meses_no_setor,
      c.uf, c.cidade, c.painel_size, c.painel_mensal, cobMensal, c.vis_dia_media, c.visitas_12m,
      c.medicos_unicos_mes, c.freq_medico_mes, c.dias_trabalhados_mes, c.pct_ausencia,
      c.mccp_panel, c.mccp_freq_media_tri, c.mccp_pct_cumprido, c.pct_dentro_mccp, c.pct_fora_mccp,
      c.pct_overlap_intra, c.pct_overlap_cross_coer, c.pct_overlap_cross_incoer,
      c.tendencia_vis_dia, c.slope_vis_dia, c.meses_ativos, c.admissao,
      c.turnover_pct_3m, c.turnover_flag, c.turnover_n_meses];
  });
  downloadCsv('Healthcheck_' + (DATA.meta.bu||'BU') + '_Detalhe.csv', headers, rows);
}

function exportAusencia(){
  const cs = getFilteredAtivos();
  const j = ST.abs_janela || 'mat';
  const pctKey = j==='1m' ? 'pct_ausencia_1m' : j==='3m' ? 'pct_ausencia_3m' : 'pct_ausencia';
  const labelJ = j==='1m' ? '1m' : j==='3m' ? '3m' : 'MAT';
  const headers = ['Consultor','ISID','Sales Force','GD',
    'Trab./mês','Aus.campo/mês','Viagem/mês','Reunião/mês','Congresso/mês',
    'Treinamento/mês','Gestão/mês','Pessoal/mês', `% Ausência (${labelJ})`];
  const sorted = cs.slice().sort((a,b)=>(b[pctKey]||0) - (a[pctKey]||0));
  const rows = sorted.map(c=>[
    c.nome, c.ISID, c.sales_force, c.gd_name,
    c.trabalhados_mes, c.ausencia_mes, c.deslocamento_mes, c.reunioes_mes,
    c.congressos_mes, c.treinamento_mes, c.gestao_mes, c.pessoais_mes, c[pctKey]
  ]);
  downloadCsv(`Healthcheck_${DATA.meta.bu||'BU'}_Ausencias_${labelJ}.csv`, headers, rows);

  // Mensal por consultor (arquivo separado)
  const isids = new Set(cs.map(c=>c.ISID));
  const m = DATA.series_consultor.filter(r=>isids.has(r.ISID));
  const h2 = ['ISID','YM','Úteis','Ausência','Trabalhados','Deslocamento','Reuniões','Congressos','Treinamento','Gestão','Pessoais'];
  const r2 = m.map(r=>[r.ISID, r.ym, r.uteis, r.ausencia, r.trabalhados, r.deslocamento, r.reunioes, r.congressos, r.treinamento, r.gestao, r.pessoais]);
  downloadCsv('Healthcheck_' + (DATA.meta.bu||'BU') + '_Ausencias_mensal.csv', h2, r2);
}

// Onda 2 — Glossário: gera Healthcheck_Formulas.xls (formato Excel XML SpreadsheetML 2003).
// Não requer biblioteca externa — só XML puro que o Excel abre nativamente.
function downloadFormulasXlsx(){
  const abas = [
    {sheet: 'Visão Geral', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['painel_size', 'Tamanho do painel oficial do consultor (snapshot mais recente)', "len(set(df_painel[df_painel['ISID']==isid]['MDM_CONTA']))", '=CONT.VALORES.ÚNICO(MDM_filtrado_ISID)', '113'],
      ['vis_dia_media (MAT)', 'Visitas por dia trabalhado, média da janela MAT 12m', "visitas_12m / (uteis_12m - ausencia_12m)", '=visitas_12m/(uteis_12m-ausencia_12m)', '4.47'],
      ['medicos_unicos_mes', 'Médicos únicos visitados por mês (média)', "len(set(mdms_mat)) / meses_ativos", '=CONT.VALORES.ÚNICO(MDM)/meses_ativos', '58.33'],
      ['cobertura_mensal_pct', '% do painel oficial tocado em um mês típico', "medicos_unicos_mes / painel_size * 100", '=medicos_unicos_mes/painel_size*100', '52%'],
      ['pct_ausencia', '% do tempo útil ausente (MAT 12m)', "ausencia_12m / uteis_12m * 100", '=ausencia_12m/uteis_12m*100', '24.6%'],
    ]},
    {sheet: 'Detalhe', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['vis_dia_3m / vis_dia_1m', 'Visitas/dia janela 3 ou 1 mês fechado', "vis_3m / (uteis_3m - ausencia_3m)", '=vis_3m/(uteis_3m-ausencia_3m)', '5.56 / 6.04'],
      ['pct_ausencia_3m / 1m', '% ausência janela 3 ou 1 mês', "ausencia_3m / uteis_3m * 100", '=ausencia_3m/uteis_3m*100', '34.6% / 30.3%'],
      ['freq_medico_mes', 'Frequência média de visita por médico/mês', "visitas_mes / medicos_unicos_mes", '=visitas_mes/medicos_unicos_mes', '0.26'],
      ['vis_dia_parcial', 'Vis/dia do mês corrente em andamento', "vis_parcial / dias_uteis_decorridos", '=vis_parcial/dias_uteis_decorridos', '5.54 (parcial)'],
      ['turnover_pct_3m', 'Turnover de painel — % médio de médicos novos/mês (média 3 meses fechados). Médico novo = não visitado nos 3 meses anteriores.', "por mês: len(mdms_mes - mdms_3m_anteriores) / len(mdms_mes) * 100. Depois: média 3 últimos meses.", '=MÉDIA(últimos_3_meses(%novos))', '23% (equilibrado)'],
      ['turnover_flag', 'Classificação do turnover: estável <15%, equilibrado 15-30%, rotativo 30-50%, volátil >50%.', "if pct<15: 'estavel'; elif <30: 'equilibrado'; elif <50: 'rotativo'; else: 'volatil'", '=SE(pct<15;"estável";SE(pct<30;"equilibrado";SE(pct<50;"rotativo";"volátil")))', 'estável'],
    ]},
    {sheet: 'Visitação', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['pct_dentro_mccp', '% visitas do trimestre para médicos no plano MCCP', "visitas_dentro_mccp / visitas_ciclo_total * 100", '=visitas_dentro_mccp/visitas_ciclo_total*100', '97.6%'],
      ['mccp_pct_cumprido', '% da meta MCCP do trimestre cumprida', "mccp_realizado / mccp_target_tri * 100", '=mccp_realizado/mccp_target_tri*100', '42.2%'],
      ['Top fora painel', 'Médicos não-painel visitados pelo time', "Filtro: med ∈ visitados ∧ med ∉ painel", '—', '—'],
    ]},
    {sheet: 'Linha do Tempo', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['slope_vis_dia_6m', 'Inclinação da reg. linear de vis/dia nos últimos 6 meses', "np.polyfit(range(6), vd_6m_serie, 1)[0]", '=INCLINAÇÃO(serie_vd_6m;{1;2;3;4;5;6})', '-0.562 (Cecchim)'],
      ['tendencia_vis_dia_6m', 'Classificação do slope 6m', "Estável se |slope|<0.02; Piorando se <0; Melhorando se >0", '—', 'Piorando'],
      ['cv_vis_dia', 'Coef. variação de vis/dia mensal (consistência)', "std(vis_dia_serie) / mean(vis_dia_serie) * 100", '=DESVPAD(serie)/MÉDIA(serie)*100', '31.8%'],
      ['cob_mensal_cv', 'Coef. variação da cobertura mensal', "std(cob_serie) / mean(cob_serie) * 100", '=DESVPAD(cob_serie)/MÉDIA(cob_serie)*100', '18%'],
    ]},
    {sheet: 'Ausências', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['ausencia_mes', 'Dias ausentes por mês (média)', "ausencia_12m / 12", '=ausencia_12m/12', '6.15 dias'],
      ['correl ausencia x cobertura', 'Pearson entre %ausência (X) e %cobertura mensal (Y) por consultor', "scipy.stats.pearsonr(aus, cob)", '=CORREL(serie_aus;serie_cob)', '-0.45 (forte negativa)'],
    ]},
    {sheet: 'Deslocamento', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['tipo_setor', 'Classificação Local / Misto / Viagem', "≤1 UF significativa: Local · 2: Misto · ≥3: Viagem", '—', 'Viagem Interestadual'],
      ['pct_visitas_cidade_sede', '% das visitas na cidade-sede (config estrutura.xlsx)', "visitas_cidade_sede / visitas_total * 100", '=visitas_cidade_sede/visitas_total*100', '49% (Floripa)'],
    ]},
    {sheet: 'Overlap', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['pct_overlap_intra', '% painel visitado também por colega da MESMA SF', "shared_intra / painel_size * 100", '=shared_intra/painel_size*100', '1.3%'],
      ['pct_sobre_menor (par)', 'Compartilhados ÷ painel do menor dos 2 consultores', "shared / min(A_total, B_total) * 100", '=shared/MÍN(A_total;B_total)*100', '87%'],
      ['Periodo painel', 'Snapshot mais recente disponível', "max(SNAPSHOT_DATE_DT)", '—', '2026-04-01'],
    ]},
    {sheet: 'Universo', linhas: [
      ['Métrica', 'Definição', 'Fórmula Python', 'Fórmula Excel', 'Exemplo'],
      ['BU', 'estrutura.xlsx coluna BU', "df[df['BU']=='ONCOLOGIA']", '=BU="ONCOLOGIA"', 'ONCOLOGIA'],
      ['HIERARCHY', 'estrutura.xlsx coluna ACC HIERARCHY LEVEL', "df[df['ACC HIERARCHY LEVEL']=='REP']", '=ACC_HIERARCHY="REP"', 'REP'],
      ['ISIDS_AFASTADOS', 'Excluídos de agregados/rankings via flag afastado=True', "afastado = c['ISID'] in ISIDS_AFASTADOS", '—', "SACOMAN, CECCHIAN, DEOLMARI"],
    ]},
  ];

  // Escapar XML
  const xmlEsc = s => String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&apos;');

  let xml = '<?xml version="1.0"?>\n';
  xml += '<?mso-application progid="Excel.Sheet"?>\n';
  xml += '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"\n';
  xml += '  xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n';
  xml += '<Styles>\n';
  xml += '<Style ss:ID="Header"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#1B1F23" ss:Pattern="Solid"/><Alignment ss:Vertical="Center"/></Style>\n';
  xml += '<Style ss:ID="Body"><Alignment ss:Vertical="Top" ss:WrapText="1"/></Style>\n';
  xml += '</Styles>\n';

  abas.forEach(a => {
    xml += `<Worksheet ss:Name="${xmlEsc(a.sheet)}">\n`;
    xml += '<Table>\n';
    xml += '<Column ss:Width="180"/><Column ss:Width="280"/><Column ss:Width="280"/><Column ss:Width="220"/><Column ss:Width="140"/>\n';
    a.linhas.forEach((row, idx) => {
      const styleAttr = idx === 0 ? ' ss:StyleID="Header"' : ' ss:StyleID="Body"';
      xml += `<Row${styleAttr}>`;
      row.forEach(cell => {
        xml += `<Cell${styleAttr}><Data ss:Type="String">${xmlEsc(cell)}</Data></Cell>`;
      });
      xml += '</Row>\n';
    });
    xml += '</Table>\n</Worksheet>\n';
  });
  xml += '</Workbook>\n';

  // Download
  const blob = new Blob(['\ufeff' + xml], {type: 'application/vnd.ms-excel;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'Healthcheck_Formulas_' + (DATA.meta.bu || 'BU') + '.xls';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(()=>URL.revokeObjectURL(url), 500);
}

function exportOverlapIntra(){
  const cs = getFilteredConsultores().filter(c=>c.medicos_visit_12m>0);
  const headers = ['Consultor','ISID','Sales Force','GD','Painel visitado',
    'Compartilhados intra-SF','% sobre painel','Cross coerente','Cross incoerente','Cross não-class.','Exclusivos'];
  const rows = cs.map(c=>[
    c.nome, c.ISID, c.sales_force, c.gd_name, c.medicos_visit_12m,
    c.shared_intra, c.pct_overlap_intra, c.shared_cross_coer, c.shared_cross_incoer, c.shared_cross_naoclass, c.exclusivos
  ]);
  downloadCsv('Healthcheck_' + (DATA.meta.bu||'BU') + '_OverlapIntra.csv', headers, rows);
}

function exportPares(){
  let pairs = DATA.pares_overlap.slice();
  const validIsids = new Set(getFilteredConsultores(true).map(c=>c.ISID));
  pairs = pairs.filter(p=>validIsids.has(p.A) && validIsids.has(p.B));
  if(ST.pair_tipo==='intra') pairs = pairs.filter(p=>p.tipo==='intra-time' || p.tipo==='intra');
  else if(ST.pair_tipo==='cross') pairs = pairs.filter(p=>p.tipo==='cross-team');
  if(ST.consultor!=='__all__') pairs = pairs.filter(p=>p.A===ST.consultor || p.B===ST.consultor);
  const headers = ['Consultor A','SF A','GD A','Consultor B','SF B','GD B','Tipo',
    'A painel','B painel','Compartilhados','% sobre menor',
    'Médicos mesmo dia','% mesmo dia','Médicos em ≤7 dias','% em ≤7 dias','Padrão de visita',
    'Visitas par total'];
  const rows = pairs.map(p=>[
    p.A_nome||p.A, p.A_sf, p.A_gd, p.B_nome||p.B, p.B_sf, p.B_gd, p.tipo,
    p.A_total, p.B_total, p.shared, p.pct_min,
    p.medicos_mesmo_dia_n||p.mesmo_dia||0, p.pct_mesmo_dia||0,
    p.medicos_7d_n||p.gap_3d||0, p.pct_7d||0,
    p.padrao_visita||'Distribuídos',
    p.visitas_par_total
  ]);
  downloadCsv('Healthcheck_' + (DATA.meta.bu||'BU') + '_Pares.csv', headers, rows);

  // Médicos compartilhados (arquivo separado)
  const h2 = ['A','A_nome','A_sf','B','B_nome','B_sf','Tipo','MDM','CRM','Nome médico','Especialidade','Visitas A','Visitas B'];
  const r2 = (DATA.pares_medicos_detail||[])
    .filter(m=>validIsids.has(m.A) && validIsids.has(m.B))
    .map(m=>[m.A, m.A_nome, m.A_sf, m.B, m.B_nome, m.B_sf, m.tipo, m.MDM, m.medico_crm, m.medico_nome, m.esp1, m.visitas_A, m.visitas_B]);
  downloadCsv('Healthcheck_' + (DATA.meta.bu||'BU') + '_Pares_medicos.csv', h2, r2);
}

// ============================================================================
// ABA SETOR — análise brickagem × atuação real
// ============================================================================
function renderSetor(){
  const cs = getFilteredConsultores();
  // Janela das visitas (afeta apenas as % na cidade/UF sede)
  const j = ST.setor_janela || 'mat';
  const labelJ = j==='1m' ? 'último mês' : j==='3m' ? 'últimos 3m' : 'MAT 12m';
  const pctUfKey = j==='1m' ? 'pct_visitas_uf_sede_1m' : j==='3m' ? 'pct_visitas_uf_sede_3m' : 'pct_visitas_uf_sede';
  const pctCidKey = j==='1m' ? 'pct_visitas_cidade_sede_1m' : j==='3m' ? 'pct_visitas_cidade_sede_3m' : 'pct_visitas_cidade_sede';

  // Status do banner cidade-sede
  const nOk = cs.filter(c=>c.cidade_sede_status==='ok').length;
  const nVal = cs.filter(c=>c.cidade_sede_status!=='ok').length;
  // Atualizar contador no banner amarelo de aviso da seção
  const sedeBannerNum = document.getElementById('sede-preenchidos');
  if(sedeBannerNum) sedeBannerNum.textContent = `${nOk} dos ${cs.length}`;
  const elStatus = document.getElementById('sede-status-text');
  if(elStatus){
    elStatus.innerHTML = `<strong>${nOk}</strong> consultor${nOk===1?'':'es'} com cidade sede preenchida no recorte. <strong>${nVal}</strong> ${nVal===1?'aguarda':'aguardam'} validação.`;
  }

  // Contagem das categorias
  const nLocal = cs.filter(c=>c.tipo_setor==='Local').length;
  const nVint = cs.filter(c=>c.tipo_setor==='Viagem Interna').length;
  const nVinter = cs.filter(c=>c.tipo_setor==='Viagem Interestadual').length;
  document.getElementById('cat-local-n').textContent = nLocal;
  document.getElementById('cat-vint-n').textContent = nVint;
  document.getElementById('cat-vinter-n').textContent = nVinter;

  // KPIs do recorte — % sede usa janela escolhida
  const csCom = cs.filter(c=>c.cidades_alocadas_n>0);
  const mediaCob = csCom.length? mean(csCom.map(c=>c.pct_cobertura_cidades||0)) : 0;
  const csSedeOk = cs.filter(c=>c.cidade_sede_status==='ok' && c[pctUfKey]!==null && c[pctUfKey]!==undefined);
  const mediaUfSede = csSedeOk.length? mean(csSedeOk.map(c=>c[pctUfKey])) : null;
  const csCidOk = cs.filter(c=>c.cidade_sede_status==='ok' && c[pctCidKey]!==null && c[pctCidKey]!==undefined);
  const mediaCidSede = csCidOk.length? mean(csCidOk.map(c=>c[pctCidKey])) : null;
  const mediaCidAloc = csCom.length? mean(csCom.map(c=>c.cidades_alocadas_n||0)) : 0;

  const kpis = [
    {lbl:'% Cobertura média da brickagem', val: pct(mediaCob),
     sub:'cidades visitadas (conta primária, MAT 12m) ÷ cidades alocadas (brickagem)'},
    {lbl:`% Vis. na cidade sede (${labelJ})`, val: mediaCidSede===null?'—':pct(mediaCidSede),
     sub: csCidOk.length>0 ? csCidOk.length+' consultor'+(csCidOk.length===1?'':'es')+' com sede definida' : 'aguardando validação da cidade sede'},
    {lbl:`% Vis. na UF sede (${labelJ})`, val: mediaUfSede===null?'—':pct(mediaUfSede),
     sub: csSedeOk.length>0 ? csSedeOk.length+' consultor'+(csSedeOk.length===1?'':'es')+' com sede definida' : 'aguardando validação'},
    // Removido: 'Média de cidades por consultor (brickagem)' — não acrescentava (consultor pode ter estado inteiro na brickagem)
  ];
  document.getElementById('setor-kpis').innerHTML = kpis.map(k=>`
    <div class="card">
      <div class="card-title">${k.lbl}</div>
      <div class="card-num">${k.val}</div>
      <div class="card-sub">${k.sub}</div>
    </div>`).join('');

  // Flags
  document.getElementById('flag-brick-n').textContent = cs.filter(c=>c.flag_brickagem_subutilizada).length;
  document.getElementById('flag-fora-n').textContent = cs.filter(c=>c.flag_fora_uf_sede).length;
  document.getElementById('flag-aus-n').textContent = cs.filter(c=>c.flag_ausencia_subreportada).length;

  // Tabela
  const tbody = document.querySelector('#tbl-setor tbody');
  const csSorted = [...cs].sort((a,b)=>{
    // Flags primeiro, depois nome
    const af = (a.flag_brickagem_subutilizada?1:0) + (a.flag_fora_uf_sede?1:0) + (a.flag_ausencia_subreportada?1:0);
    const bf = (b.flag_brickagem_subutilizada?1:0) + (b.flag_fora_uf_sede?1:0) + (b.flag_ausencia_subreportada?1:0);
    if(bf !== af) return bf - af;
    return String(a.nome||'').localeCompare(String(b.nome||''),'pt-BR');
  });
  tbody.innerHTML = csSorted.map(c=>{
    let flags = '';
    if(c.flag_brickagem_subutilizada) flags += '<span class="flag-tag brick" data-tip="Cidades alocadas: '+c.cidades_alocadas_n+'; visitou só '+c.cidades_visitadas_n+' ('+(c.pct_cobertura_cidades||0).toFixed(0)+'%)">B</span>';
    if(c.flag_fora_uf_sede) flags += '<span class="flag-tag fora" data-tip="UF sede '+(c.uf_sede||'?')+' tem só '+(c.pct_visitas_uf_sede||0).toFixed(0)+'% das visitas">F</span>';
    if(c.flag_ausencia_subreportada) flags += '<span class="flag-tag aus" data-tip="'+(c.gap_dias_nao_explicados||0)+' dias úteis sem visita e sem ausência lançada">A</span>';
    if(!flags) flags = '<span style="color:var(--ink3);">—</span>';

    const corCob = c.pct_cobertura_cidades < 15 ? 'var(--warn)' : c.pct_cobertura_cidades > 50 ? 'var(--teal)' : 'var(--ink2)';
    const isOk = c.cidade_sede_status==='ok';
    const cidadeSedeDisp = isOk ? escapeHtml(c.cidade_sede||'—') :
        '<span class="flag-tag" style="background:#FFF3E0;color:#D4900A;font-size:9.5px;">em validação</span>';
    const ufSedeDisp = isOk ? escapeHtml(c.uf_sede||'—') : '—';
    // Pcts na janela escolhida
    const pctCidVal = c[pctCidKey];
    const pctUfVal = c[pctUfKey];
    const pctCidSedeDisp = (isOk && pctCidVal!==null && pctCidVal!==undefined) ? pct(pctCidVal) : '—';
    const pctUfSedeDisp = (isOk && pctUfVal!==null && pctUfVal!==undefined) ? pct(pctUfVal) : '—';
    const corUf = (isOk && pctUfVal!==null && pctUfVal!==undefined && pctUfVal < 50) ? 'var(--danger)' : 'var(--ink2)';

    return `
    <tr data-isid="${c.ISID}" onclick="showPerfUf('${c.ISID}')" style="cursor:pointer;">
      <td class="nm">${escapeHtml(c.nome)}</td>
      <td>${escapeHtml(c.sales_force||'')}</td>
      <td>${escapeHtml(c.tipo_setor||'—')}</td>
      <td>${cidadeSedeDisp}</td>
      <td>${ufSedeDisp}</td>
      <td class="num">${c.ufs_alocadas_n||0}</td>
      <td class="num">${fmt(c.cidades_alocadas_n)}</td>
      <td class="num">${fmt(c.cidades_visitadas_n)}</td>
      <td class="num" style="color:${corCob};font-weight:700;">${pct(c.pct_cobertura_cidades)}</td>
      <td class="num">${pctCidSedeDisp}</td>
      <td class="num" style="color:${corUf};font-weight:700;">${pctUfSedeDisp}</td>
      <td class="num" style="font-weight:700;color:${
        c.score_territorio===null||c.score_territorio===undefined ? 'var(--ink3)' :
        c.score_territorio >= 80 ? 'var(--teal)' :
        c.score_territorio >= 60 ? 'var(--warn)' : 'var(--danger)'
      };">${c.score_territorio===null||c.score_territorio===undefined ? '—' : c.score_territorio.toFixed(0)}</td>
      <td><span style="font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;background:${
        c.score_territorio_status==='saudavel' ? '#E8F4F2' :
        c.score_territorio_status==='atencao'  ? '#FEF5E4' :
        c.score_territorio_status==='critico'  ? '#FBE9EC' : '#F2F4F6'
      };color:${
        c.score_territorio_status==='saudavel' ? '#005F58' :
        c.score_territorio_status==='atencao'  ? '#7A4D00' :
        c.score_territorio_status==='critico'  ? '#8C0B23' : 'var(--ink3)'
      };">${
        c.score_territorio_status==='saudavel' ? 'Saudável' :
        c.score_territorio_status==='atencao'  ? 'Atenção' :
        c.score_territorio_status==='critico'  ? 'Crítico'  : '—'
      }</span></td>
      <td>${flags}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="14" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados no recorte.</td></tr>';

  // Atualizar headers das colunas com a janela — preservando sort-arrow se houver
  const thRow = document.querySelector('#tbl-setor thead tr');
  if(thRow){
    const ths = thRow.querySelectorAll('th');
    const setLabel = (th, newLabel)=>{
      if(!th) return;
      const arrow = th.querySelector('.sort-arrow');
      setThLabel(th, newLabel);
    };
    setLabel(ths[9], '% Vis. na cidade sede (' + labelJ + ')');
    setLabel(ths[10], '% Vis. na UF sede (' + labelJ + ')');
  }

  // Auto-mostrar perf por UF se for consultor único
  if(ST.consultor && ST.consultor!=='__all__'){
    showPerfUf(ST.consultor);
  } else {
    document.getElementById('setor-perf-uf-block').style.display = 'none';
  }
  aplicarSortEmTodasTabelas();
}

function showPerfUf(isid){
  const c = DATA.consultores.find(x=>x.ISID===isid);
  if(!c) return;
  const block = document.getElementById('setor-perf-uf-block');
  block.style.display = 'block';
  document.getElementById('setor-perf-uf-titulo').innerHTML =
    `${escapeHtml(c.nome)} <span style="color:var(--ink3);font-weight:500;">· ${escapeHtml(c.sales_force)} · ${escapeHtml(c.tipo_setor)} · UF sede: ${escapeHtml(c.uf_sede||'—')}</span>`;
  const perf = c.performance_por_uf || [];
  const tbody = document.querySelector('#tbl-perf-uf tbody');
  if(!perf.length){
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--ink3);padding:14px;">Sem visitas no MAT.</td></tr>';
    return;
  }
  // Maior vis/dia entre as UFs do consultor
  const maxVisDia = Math.max(...perf.map(r=>r.vis_dia||0));
  tbody.innerHTML = perf.map(r=>{
    let obs = '';
    if(r.is_sede) obs += '<span style="color:var(--purple);font-weight:700;">UF sede</span> ';
    if(r.vis_dia === maxVisDia && perf.length > 1) obs += '<span style="color:var(--teal);">melhor produtividade</span>';
    if(!obs) obs = '<span style="color:var(--ink3);">—</span>';
    return `
    <tr>
      <td><strong>${escapeHtml(r.uf)}</strong></td>
      <td class="num">${fmt(r.visitas)}</td>
      <td class="num">${fmt(r.dias_ativos)}</td>
      <td class="num">${fmt(r.vis_dia,2)}</td>
      <td class="num">${fmt(r.medicos)}</td>
      <td>${obs}</td>
    </tr>`;
  }).join('');
}

function exportSetor(){
  const cs = getFilteredConsultores();
  const rows = cs.map(c=>{
    const flags = [];
    if(c.flag_brickagem_subutilizada) flags.push('Brickagem subutilizada');
    if(c.flag_fora_uf_sede) flags.push('Atuando fora UF sede');
    if(c.flag_ausencia_subreportada) flags.push('Ausência subreportada ('+c.gap_dias_nao_explicados+'d)');
    return [c.nome, c.sales_force, c.gd_name, c.tipo_setor,
            c.cidade_sede||'', c.uf_sede||'', c.cidade_sede_status,
            c.ufs_alocadas_n||0, c.cidades_alocadas_n, c.cidades_visitadas_n,
            c.cidades_alocadas_visitadas_n, c.pct_cobertura_cidades,
            c.pct_visitas_cidade_sede!==null && c.pct_visitas_cidade_sede!==undefined ? c.pct_visitas_cidade_sede : '',
            c.pct_visitas_uf_sede!==null && c.pct_visitas_uf_sede!==undefined ? c.pct_visitas_uf_sede : '',
            c.pct_visitas_fora_uf_sede!==null && c.pct_visitas_fora_uf_sede!==undefined ? c.pct_visitas_fora_uf_sede : '',
            flags.join(' | '), c.gap_dias_nao_explicados||0,
            (c.cidades_nao_visitadas_sample||[]).slice(0,5).join(' | ')];
  });
  downloadCsv('deslocamento_analise.csv',
    ['Consultor','Sales Force','GD','Deslocamento',
     'Cidade Sede','UF Sede','Status Sede',
     'UFs alocadas (n)','Cidades alocadas','Cidades visitadas',
     'Cidades alocadas E visitadas','% Cobertura',
     '% Visitas cidade sede','% Visitas UF sede','% Visitas fora UF sede',
     'Flags','Gap dias não explicados','Cidades alocadas NÃO visitadas (sample)'],
    rows);
}


// ============================================================================
// ABA VISITAÇÃO — Cobertura painel + Frequência + MCCP
// ============================================================================
function getQuartersDisponiveis(){
  // Pega quarters do primeiro consultor (todos têm os mesmos)
  if(!DATA.consultores.length || !DATA.consultores[0].quarters) return [];
  return DATA.consultores[0].quarters || [];
}

function labelQuarterPt(qlabel){
  // "2025-Q4" → "Q4/25"
  const m = String(qlabel||'').match(/^(\d{4})-Q(\d)$/);
  if(!m) return qlabel;
  return 'Q' + m[2] + '/' + m[1].slice(2);
}

function getVisitQuarter(){
  // Retorna o quarter selecionado (default = atual)
  const qs = getQuartersDisponiveis();
  if(!qs.length) return null;
  const sel = ST.visit_quarter;
  return qs.find(q=>q.label===sel) || qs[qs.length-1];  // último = corrente
}

function setVisitQuarter(qlabel){
  ST.visit_quarter = qlabel;
  document.querySelectorAll('#visit-q-toggle button').forEach(b=>{
    b.classList.toggle('active', b.dataset.q===qlabel);
  });
  document.querySelectorAll('#freq-q-toggle button').forEach(b=>{
    b.classList.toggle('active', b.dataset.q===qlabel);
  });
  renderVisitation();
}

function renderVisitQuarterToggle(){
  const qs = getQuartersDisponiveis();
  if(!qs.length) return;
  const current = ST.visit_quarter || qs[qs.length-1].label;
  // Toggle Visitação
  const t1 = document.getElementById('visit-q-toggle');
  if(t1 && !t1.children.length){
    t1.innerHTML = qs.map(q=>{
      const active = q.label===current ? ' class="active"' : '';
      return `<button${active} data-q="${q.label}" onclick="setVisitQuarter('${q.label}')">${labelQuarterPt(q.label)}</button>`;
    }).join('');
  }
  // Toggle Frequência
  const t2 = document.getElementById('freq-q-toggle');
  if(t2 && !t2.children.length){
    t2.innerHTML = qs.map(q=>{
      const active = q.label===current ? ' class="active"' : '';
      return `<button${active} data-q="${q.label}" onclick="setVisitQuarter('${q.label}')">${labelQuarterPt(q.label)}</button>`;
    }).join('');
  }
}

function renderVisitation(){
  // Garantir que os toggles existem (primeira chamada)
  renderVisitQuarterToggle();

  const cs = getFilteredAtivos();
  const q = getVisitQuarter();
  if(!q) return;
  const labelQ = labelQuarterPt(q.label);

  // === Painel POR QUARTER (snapshot do 2º mês) ===
  // Cada consultor tem c.quarters[i].painel_mdms — agregamos pelo quarter selecionado
  const allPainel = new Set();
  let snapUsado = null;
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(qc){
      getPainelMdms(c, qc).forEach(m=>allPainel.add(m));
      if(qc.painel_snapshot) snapUsado = qc.painel_snapshot;
    }
  });
  // Atualizar header de referência
  const elRef = document.getElementById('visit-painel-ref');
  if(elRef){
    elRef.innerHTML = `Painel oficial do quarter: <strong>${fmt(allPainel.size)}</strong> médicos (snapshot <strong>${snapUsado||'—'}</strong>) · Visitas: <strong>${labelQ}</strong>`;
  }

  // === Visitados no quarter ===
  const visitados = new Set();
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(qc) (qc.mdms||[]).forEach(m=>visitados.add(m));
  });
  let dentro=0, fora=0;
  visitados.forEach(m=>{ if(allPainel.has(m)) dentro++; else fora++; });

  const medItems = [
    {
      lbl: 'Total único visitado em ' + labelQ,
      val: fmt(visitados.size),
      sub: cs.length + ' consultor' + (cs.length===1?'':'es') + ' no recorte · dedupe global',
      cls: 'accent-teal'
    },
    {
      lbl: 'Dentro do painel oficial',
      val: fmt(dentro),
      sub: allPainel.size > 0
        ? Math.round(dentro/allPainel.size*100) + '% do painel (' + fmt(allPainel.size) + ' méd.) visitado em ' + labelQ
        : 'sem painel oficial no recorte',
      cls: 'accent-purple'
    },
    {
      lbl: 'Fora do painel',
      val: fmt(fora),
      sub: visitados.size > 0
        ? Math.round(fora/visitados.size*100) + '% das visitas do período vão para médicos fora do painel'
        : '—',
      cls: 'accent-warn'
    }
  ];
  const elMed = document.getElementById('kpi-medicos');
  if(elMed){
    elMed.innerHTML = medItems.map(it=>`
      <div class="kpi ${it.cls||''}">
        <div class="kpi-lbl">${it.lbl}</div>
        <div class="kpi-val">${it.val}</div>
        <div class="kpi-sub">${it.sub}</div>
      </div>`).join('');
  }

  // === Tabela por Sales Force — também usa painel do quarter ===
  const bySf = {};
  cs.forEach(c=>{
    const sf = c.sales_force || '—';
    if(!bySf[sf]) bySf[sf] = {sf, n:0, painel:new Set(), visitados:new Set()};
    bySf[sf].n++;
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    // Fallback (mesmo da tabela por consultor) — usa painel atual quando quarter não tem
    getPainelMdms(c, qc).forEach(m=>bySf[sf].painel.add(m));
    if(qc){
      (qc.mdms||[]).forEach(m=>bySf[sf].visitados.add(m));
    }
  });
  const sfRows = Object.values(bySf).map(g=>{
    let dentro=0, fora=0;
    g.visitados.forEach(m=>{ if(g.painel.has(m)) dentro++; else fora++; });
    const cobertura = g.painel.size>0 ? Math.round(dentro/g.painel.size*100) : null;
    const pctFora = g.visitados.size>0 ? Math.round(fora/g.visitados.size*100) : null;
    return {sf:g.sf, n:g.n, painel:g.painel.size, visitados:g.visitados.size, dentro, fora, cobertura, pctFora};
  }).sort((a,b)=>(b.fora||0) - (a.fora||0));  // DESC por fora — Onda 5

  const tbodySf = document.querySelector('#tbl-visit-sf tbody');
  if(tbodySf){
    tbodySf.innerHTML = sfRows.map(r=>{
      const corCob = r.cobertura===null ? 'var(--ink3)' : r.cobertura<30 ? 'var(--danger)' : r.cobertura<60 ? 'var(--warn)' : 'var(--teal)';
      const corFora = r.pctFora===null ? 'var(--ink3)' : r.pctFora>60 ? 'var(--warn)' : 'var(--ink2)';
      return `
      <tr>
        <td class="nm">${escapeHtml(r.sf)}</td>
        <td class="num">${r.n}</td>
        <td class="num">${fmt(r.painel)}</td>
        <td class="num">${fmt(r.visitados)}</td>
        <td class="num">${fmt(r.dentro)}</td>
        <td class="num">${fmt(r.fora)}</td>
        <td class="num" style="color:${corCob};font-weight:700;">${r.cobertura===null?'—':r.cobertura+'%'}</td>
        <td class="num" style="color:${corFora};">${r.pctFora===null?'—':r.pctFora+'%'}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="8" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados.</td></tr>';
  }
  const thV = document.querySelector('#tbl-visit-sf thead tr');
  if(thV){
    const ths = thV.querySelectorAll('th');
    if(ths[2]) setThLabel(ths[2], 'Painel ' + labelQ);
    if(ths[3]) setThLabel(ths[3], 'Visitados em ' + labelQ);
  }

  // === Tabela por Consultor — usa painel do quarter ===
  const tbodyC = document.querySelector('#tbl-visit-cons tbody');
  if(tbodyC){
    const consRows = cs.map(c=>{
      const qc = (c.quarters||[]).find(x=>x.label===q.label);
      const pSet = new Set(getPainelMdms(c, qc));
      const vSet = new Set(qc ? (qc.mdms||[]) : []);
      let dentro=0, fora=0;
      vSet.forEach(m=>{ if(pSet.has(m)) dentro++; else fora++; });
      const cobertura = pSet.size>0 ? Math.round(dentro/pSet.size*100) : null;
      const pctFora = vSet.size>0 ? Math.round(fora/vSet.size*100) : null;
      return {c, painel:pSet.size, visitados:vSet.size, dentro, fora, cobertura, pctFora};
    }).sort((a,b)=>(b.fora||0) - (a.fora||0));
    tbodyC.innerHTML = consRows.map(r=>{
      const c = r.c;
      const corCob = r.cobertura===null ? 'var(--ink3)' : r.cobertura<30 ? 'var(--danger)' : r.cobertura<60 ? 'var(--warn)' : 'var(--teal)';
      const corFora = r.pctFora===null ? 'var(--ink3)' : r.pctFora>60 ? 'var(--warn)' : 'var(--ink2)';
      return `
      <tr>
        <td class="nm">${escapeHtml(c.nome)}</td>
        <td>${escapeHtml(c.sales_force||'')}</td>
        <td>${escapeHtml(c.gd_name||'—')}</td>
        <td class="num">${fmt(r.painel)}</td>
        <td class="num">${fmt(r.visitados)}</td>
        <td class="num">${fmt(r.dentro)}</td>
        <td class="num">${fmt(r.fora)}</td>
        <td class="num" style="color:${corCob};font-weight:700;">${r.cobertura===null?'—':r.cobertura+'%'}</td>
        <td class="num" style="color:${corFora};">${r.pctFora===null?'—':r.pctFora+'%'}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="9" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados.</td></tr>';
  }
  const thC = document.querySelector('#tbl-visit-cons thead tr');
  if(thC){
    const ths = thC.querySelectorAll('th');
    if(ths[3]) setThLabel(ths[3], 'Painel ' + labelQ);
    if(ths[4]) setThLabel(ths[4], 'Visitados em ' + labelQ);
  }

  // === Frequência granular ===
  renderFreqMedicoChart(cs, q);

  // === Médicos parados há 60+ dias ===
  renderMedicosParados(cs);

  // === Top médicos fora do painel ===
  renderMedicosForaPainel(cs);

  // === Tabela Visitas dentro/fora MCCP ===
  const tbodyM = document.querySelector('#tbl-visit-mccp tbody');
  if(tbodyM){
    const linhas = cs.filter(c=>c.mccp_q_disponivel && c.visitas_ciclo_total>0);
    const ordenado = linhas.sort((a,b)=>(b.pct_fora_mccp||0)-(a.pct_fora_mccp||0));
    tbodyM.innerHTML = ordenado.map(c=>{
      const pf = c.pct_fora_mccp || 0;
      const diag = pf>50 ? '<span style="color:var(--warn);font-weight:700;">muita prospecção</span>' :
                   pf>30 ? '<span style="color:var(--ink2);">complementação ao plano</span>' :
                   '<span style="color:var(--teal);">aderente ao plano</span>';
      return `
      <tr>
        <td class="nm">${escapeHtml(c.nome)}</td>
        <td>${escapeHtml(c.sales_force||'')}</td>
        <td class="num">${fmt(c.visitas_ciclo_total)}</td>
        <td class="num">${fmt(c.visitas_dentro_mccp)}</td>
        <td class="num">${fmt(c.visitas_fora_mccp)}</td>
        <td class="num">${pct(c.pct_dentro_mccp)}</td>
        <td class="num">${pct(c.pct_fora_mccp)}</td>
        <td>${diag}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="8" style="text-align:center;color:var(--ink3);padding:14px;">Nenhum consultor com MCCP no trimestre corrente para o recorte.</td></tr>';
  }
  aplicarSortEmTodasTabelas();
}

// ============================================================================
// FREQUÊNCIA POR MÉDICO — gráfico de barras granular (1×, 2×, ..., 7+)
// ============================================================================
function renderFreqMedicoChart(cs, q){
  if(!cs.length || !q) return;
  // Painel POR QUARTER (não o painel atual fixo)
  const allPainel = new Set();
  let snapUsado = null;
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(qc){
      getPainelMdms(c, qc).forEach(m=>allPainel.add(m));
      if(qc.painel_snapshot) snapUsado = qc.painel_snapshot;
    }
  });
  // Buckets por frequência
  const buckets = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0, 6:0, '7+':0};
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(!qc) return;
    buckets[1] += qc.n_med_1x || 0;
    buckets[2] += qc.n_med_2x || 0;
    buckets[3] += qc.n_med_3x || 0;
    buckets[4] += qc.n_med_4x || 0;
    buckets[5] += qc.n_med_5x || 0;
    buckets[6] += qc.n_med_6x || 0;
    buckets['7+'] += qc.n_med_7p || 0;
  });
  // Médicos do painel do quarter NÃO visitados no quarter = 0×
  const visitadosQ = new Set();
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(qc) (qc.mdms||[]).forEach(m=>visitadosQ.add(m));
  });
  const naoVisitadosNoPainel = [...allPainel].filter(m=>!visitadosQ.has(m)).length;
  buckets[0] = naoVisitadosNoPainel;

  // Header explícito
  const totalVisitadosQ = visitadosQ.size;
  const dentroPainelQ = [...visitadosQ].filter(m=>allPainel.has(m)).length;
  const labelQ = labelQuarterPt(q.label);
  document.getElementById('freq-medico-header').innerHTML =
    `Painel oficial do ${labelQ}: <strong>${fmt(allPainel.size)}</strong> médicos (snapshot ${snapUsado||'—'}) · ` +
    `Visitados em ${labelQ}: <strong>${fmt(totalVisitadosQ)}</strong> ` +
    `(<strong>${fmt(dentroPainelQ)}</strong> do painel + <strong>${fmt(totalVisitadosQ-dentroPainelQ)}</strong> fora do painel)`;

  // Renderizar gráfico de barras
  const labels = ['0×','1×','2×','3×','4×','5×','6×','7+'];
  const values = [buckets[0], buckets[1], buckets[2], buckets[3], buckets[4], buckets[5], buckets[6], buckets['7+']];
  const colors = ['#C8102E', '#D4900A', '#E0B040', '#9F7BBF', '#6B3FA0', '#5BB59E', '#00857C', '#003A39'];

  const w = 880, h = 320;
  const pad = {l:40, r:20, t:30, b:50};
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const vmax = Math.max(...values, 1);
  const niceMax = nice(vmax * 1.15);
  const barW = innerW / labels.length * 0.7;
  const slotW = innerW / labels.length;

  let grid = '';
  for(let i=0; i<=5; i++){
    const v = niceMax * i / 5;
    const y = pad.t + innerH - (v/niceMax)*innerH;
    grid += `<line x1="${pad.l}" y1="${y}" x2="${pad.l+innerW}" y2="${y}" stroke="#E8EEF3" stroke-dasharray="2,3"/>`;
    grid += `<text x="${pad.l-6}" y="${y+3}" text-anchor="end" font-size="9.5" fill="#8A9BAD" font-family="Arial">${Math.round(v)}</text>`;
  }
  let bars = '';
  labels.forEach((lbl, i)=>{
    const v = values[i];
    const x = pad.l + i*slotW + (slotW-barW)/2;
    const bh = (v/niceMax)*innerH;
    const y = pad.t + innerH - bh;
    bars += `<rect x="${x}" y="${y}" width="${barW}" height="${bh}" fill="${colors[i]}" rx="3"/>`;
    bars += `<text x="${x+barW/2}" y="${y-6}" text-anchor="middle" font-size="11" font-weight="700" fill="${colors[i]}" font-family="Arial">${fmt(v)}</text>`;
    bars += `<text x="${x+barW/2}" y="${pad.t+innerH+18}" text-anchor="middle" font-size="11" font-weight="600" fill="#0C2340" font-family="Arial">${lbl}</text>`;
  });
  bars += `<text x="${pad.l+innerW/2}" y="${h-8}" text-anchor="middle" font-size="10.5" fill="#566778" font-family="Arial">Número de vezes que o médico foi visitado em ${labelQ}</text>`;
  document.getElementById('freq-medico-chart').innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
      ${grid}${bars}
    </svg>
    <div style="font-size:11px;color:var(--ink3);margin-top:6px;line-height:1.5;">
      <strong>0×</strong> = médicos do painel oficial do ${labelQ} NÃO visitados no período (lacuna de cobertura).
      <strong>1× a 6×</strong> = médicos visitados N vezes.
      <strong>7+</strong> = relacionamento forte.
    </div>`;
}

// Baixar CSV de médicos NÃO visitados (painel - visitados) no quarter selecionado
// ============================================================================
// MÉDICOS DO PAINEL SEM VISITA HÁ 60+ DIAS
// ============================================================================
function calcParadosConsultor(c){
  // Painel oficial atual (snapshot mais recente) vs visitados últimos 3m
  const painel = new Set(c.mdms_painel || []);
  const vis3m = new Set(c.mdms_visitados_3m || []);
  const parados = [];
  painel.forEach(m=>{ if(!vis3m.has(m)) parados.push(m); });
  return parados;
}

function renderMedicosParados(cs){
  const tbody = document.querySelector('#tbl-medicos-parados tbody');
  if(!tbody) return;
  // FILTROS DE QUALIDADE — evitar falsos outliers
  // 1. Excluir consultores com <3 snapshots de painel (cadastro muito novo)
  // 2. Excluir consultores com <50% overlap com painel de ~90d atrás (mudança de território)
  const excluidos = [];
  const csValidos = cs.filter(c=>{
    const painelN = (c.mdms_painel || []).length;
    if(painelN === 0) return false;  // sem painel
    const nSnaps = c.n_snapshots_historico || 0;
    const overlap = c.painel_overlap_90d_pct;
    if(nSnaps < 3){
      excluidos.push({nome:c.nome, motivo:'painel recém-cadastrado (<3 snapshots)'});
      return false;
    }
    if(overlap !== null && overlap !== undefined && overlap < 50){
      excluidos.push({nome:c.nome, motivo:'painel trocou recentemente (overlap '+Math.round(overlap)+'%)'});
      return false;
    }
    return true;
  });

  // KPIs
  let totParadosAgg = 0;
  let totPainelAgg = 0;
  const linhas = csValidos.map(c=>{
    const parados = calcParadosConsultor(c);
    const painelN = (c.mdms_painel || []).length;
    const vis3mN = (c.mdms_visitados_3m || []).length;
    const pct = painelN > 0 ? Math.round(parados.length / painelN * 100) : 0;
    totParadosAgg += parados.length;
    totPainelAgg += painelN;
    return {c, parados:parados.length, painelN, vis3mN, pct};
  }).sort((a,b)=>b.parados - a.parados);

  // Mediana e faixas
  const pcts = linhas.map(l=>l.pct).sort((a,b)=>a-b);
  const mediana = pcts.length ? pcts[Math.floor(pcts.length/2)] : 0;
  const baixo = linhas.filter(l=>l.pct < 15).length;
  const medio = linhas.filter(l=>l.pct >= 15 && l.pct < 30).length;
  const alto = linhas.filter(l=>l.pct >= 30).length;

  // Cards
  document.getElementById('kpi-medicos-parados').innerHTML = `
    <div class="card accent-teal">
      <div class="card-title">Caso típico (mediana)</div>
      <div class="card-num">${mediana}%</div>
      <div class="card-sub">do painel parado · metade dos consultores está abaixo deste valor</div>
    </div>
    <div class="card accent-purple">
      <div class="card-title">Saudável vs Atenção vs Crítico</div>
      <div class="card-num" style="font-size:18px;line-height:1.2;">
        <span style="color:var(--teal);">${baixo}</span> ·
        <span style="color:var(--warn);">${medio}</span> ·
        <span style="color:var(--danger);">${alto}</span>
      </div>
      <div class="card-sub">
        <span style="color:var(--teal);font-weight:700;">verde</span> &lt;15% parado ·
        <span style="color:var(--warn);font-weight:700;">amarelo</span> 15-30% ·
        <span style="color:var(--danger);font-weight:700;">vermelho</span> ≥30%
      </div>
    </div>
    <div class="card accent-warn">
      <div class="card-title">Total absoluto (médicos)</div>
      <div class="card-num">${fmt(totParadosAgg)}</div>
      <div class="card-sub">soma dos ${linhas.length} consultores com painel estável · painel total: ${fmt(totPainelAgg)} méd.</div>
    </div>`;

  // Bloco informativo de exclusões (quando tiver)
  let blocoExcluidos = '';
  if(excluidos.length > 0){
    blocoExcluidos = `
      <div style="background:#F4F8FB;border-left:3px solid #6B3FA0;padding:10px 14px;margin-bottom:12px;font-size:11.5px;color:var(--ink2);line-height:1.5;">
        <strong style="color:var(--purple);">${excluidos.length} consultor(es) excluído(s) desta análise</strong> por mudança recente de painel ou cadastro novo (não é possível medir "parados" com histórico insuficiente):
        <div style="margin-top:5px;font-size:10.5px;color:var(--ink3);">
          ${excluidos.map(e=>'• <strong>'+escapeHtml(e.nome)+'</strong> — '+e.motivo).join('<br>')}
        </div>
      </div>`;
  }
  // Inserir bloco de exclusões antes da tabela
  const elTabWrap = document.querySelector('#tbl-medicos-parados').closest('.tab-wrap');
  if(elTabWrap){
    let elInfo = document.getElementById('parados-excluidos-info');
    if(!elInfo){
      elInfo = document.createElement('div');
      elInfo.id = 'parados-excluidos-info';
      elTabWrap.parentNode.insertBefore(elInfo, elTabWrap);
    }
    elInfo.innerHTML = blocoExcluidos;
  }

  // Tabela
  tbody.innerHTML = linhas.map(l=>{
    const corPct = l.pct >= 30 ? 'var(--danger)' : l.pct >= 15 ? 'var(--warn)' : 'var(--teal)';
    const corParados = l.parados >= 20 ? 'var(--danger)' : l.parados >= 10 ? 'var(--warn)' : 'var(--ink2)';
    return `
    <tr>
      <td class="nm">${escapeHtml(l.c.nome)}</td>
      <td>${escapeHtml(l.c.sales_force||'')}</td>
      <td>${escapeHtml(l.c.gd_name||'—')}</td>
      <td class="num">${fmt(l.painelN)}</td>
      <td class="num">${fmt(l.vis3mN)}</td>
      <td class="num" style="color:${corParados};font-weight:700;">${fmt(l.parados)}</td>
      <td class="num" style="color:${corPct};font-weight:700;">${l.pct}%</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--ink3);padding:14px;">Sem dados.</td></tr>';
}

function exportMedicosParados(){
  const cs = getFilteredAtivos();
  const rows = [];
  cs.forEach(c=>{
    const painelN = (c.mdms_painel || []).length;
    if(painelN === 0) return;
    const parados = calcParadosConsultor(c);
    const nSnaps = c.n_snapshots_historico || 0;
    const overlap = c.painel_overlap_90d_pct;
    let qualidade = 'OK';
    if(nSnaps < 3) qualidade = 'painel novo — descartar';
    else if(overlap !== null && overlap !== undefined && overlap < 50) qualidade = 'painel trocou — descartar';
    if(parados.length === 0 && qualidade === 'OK') return;
    if(parados.length > 0){
      parados.forEach(m=>{
        const meta = mdMeta(m);
        rows.push([c.nome, c.sales_force, c.gd_name, m, meta.nome||'', meta.crm||'', (meta.especialidade||'').replace('_BR',''), qualidade]);
      });
    }
  });
  downloadCsv('medicos_parados_60d.csv',
    ['Consultor','SF','GD','MDM','Nome médico','CRM','Especialidade','Qualidade do painel'],
    rows);
}

// ============================================================================
// TOP MÉDICOS FORA DO PAINEL — candidatos a adicionar
// ============================================================================
function calcTopMedicosForaPainel(cs){
  // Para cada MDM visitado por algum consultor, ver se ele está no painel de ALGUÉM
  // Se NÃO está no painel de ninguém, contabilizar quantos consultores visitam
  const painelGlobal = new Set();
  cs.forEach(c=>(c.mdms_painel||[]).forEach(m=>painelGlobal.add(m)));

  // Mapa ISID → nome (pra exportar quem está visitando)
  const isidToNome = {};
  cs.forEach(c=>{ isidToNome[c.ISID] = c.nome; });

  // Mapa MDM -> {visitas_total, consultores_set, sfs_set}
  const mapa = {};
  cs.forEach(c=>{
    const visMat = c.mdms_visitados_mat || [];
    visMat.forEach(m=>{
      if(painelGlobal.has(m)) return;  // está no painel de alguém → ignora
      if(!mapa[m]) mapa[m] = {mdm:m, visitas:0, consultores:new Set(), sfs:new Set()};
      mapa[m].consultores.add(c.ISID);
      if(c.sales_force) mapa[m].sfs.add(c.sales_force);
      // Visitas estimadas: usar contagem nos quarters do consultor (já é approximation)
      // Como não temos contagem direta por MDM, vamos contar +1 por consultor que visita
      mapa[m].visitas++;
    });
  });
  // Ordenar por nº de consultores que visitam (proxy de relevância), depois visitas
  return Object.values(mapa).map(r=>{
    const meta = mdMeta(r.mdm);
    return {
      mdm: r.mdm,
      nome: meta.nome || '',
      crm: meta.crm || '',
      especialidade: meta.especialidade || '',
      consultores_n: r.consultores.size,
      consultores_nomes: [...r.consultores].map(i=>isidToNome[i]||i).sort(),
      sfs: [...r.sfs].sort(),
      visitas_aprox: r.visitas,
    };
  }).sort((a,b)=>{
    if(b.consultores_n !== a.consultores_n) return b.consultores_n - a.consultores_n;
    return b.visitas_aprox - a.visitas_aprox;
  });
}

function renderMedicosForaPainel(cs){
  const tbody = document.querySelector('#tbl-medicos-fora-painel tbody');
  if(!tbody) return;
  const ranking = calcTopMedicosForaPainel(cs).slice(0, 50);  // top 50 na tela
  if(!ranking.length){
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--ink3);padding:14px;">Nenhum médico visitado fora do painel.</td></tr>';
    return;
  }
  tbody.innerHTML = ranking.map((r,i)=>{
    const nsfs = r.sfs.length;
    const status = nsfs >= 3 ? '<span style="color:var(--danger);font-weight:700;">candidato forte</span>' :
                   nsfs === 2 ? '<span style="color:var(--warn);font-weight:700;">avaliar</span>' :
                   '<span style="color:var(--ink3);">caso isolado</span>';
    const sfsTxt = r.sfs.slice(0, 3).join(' · ') + (r.sfs.length > 3 ? ' (+' + (r.sfs.length-3) + ')' : '');
    // Célula do médico: Nome (CRM) + MDM em segunda linha (mais legível que só MDM)
    const mdmCell = (r.nome || r.crm)
      ? `<div style="font-weight:600;">${escapeHtml(r.nome || '—')}</div>
         <div style="font-size:10px;color:var(--ink3);">${r.crm ? 'CRM ' + escapeHtml(r.crm) + ' · ' : ''}MDM ${escapeHtml(r.mdm)}${r.especialidade ? ' · ' + escapeHtml(r.especialidade.replace('_BR','')) : ''}</div>`
      : escapeHtml(r.mdm);
    return `
    <tr>
      <td class="num" style="font-weight:700;color:var(--ink3);">${i+1}</td>
      <td>${mdmCell}</td>
      <td class="num">${r.visitas_aprox}</td>
      <td class="num" style="font-weight:700;">${r.consultores_n}</td>
      <td style="font-size:10.5px;">${escapeHtml(sfsTxt)}</td>
      <td>${status}</td>
    </tr>`;
  }).join('');
}

function exportMedicosForaPainel(){
  const cs = getFilteredAtivos();
  const ranking = calcTopMedicosForaPainel(cs);
  const rows = ranking.map((r,i)=>{
    const nsfs = r.sfs.length;
    const status = nsfs >= 3 ? 'candidato forte' : nsfs === 2 ? 'avaliar' : 'caso isolado';
    return [
      i+1,
      r.mdm,
      r.nome || '',
      r.crm || '',
      r.especialidade ? r.especialidade.replace('_BR','') : '',
      r.visitas_aprox,
      r.consultores_n,
      r.consultores_nomes.join(' | '),
      r.sfs.join(' | '),
      status
    ];
  });
  downloadCsv('medicos_fora_painel_top.csv',
    ['Ranking','MDM','Nome médico','CRM','Especialidade','Total visitas MAT','Nº consultores que visitam','Consultores (nomes)','SFs envolvidas','Status'],
    rows);
}

function exportNaoVisitados(){
  const cs = getFilteredAtivos();
  const q = getVisitQuarter();
  if(!q) return;
  // Por consultor: identificar médicos do painel_mdms que NÃO estão em mdms (do quarter)
  const rows = [];
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(!qc) return;
    const visited = new Set(qc.mdms || []);
    getPainelMdms(c, qc).forEach(m=>{
      if(!visited.has(m)){
        rows.push([c.nome, c.sales_force, c.gd_name, m, q.label, qc.painel_snapshot||'']);
      }
    });
  });
  downloadCsv('medicos_nao_visitados_'+q.label+'.csv',
    ['Consultor','Sales Force','GD','MDM (médico)','Quarter','Snapshot painel'],
    rows);
}

function exportFreqMedico(){
  const cs = getFilteredAtivos();
  const q = getVisitQuarter();
  if(!q) return;
  const allPainel = new Set();
  cs.forEach(c=>(c.mdms_painel||[]).forEach(m=>allPainel.add(m)));
  const visitadosQ = new Set();
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(qc) (qc.mdms||[]).forEach(m=>visitadosQ.add(m));
  });
  const naoVis = [...allPainel].filter(m=>!visitadosQ.has(m)).length;
  let b1=0, b2=0, b3=0, b4=0, b5=0, b6=0, b7p=0;
  cs.forEach(c=>{
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(!qc) return;
    b1+=qc.n_med_1x||0; b2+=qc.n_med_2x||0; b3+=qc.n_med_3x||0;
    b4+=qc.n_med_4x||0; b5+=qc.n_med_5x||0; b6+=qc.n_med_6x||0; b7p+=qc.n_med_7p||0;
  });
  const rows = [
    ['0× (painel não visitado)', naoVis],
    ['1×', b1], ['2×', b2], ['3×', b3], ['4×', b4],
    ['5×', b5], ['6×', b6], ['7+', b7p],
  ];
  downloadCsv('frequencia_visita_'+q.label+'.csv',
    ['Frequência de visita ('+q.label+')','Nº de médicos'], rows);
}

function exportVisitSF(){
  const cs = getFilteredAtivos();
  const q = getVisitQuarter();
  if(!q) return;
  const bySf = {};
  cs.forEach(c=>{
    const sf = c.sales_force || '—';
    if(!bySf[sf]) bySf[sf] = {sf, n:0, painel:new Set(), visitados:new Set()};
    bySf[sf].n++;
    (c.mdms_painel||[]).forEach(m=>bySf[sf].painel.add(m));
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    if(qc) (qc.mdms||[]).forEach(m=>bySf[sf].visitados.add(m));
  });
  const rows = Object.values(bySf).map(g=>{
    let dentro=0, fora=0;
    g.visitados.forEach(m=>{ if(g.painel.has(m)) dentro++; else fora++; });
    return [g.sf, g.n, g.painel.size, g.visitados.size, dentro, fora,
            g.painel.size>0?Math.round(dentro/g.painel.size*100):'',
            g.visitados.size>0?Math.round(fora/g.visitados.size*100):''];
  });
  downloadCsv('visitacao_sf_'+q.label+'.csv',
    ['Sales Force','Consultores','Painel total','Visitados ('+q.label+')','Dentro painel','Fora painel','% Cobertura','% Fora'],
    rows);
}

function exportVisitConsultor(){
  const cs = getFilteredAtivos();
  const q = getVisitQuarter();
  if(!q) return;
  const rows = cs.map(c=>{
    const pSet = new Set(c.mdms_painel||[]);
    const qc = (c.quarters||[]).find(x=>x.label===q.label);
    const vSet = new Set(qc ? (qc.mdms||[]) : []);
    let dentro=0, fora=0;
    vSet.forEach(m=>{ if(pSet.has(m)) dentro++; else fora++; });
    return [c.nome, c.sales_force, c.gd_name, pSet.size, vSet.size, dentro, fora,
            pSet.size>0?Math.round(dentro/pSet.size*100):'',
            vSet.size>0?Math.round(fora/vSet.size*100):''];
  });
  downloadCsv('visitacao_consultor_'+q.label+'.csv',
    ['Consultor','Sales Force','GD','Painel','Visitados ('+q.label+')','Dentro painel','Fora painel','% Cobertura','% Fora'],
    rows);
}

function exportMCCPMedicoMedico(){
  const cs = getFilteredAtivos().filter(c=>c.mccp_q_disponivel);
  const rows = [];
  cs.forEach(c=>{
    (c.mdms_dentro_mccp||[]).forEach(m=>{
      const meta = mdMeta(m);
      rows.push([c.nome, c.sales_force, c.gd_name, c.ciclo, m, meta.nome||'', meta.crm||'', (meta.especialidade||'').replace('_BR',''), 'Dentro MCCP']);
    });
    (c.mdms_fora_mccp||[]).forEach(m=>{
      const meta = mdMeta(m);
      rows.push([c.nome, c.sales_force, c.gd_name, c.ciclo, m, meta.nome||'', meta.crm||'', (meta.especialidade||'').replace('_BR',''), 'Fora MCCP']);
    });
  });
  downloadCsv('mccp_medico_a_medico.csv',
    ['Consultor','Sales Force','GD','Ciclo','MDM','Nome médico','CRM','Especialidade','Status'],
    rows);
}

function exportVisitMCCP(){
  const cs = getFilteredAtivos().filter(c=>c.mccp_q_disponivel && c.visitas_ciclo_total>0);
  const rows = cs.map(c=>[
    c.nome, c.sales_force, c.gd_name, c.ciclo,
    c.visitas_ciclo_total, c.visitas_dentro_mccp, c.visitas_fora_mccp,
    c.pct_dentro_mccp, c.pct_fora_mccp
  ]);
  downloadCsv('visitacao_mccp.csv',
    ['Consultor','Sales Force','GD','Ciclo','Visitas trimestre','Dentro MCCP','Fora MCCP','% Dentro','% Fora'],
    rows);
}


function downloadCsv(filename, headers, rows){
  const csvRows = [headers.join(';')].concat(rows.map(r=>r.map(v=>{
    if(v===null||v===undefined) return '';
    const s = String(v);
    return s.includes(';')||s.includes('"')||s.includes('\n') ? '"'+s.replace(/"/g,'""')+'"' : s;
  }).join(';')));
  const blob = new Blob(['\ufeff'+csvRows.join('\n')], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadHist(kind){
  const cs = getFilteredAtivos();
  if(kind==='painel'){
    const rows = cs.filter(c=>c.painel_size>0).map(c=>[c.nome, c.sales_force, c.gd_name, c.tipo_setor, c.painel_size]);
    downloadCsv('histograma_painel.csv', ['Consultor','Sales Force','GD','Setor','Painel'], rows);
  } else if(kind==='vis'){
    const rows = cs.filter(c=>c.vis_dia_media>0).map(c=>[c.nome, c.sales_force, c.gd_name, c.tipo_setor, c.vis_dia_media]);
    downloadCsv('histograma_visdia.csv', ['Consultor','Sales Force','GD','Setor','Vis/dia MAT'], rows);
  }
}

function exportAbsKpis(){
  const cs = getFilteredAtivos();
  const meanKey = k => {
    const vs = cs.map(c=>c[k]).filter(v=>v!==null && v!==undefined);
    return vs.length? mean(vs) : 0;
  };
  const rows = [
    ['Tempo fora do campo (% MAT)', (meanKey('pct_ausencia')).toFixed(1)+'%'],
    ['Dias em campo / mês', meanKey('dias_trabalhados_mes').toFixed(1)],
    ['Tempo fora total / mês', meanKey('ausencia_mes').toFixed(1)],
    ['Viagem / mês', meanKey('viagem_mes').toFixed(1)],
    ['Reunião/escritório / mês', meanKey('reunioes_mes').toFixed(1)],
    ['Congresso / mês', meanKey('congressos_mes').toFixed(1)],
    ['Treinamento / mês', meanKey('treinamento_mes').toFixed(1)],
    ['Gestão de território / mês', meanKey('gestao_mes').toFixed(1)],
    ['Pessoais / mês', meanKey('pessoais_mes').toFixed(2)],
  ];
  downloadCsv('ausencias_kpis.csv', ['Indicador','Valor (média do recorte)'], rows);
}

// ============================================================================
// BOOT — chamado depois do payload decodificar (gzip + base64)
// ============================================================================
function boot(){
  // Esconder o banner de "abra no navegador" — só aparece quando JS não roda
  const banner = document.getElementById('preview-warning');
  if(banner) banner.style.display = 'none';

  fillMeta();
  fillFilters();
  initSimInputs();
  setPairFilter('all');
  document.querySelectorAll('#tab-toggle button').forEach(b=>{
    b.addEventListener('click', ()=>setTab(b.dataset.tab));
  });
  installFloatingTooltip();
  // Sort universal (DOM-based) é aplicado dentro de renderAll() em todas as tabelas
  renderAll();
}

// Tooltip flutuante — renderiza no body, escapa overflow:auto do .tab-wrap
function installFloatingTooltip(){
  let tipEl = document.getElementById('floating-tooltip');
  if(!tipEl){
    tipEl = document.createElement('div');
    tipEl.id = 'floating-tooltip';
    document.body.appendChild(tipEl);
  }
  document.addEventListener('mouseover', e=>{
    const t = e.target.closest && e.target.closest('.tip');
    if(!t || !t.dataset.tip) return;
    tipEl.textContent = t.dataset.tip;
    tipEl.style.display = 'block';
    const rect = t.getBoundingClientRect();
    const tipRect = tipEl.getBoundingClientRect();
    const margin = 8;
    let top = rect.top - tipRect.height - margin;
    if(top < 4){ top = rect.bottom + margin; }
    let left = rect.left + rect.width/2 - tipRect.width/2;
    if(left < 4) left = 4;
    if(left + tipRect.width > window.innerWidth - 4) left = window.innerWidth - tipRect.width - 4;
    tipEl.style.top = top + 'px';
    tipEl.style.left = left + 'px';
  });
  document.addEventListener('mouseout', e=>{
    if(e.target.closest && e.target.closest('.tip')) tipEl.style.display = 'none';
  });
  // Esconder no scroll (evita tooltip "voador")
  document.addEventListener('scroll', ()=>{ tipEl.style.display='none'; }, true);
}
</script>
</body>
</html>
"""

HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Healthcheck — MSD</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
""" + CSS + """
</style>
</head>
"""


def main():
    payload_path = BUILD / "payload.json"
    if not payload_path.exists():
        raise FileNotFoundError("payload.json não encontrado. Rode processar.py primeiro.")
    payload_str = payload_path.read_text(encoding="utf-8")

    # Comprimir o payload com gzip + base64 (reduz ~5×) — evita truncamento em
    # clientes como WhatsApp/iOS Quick Look que limitam tamanho ou interpretam
    # mal arquivos HTML grandes.
    import gzip, base64
    payload_bytes = payload_str.encode("utf-8")
    payload_gz = gzip.compress(payload_bytes, compresslevel=9)
    payload_b64 = base64.b64encode(payload_gz).decode("ascii")
    print(f"  Payload original:    {len(payload_bytes)/1024/1024:.2f} MB")
    print(f"  Após gzip + base64:  {len(payload_b64)/1024/1024:.2f} MB")

    # Injeta payload comprimido no SCRIPT (BODY não tem placeholder)
    html = HEAD + BODY + SCRIPT.replace("__DADOS_B64__", payload_b64)

    bu = "BU"
    try:
        import json as _j
        bu = _j.loads(payload_str).get("meta", {}).get("bu", "BU")
    except Exception:
        pass
    out_path = OUT / f"Healthcheck_{bu}.html"
    out_path.write_text(html, encoding="utf-8")
    mb = out_path.stat().st_size / 1024 / 1024
    print(f"✓ {out_path}  ({mb:.2f} MB)")


if __name__ == "__main__":
    main()
