# bases_healtcheck - Portal Analitico Modular

Este repositório foi estruturado para evoluir de um dashboard unico para um portal analitico modular, mantendo a entrega final em **HTML self-contained** para uso offline.

## 1) Diagnostico da arquitetura original (problema alvo)

O desenho original descrito no prompt (`processar.py -> payload.json -> html.py`) funciona para um dashboard unico, mas apresenta gargalos para escala:

- acoplamento forte entre processamento e visual;
- HTML monolitico com CSS, JS, layout e regras de filtro no mesmo arquivo;
- crescimento por abas hardcoded;
- payload amplo sem contrato por dominio;
- baixa reusabilidade de componentes;
- alto risco de regressao em cada nova pagina.

## 2) Arquitetura-alvo implementada (fase 1 com base para fase 2+)

Fluxo atual:

```text
main.py
  -> processing.pipeline.rodar_processamento()
  -> output/payload.json
  -> frontend.html_builder.gerar_html()
  -> output/Healthcheck_BU.html
```

Principios adotados:

- execucao unica para operacao (`python main.py`);
- modularizacao por dominio no processamento;
- payload modular com `meta`, `dimensions`, `sections`, `page_registry`, `audit`;
- registry central de paginas e blocos;
- componentes reutilizaveis no frontend;
- renderizacao por rota (Home -> Secao -> Pagina);
- filtros globais com estado unico;
- HTML final self-contained (sem dependencias externas obrigatorias).

## 3) Estrutura de pastas

```text
.
├── main.py
├── config.py
├── processing/
│   ├── __init__.py
│   ├── common.py
│   ├── load_sources.py
│   ├── painel.py
│   ├── visitas.py
│   ├── ausencias.py
│   ├── cobertura.py
│   ├── territorio.py
│   ├── overlap.py
│   ├── indices.py
│   ├── payload_builder.py
│   └── pipeline.py
├── frontend/
│   ├── __init__.py
│   ├── html_builder.py
│   ├── template.html
│   ├── css/
│   │   ├── base.css
│   │   ├── layout.css
│   │   ├── components.css
│   │   └── pages.css
│   └── js/
│       ├── state.js
│       ├── filters.js
│       ├── registry.js
│       ├── router.js
│       ├── components/
│       └── pages/
├── bases/
│   └── franquias_especialidades.csv
└── output/
```

## 4) Portal com 15 macrosecoes

O `config.py` declara 15 secoes com ate 5 subsecoes cada, incluindo:

1. Executive Overview  
2. Performance Comercial  
3. Cobertura e Painel  
4. Visitacao e Frequencia  
5. Eficiencia Territorial  
6. Ausencias e Capacidade  
7. Especialidades e Franquias  
8. Qualidade de Execucao  
9. Overlap e Conflitos  
10. Simulador e Planejamento  
11. Oportunidades e Plano de Acao  
12. Governanca e Auditoria  
13. Inteligencia de Mercado  
14. Experiencia Omnicanal  
15. Sustentacao Operacional

## 5) Modelo de payload modular

O payload gerado em `output/payload.json` segue:

```json
{
  "meta": {},
  "dimensions": {
    "consultores": [],
    "sales_forces": [],
    "gds": [],
    "medicos": []
  },
  "sections": {
    "executive_overview": {
      "summary": {},
      "pages": {
        "snapshot_executivo": {
          "cards": [],
          "charts": [],
          "tables": [],
          "insights": [],
          "exports": [],
          "methodology": []
        }
      }
    }
  },
  "page_registry": {},
  "audit": {}
}
```

## 6) PAGE_REGISTRY

Gerado automaticamente em `config.build_page_registry()`.

Cada pagina contem:

- `section`, `sectionId`, `subsection`, `pageId`;
- pergunta de negocio e decisao suportada;
- `dataPath` para localizar dados no payload;
- lista de `blocks` (ate 8 por pagina).

## 7) Componentes reutilizaveis

No frontend:

- `renderKpiCard`
- `renderChart`
- `renderTable`
- `renderInsight`
- `renderExportButton`

Todos consumidos por `router.js` para montar paginas por configuracao.

## 8) Estrategia de navegacao

- Home com cards de macrosecoes;
- clique em secao -> cards de subsecoes;
- clique em subsecao -> pagina analitica;
- breadcrumb dinamico;
- botao "Voltar para Home";
- filtros globais persistentes no `APP_STATE`.

## 9) Execucao offline

### Caminho das bases

Ordem de resolucao do diretorio de CSVs:

1. `--bases-dir` informado no comando
2. variavel de ambiente `HEALTHCHECK_BASES_DIR`
3. caminho Windows padrao:
   `C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases`
4. fallback local: `./bases`

### Comandos

```bash
python main.py                    # roda tudo: processamento + html
python main.py --skip-html        # roda so processamento/payload
python main.py --skip-processar   # roda so html usando payload existente
python main.py --bases-dir "C:\...\bases"
```

## 10) Riscos tecnicos e mitigacoes

- **Heterogeneidade de schema CSV**: leitura resiliente por aliases de colunas.
- **Ausencia de bases em ambiente limpo**: pipeline nao quebra; gera payload minimo auditavel.
- **Escala de paginas**: registry central evita hardcode por aba.
- **Regressao metodologica**: camada `audit` e secao `governanca_auditoria`.

## 11) Estrategia incremental recomendada

1. Estruturar portal modular (entregue nesta fase).
2. Migrar calculos legados para modulos por dominio sem alterar formula.
3. Popular novas paginas por reutilizacao de dados existentes.
4. Evoluir insights automaticos por regras.
5. Expandir exports executivos e trilha metodologica.

## 12) Observacoes sobre Especialidades x Franquias

- arquivo `bases/franquias_especialidades.csv` foi criado como contrato inicial;
- preparada a base para evoluir os indices `IAEF`, `ICEF`, `IFEF`, `IDEF`;
- tratamento `sem_classificacao` para especialidade ausente ja aplicado no processamento de painel.
