# Payload modular — Fase 2

## Compatibilidade

`payload.json` mantém **todas as chaves legadas na raiz** (`meta`, `kpis`, `consultores`, …) para `html (13).py` e o portal atual.

Nova chave:

```json
{
  "meta": { "...": "inalterado" },
  "kpis": { "...": "inalterado" },
  "consultores": [ "..." ],
  "portal": {
    "version": 2,
    "schema": "healthcheck.portal.v2",
    "dimensions": { },
    "sections": { },
    "pages": { },
    "audit": { },
    "insights_global": [ ]
  }
}
```

## `portal.dimensions`

| Campo | Conteúdo |
|-------|----------|
| `consultores` | Lista leve (ISID, nome, SF, GD, KPIs principais) |
| `sales_forces` | Cópia de `sales_forces` |
| `gds` | Cópia de `gds` |

## `portal.sections`

Uma entrada por macro-seção (`executive`, `performance`, `cobertura`, …):

- `summary` — KPIs agregados da seção
- `rankings` / `oportunidades` / `series` — quando aplicável
- `insights` — regras interpretativas (Fase 4 expande)
- `pages` — metadados de páginas da seção

## `portal.pages`

Registry plano: chave `sectionId.pageId` → pergunta de negócio, `legacyVista`, `legacyAnchor`.

## `portal.audit`

Fontes em `bases/`, arquivos esperados, regras de exclusão (de `meta`).

## Próxima fase (3)

Páginas do portal podem ler `DATA.portal.sections.*` para blocos nativos sem duplicar cálculo no JS.
