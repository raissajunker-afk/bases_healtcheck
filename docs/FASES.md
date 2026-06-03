# Roadmap de fases

| Fase | Status | Entrega |
|------|--------|---------|
| **1** | Concluída | Portal = `html (13).py` + Home/15 seções/breadcrumb; `main.py`; bases em `healthcheck/bases/` |
| **2** | Concluída | `payload.portal` modular (`dimensions`, `sections`, `pages`, `audit`, `insights`); legado intacto na raiz |
| **3** | Próxima | Páginas com blocos nativos lendo `DATA.portal.sections.*` (sem só `setTab`) |
| **4** | Planejada | Camada de insights automáticos expandida |
| **5** | Planejada | Export executivo (CSV por seção, pacote liderança) |

## Fase 2 — como usar

Após `python main.py`, abra `payload.json` e consulte `portal`:

```python
import json
p = json.load(open("payload.json", encoding="utf-8"))
p["portal"]["sections"]["oportunidades"]["oportunidades"][:5]
```

Documentação: `docs/PAYLOAD_SCHEMA.md`
