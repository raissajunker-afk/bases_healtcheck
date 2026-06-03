# Healthcheck Operacional — Portal Analítico Modular

Pipeline **offline** em Python (apenas biblioteca padrão) que lê as bases em
CSV e gera um **portal analítico self-contained** em HTML: um único arquivo que
abre em qualquer navegador, sem internet e sem dependências externas, pronto
para compartilhar por e-mail, Teams, SharePoint ou WhatsApp.

O projeto evoluiu de um *dashboard único com muitas abas* para um **portal
modular** com a hierarquia:

```
Home → Macro Seção → Sub Seção → Página Analítica → Blocos (KPI, tabela, gráfico, insight, export, metodologia)
```

São **15 macro seções**, cada uma com até 5 sub seções e cada página com até 8
blocos analíticos — uma infraestrutura que suporta centenas de blocos e cresce
**por configuração**, sem reescrever a aplicação.

---

## Como rodar

Requisito: **Python 3.10+** (nenhuma dependência externa — usa só a stdlib).

```bash
# 1) Coloque suas bases CSV na pasta de bases (veja "Bases" abaixo)
# 2) Rode tudo (processa + gera HTML):
python main.py

# Refazer apenas o HTML (payload já existe — ajuste visual rápido):
python main.py --skip-processar

# Refazer apenas o processamento/payload:
python main.py --skip-html

# Apontar para uma pasta de bases específica:
python main.py --bases "C:\caminho\para\bases"

# Gerar bases de exemplo (sintéticas) e validar o portal sem dados reais:
python main.py --demo
```

A saída fica em `output/`:

- `output/Healthcheck_BU.html` — **o portal** (abra no navegador)
- `output/payload.json` — payload modular gerado
- `output/audit/` — área reservada para artefatos de auditoria

### Onde ficam as bases

O caminho é resolvido nesta ordem:

1. variável de ambiente `HEALTHCHECK_BASES`;
2. caminho corporativo do usuário (configurado em `config.py`):
   `C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases`;
3. pasta local `./bases` do projeto.

---

## Bases esperadas

Todas são **opcionais** — o pipeline degrada com elegância e os blocos sem dado
mostram um estado vazio explicativo. A leitura é **tolerante** (detecta
delimitador `;`/`,`/tab, encoding, e mapeia sinônimos de colunas).

| Arquivo (prefixo)                    | Conteúdo                                            |
|--------------------------------------|-----------------------------------------------------|
| `relatorio_visitas_*.csv`            | Visitas (data, consultor, SF, GD, médico, canal, UF…) |
| `ausencias_*.csv`                    | Ausências (consultor, início, fim, dias, categoria) |
| `painel*.csv`                        | Snapshot de painel (médico × consultor, MCCP)        |
| `estrutura.csv` / `.xlsx`            | Hierarquia consultor/SF/GD, sede, tipo de setor, meta|
| `franquias_especialidades.csv`       | Mapa estratégico Especialidade × Franquia (config)   |

> Se não houver `painel*.csv`, o painel é **derivado das visitas**.

### `franquias_especialidades.csv` (configuração estratégica)

Formato (separador `;`):

```
franquia;especialidade;relevancia;peso;papel;observacao
GI;ONCOLOGIA CLINICA;alta;1.0;decisor;Especialidade central
```

Regras: especialidade **nunca** é hardcodada no código; uma especialidade pode
pertencer a mais de uma franquia; especialidade ausente vira `sem_classificacao`
(auditada). Um template já vem em `bases/franquias_especialidades.csv`.

---

## Arquitetura

```
Bases brutas (CSV)
   ↓  processing/load_sources.py        (leitura tolerante)
   ↓  processing/{painel,visitas,ausencias,cobertura,territorio,overlap,especialidades}.py
   ↓  processing/indices.py             (consolida métricas por consultor)
   ↓  processing/payload_builder.py     (payload modular: meta + dimensions + datasets + summaries + registry)
   ↓  frontend/html_builder.py          (template + css + js + payload → HTML único)
HTML final self-contained
```

- **Orquestrador único** (`main.py`): módulos separados para manutenção,
  execução única para operação.
- **Registry central** (`processing/registry.py`): única fonte de verdade da
  navegação. Adicionar uma página = adicionar um dicionário; o frontend monta a
  página por **componentes reutilizáveis** a partir da configuração dos blocos.
- **Payload modular** com `datasets` (linhas filtráveis) e `summaries`
  (agregados prontos). Os filtros globais (GD, SF, Consultor, Janela) são
  aplicados de forma **centralizada** — nenhuma página duplica lógica de filtro.

### Estrutura de pastas

```
healthcheck/
├── main.py                  # orquestrador (--skip-processar / --skip-html / --demo / --bases)
├── config.py                # caminhos, benchmarks, janelas, sinônimos de colunas
├── processing/
│   ├── load_sources.py  painel.py  visitas.py  ausencias.py
│   ├── cobertura.py  territorio.py  overlap.py  especialidades.py
│   ├── indices.py  registry.py  payload_builder.py  pipeline.py  util.py
├── frontend/
│   ├── template.html  html_builder.py
│   ├── css/{base,layout,components,pages}.css
│   └── js/{state,filters,aggregate,registry,router,app}.js + js/components/*
├── tools/gerar_dados_exemplo.py   # bases sintéticas para --demo
├── bases/                          # suas bases CSV (apenas o template é versionado)
└── output/                         # payload.json + Healthcheck_BU.html
```

---

## As 15 macro seções

1. Executive Overview
2. Performance Comercial
3. Cobertura e Painel
4. Visitação e Frequência
5. Eficiência Territorial
6. Ausências e Capacidade
7. Especialidades e Franquias *(camada estratégica: IAEF, ICEF, IFEF, IDEF, matriz, gaps)*
8. Qualidade de Execução
9. Overlap e Conflitos
10. Multicanal e Engajamento Digital
11. Benchmark e Metas
12. Simulador e Planejamento
13. Oportunidades e Plano de Ação
14. Saúde dos Dados
15. Governança e Auditoria

---

## Como adicionar uma nova página (sem escrever JS)

Edite `processing/registry.py` e adicione uma sub seção com `blocks`. Exemplo:

```python
{"id": "minha_pagina", "title": "Minha Página", "page": _page(
    "Cobertura e Painel", "cobertura", "Minha Página", "cob_minha",
    "Minha Página", "Qual pergunta de negócio?", "Qual decisão suporta?",
    [
        kpi("k1", "Cobertura F2F", "consultores", agg="ratio",
            num="hcp_coberto_f2f", den="hcp_alvo", fmt="percent", benchmark="pct_cobertura_f2f"),
        ranking("r1", "Ranking", "consultores", "consultor", "visitas"),
        export_block("e1", "Exportar", "consultores"),
    ])}
```

Tipos de bloco: `kpi`, `table`, `ranking`, `chart` (`line`/`bar`/`donut`/`heatmap`),
`insight`, `export`, `methodology`, `simulator`, `audit`, `empty`.

---

## Notas metodológicas

- Visitas deduplicadas por `(consultor, médico, data, canal)`.
- Cobertura F2F = médicos do painel com ≥1 visita presencial / painel.
- Cobertura MCCP = médicos MCCP com ≥1 visita F2F / médicos MCCP.
- `% ausência` = dias de ausência / dias úteis do período.
- Índices estratégicos (seção 7): IAEF (aderência), ICEF (cobertura),
  IFEF (frequência), IDEF (dispersão).

Benchmarks (semáforo) e fórmulas estão centralizados em `config.py` e na seção
**Governança e Auditoria** do próprio portal.
