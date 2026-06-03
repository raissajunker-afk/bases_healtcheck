# Healthcheck Operacional — Portal Analítico Modular

Transforma o Healthcheck Operacional (MSD Oncologia) de um *dashboard único com
muitas abas* em um **portal analítico modular**, **sem alterar nenhuma regra de
negócio**: o motor de cálculo continua sendo o `processar.py` original.

```
bases CSV ──(processar.py: regras reais)──> payload.json
          ──(portal/adapter.py)──────────> payload modular
          ──(frontend/html_builder.py)───> Healthcheck_Portal.html  (self-contained)
```

O resultado é um **único arquivo HTML offline** (abre em qualquer navegador, sem
internet), com navegação **Home → Macro Seção → Sub Seção → Página Analítica**,
filtros globais (GD, Sales Force, Consultor, Janela) e componentes reutilizáveis.

## Como rodar

O `processar.py` requer `pandas`, `numpy`, `openpyxl` (como no projeto original).
O portal em si (adapter + HTML) usa só a biblioteca padrão.

```bash
pip install pandas numpy openpyxl   # apenas para o processar.py

python main.py                  # roda tudo: processar.py + portal + HTML
python main.py --skip-processar # refaz só o portal/HTML usando payload.json existente
python main.py --skip-html      # roda só o processar.py (gera payload.json)
python main.py --bases "C:\...\bases"   # aponta a pasta de bases
```

Saídas em `output/`:
- `Healthcheck_Portal.html` — **o portal** (abra no navegador / compartilhe)
- `payload.json` — payload real gerado pelo `processar.py`
- `portal_payload.json` — payload modular adaptado para o portal
- `audit/` — `processar_log.txt`, `dedup_audit.csv`, `tipo_setor_audit.csv`

### Bases (input)

Caminho resolvido por: `HEALTHCHECK_BASES` → caminho corporativo (OneDrive, em
`config.py`) → `./bases`. As bases esperadas pelo `processar.py` são as mesmas do
projeto original:

```
estrutura.xlsx · ausencias_de_campo_visao_geral.csv
relatorio_visitas_24.csv · relatorio_visitas_25.csv · relatorio_visitas_26.csv
relatorio_mccp.csv · relatorio_painel.csv · relatorio_brickagem.csv · relatorio_1030.csv
excecoes_trocas_sf.csv · excecoes_trocas_gd.csv · MM_AAAA-ESTRUTURA-FV.csv (histórico)
```

> As bases (≈270 MB) **não são versionadas** no git. Coloque-as em `healthcheck/bases/`
> ou aponte com `--bases`.

## Arquitetura

```
healthcheck/
├── main.py                # orquestrador único (--skip-processar / --skip-html / --bases)
├── config.py              # caminhos, janelas (sufixos), benchmarks (semáforo)
├── processar.py           # MOTOR REAL (regras de negócio originais — intocado)
├── gerar_html_legado.py   # gerador de HTML original (referência)
├── portal/
│   ├── adapter.py         # payload real -> datasets/summaries/dimensions do portal
│   ├── registry.py        # 15 macro seções × sub seções × páginas × blocos (campos reais)
│   └── pipeline.py        # roda processar.py, adapta e prepara o portal
├── frontend/
│   ├── template.html  html_builder.py
│   ├── css/{base,layout,components,pages}.css
│   └── js/{state,filters,aggregate,registry,router,app}.js + js/components/*
└── output/                # payload.json + Healthcheck_Portal.html + audit/
```

- **Registry central** (`portal/registry.py`): única fonte de verdade da navegação.
  Cada bloco é declarado por configuração e resolvido contra os campos **reais**
  do payload (`pctCoberturaF2F`, `mccp_pct_cumprido`, `pct_ausencia`, `ipt`,
  `score_territorio`, `pct_visitas_uf_sede`, `pct_overlap_intra`, ...). Adicionar
  uma página = adicionar um dicionário; nenhum JS novo é necessário.
- **Filtros globais centralizados**: GD, Sales Force, Consultor e **Janela**
  (MAT 12m / 3m / mês fechado / parcial). A janela troca automaticamente o sufixo
  do campo (`_mat`/`_3m`/`_1m`/`_parcial`) quando a variante existe no payload.
- **Componentes reutilizáveis**: `kpi`, `table`, `ranking`, `chart` (line/bar/
  donut), `insight`, `export` (CSV), `simulator`, `methodology`, `audit`.
- **HTML self-contained**: `html_builder.py` inlina CSS, JS e o payload em um
  único arquivo, preservando a facilidade de distribuição do projeto original.

## As 15 macro seções

1. Executive Overview · 2. Performance Comercial · 3. Cobertura e Painel ·
4. Visitação e Frequência · 5. Eficiência Territorial · 6. Ausências e Capacidade ·
7. Especialidades e Cadastro · 8. Qualidade de Execução (MCCP/IPA/IPT) ·
9. Overlap e Conflitos · 10. Multicanal e Engajamento · 11. Benchmark e Metas ·
12. Simulador e Planejamento · 13. Oportunidades e Plano de Ação ·
14. Saúde dos Dados · 15. Governança e Auditoria

## Regras de negócio (preservadas do `processar.py`)

- ICP-F2F = HCPs alvo com ≥1 interação F2F / HCPs alvo × 100.
- ICP-Multi = HCPs alvo com ≥1 canal qualquer / HCPs alvo × 100.
- HCP alvo = painel (snapshot ≤ mês fechado) ∩ MCCP (meta>0 no quarter).
- MCCP % cumprido = realizado / meta do trimestre × 100.
- Deduplicação de ausências (TOT), exclusão de SFs e tratamento de afastados
  seguem **exatamente** o `processar.py` — este portal não recalcula nada.
