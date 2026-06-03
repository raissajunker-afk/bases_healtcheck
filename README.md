# Healthcheck Operacional — Portal Analítico

Pipeline **offline** em Python: lê as bases CSV/Excel, aplica as regras de negócio (`processar.py`) e gera um **HTML único** para abrir no navegador (sem servidor).

## Uso no seu computador

```bash
pip install -r requirements.txt
python main.py
```

**Bases (padrão):**  
`C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases`

**Saída (padrão):**  
`C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\Healthcheck_Portal.html`

### Comandos

| Comando | Efeito |
|---------|--------|
| `python main.py` | Processa bases + gera portal |
| `python main.py --skip-processar` | Só regenera HTML (usa `payload.json` existente) |
| `python main.py --skip-html` | Só processamento |
| `python main.py --with-legacy` | Também gera o dashboard antigo (6+ abas) |
| `python main.py --portal-only` | Só portal (sem reprocessar) |

### Variáveis de ambiente (opcional)

```bash
set HEALTHCHECK_BASES_PATH=C:\...\bases
set HEALTHCHECK_OUT_PATH=C:\...\healthcheck
```

## Estrutura

```text
main.py                 # Orquestrador
config.py               # Caminhos Windows + fallback
healthcheck/
  processar.py          # Regras de negócio (inalteradas)
  gerar_html_legacy.py  # Dashboard antigo (opcional)
  bases/                # CSVs locais / referência
frontend/
  html_builder.py       # Monta HTML self-contained
  css/portal.css
  js/portal-app.js
app/config/sections.json  # 15 macro-seções × 5 subseções
```

## Portal (15 seções)

Navegação: **Home → Macro seção → Subseção → Página** (até 8 blocos: KPIs, gráficos, tabelas, insights, metodologia, CSV).

Ver `ANALISE_CRITICA.md` para o que **não** duplicar do dashboard legado.

## Origem dos dados

O arquivo `healthcheck (3).7z` no repositório contém o projeto completo. Após extrair, use `healthcheck/bases` ou o caminho OneDrive acima.
