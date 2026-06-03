# bases_healtcheck

Portal analitico offline para transformar bases CSV em um HTML self-contained do Healthcheck Operacional.

## O que esta entrega faz

- le todos os CSVs de uma pasta local;
- identifica bases candidatas de painel, visitas e ausencias por heuristica de nome/coluna;
- consolida indicadores em um payload modular;
- gera um `payload.json`;
- gera um `Healthcheck_BU.html` navegavel e compartilhavel;
- entrega Home, breadcrumb, filtros globais e 15 macrosecoes configuradas por registry.

## Estrutura do projeto

```text
.
├── config.py
├── main.py
├── requirements.txt
├── processing/
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
│   ├── page_registry.py
│   └── html_builder.py
└── output/
    ├── payload.json
    ├── Healthcheck_BU.html
    └── audit/
```

## Como rodar

### 1. Instalar dependencia

```bash
python -m pip install -r requirements.txt
```

### 2. Rodar tudo

Por padrao, o projeto tenta usar primeiro:

```text
C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases
```

Se esse caminho existir na sua maquina, basta rodar:

```bash
python main.py
```

### 3. Rodar com pasta customizada

```bash
python main.py --bases-dir "C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases"
```

### 4. Reprocessar apenas parte do fluxo

```bash
python main.py --skip-html
python main.py --skip-processar
```

## Saidas

Os artefatos sao gerados em `output/`:

- `output/payload.json`
- `output/Healthcheck_BU.html`
- `output/audit/warnings.json`

## Arquitetura implementada

O projeto foi montado com a separacao:

```text
bases CSV
  -> processing/*
  -> payload modular
  -> frontend/page_registry.py
  -> frontend/html_builder.py
  -> HTML self-contained
```

### Contrato do payload

```json
{
  "meta": {},
  "dimensions": {
    "consultores": [],
    "sales_forces": [],
    "gds": [],
    "windows": []
  },
  "analytics": {
    "consultor_window": [],
    "monthly_series": [],
    "overlap_pairs": [],
    "opportunity_doctors": [],
    "specialty_franchise": []
  },
  "sections": {},
  "audit": {}
}
```

## 15 macrosecoes entregues no portal

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
13. Canais e Mix Omnichannel
14. Cadastro e Master Data
15. Tendencias e Sazonalidade

## O que esta primeira versao preserva

- execucao unica via `python main.py`;
- HTML final em arquivo unico;
- filtros globais;
- estrutura escalavel por configuracao;
- separacao entre processamento e visualizacao.

## O que fica preparado para a proxima fase

- trocar heuristicas por regras de negocio finais de MCCP/painel/overlap;
- adicionar calculos detalhados por especialidade x franquia;
- incluir exports adicionais por secao;
- enriquecer insights automaticos;
- criar paginas mais especificas com menor dependencia de blocos genericos.
