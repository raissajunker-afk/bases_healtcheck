# Healthcheck Operacional — Portal (a partir do projeto original)

Pipeline **offline**: lê as bases da pasta **`healthcheck/bases/`** (como no 7z), roda o **`processar.py` original** (regras de negócio intactas) e gera **`Healthcheck_Portal.html`** — o mesmo dashboard (`html (13).py`) com navegação tipo portal (15 seções).

## Uso no seu PC

```bash
pip install -r requirements.txt
python main.py
```

| Caminho | Padrão |
|---------|--------|
| **Bases (entrada)** | `C:\Users\delimajr\OneDrive - Merck Sharp & Dohme LLC\Desktop\PY\healthcheck\bases` |
| **Saída** | `...\healthcheck\Healthcheck_Portal.html` |

Todos os CSVs/Excel do 7z ficam em **`bases/`** (`relatorio_visitas_*.csv`, `ausencias_de_campo_visao_geral.csv`, `estrutura.xlsx`, `relatorio_painel.csv`, `relatorio_mccp.csv`, etc.). O `processar.py` usa `IN(arquivo)` → `BASES_DIR/arquivo`.

## Comandos

```bash
python main.py                    # processar + portal
python main.py --skip-processar   # só HTML (payload já existe)
python main.py --portal-only      # só regenera portal
python main.py --with-legacy      # também gera Healthcheck_* legado (barra de abas antiga)
python scripts/validate_portal.py # confere se o HTML tem dashboard original embutido
```

## O que mudou vs. tentativa anterior

- **Não** é um portal genérico novo: é o **`html (13).py` completo** (histogramas, simulador, overlap, exports CSV, glossário) + **Home / 15 seções / breadcrumb**.
- Cada página do portal chama `setTab('overview'|'detail'|...)` — a mesma aba que você já tinha.
- Configuração das seções: `app/config/sections.json` (campo `legacyVista` por página).

## Estrutura (conteúdo do 7z)

```text
healthcheck/
  processar.py          # lê healthcheck/bases/*
  html (13).py          # fonte do dashboard
  gerar_html_legacy.py  # cópia para import
  bases/                # TODAS as bases originais
main.py
frontend/portal_builder.py
```

Ver `ANALISE_CRITICA.md` para o que cada seção do portal abre no dashboard legado.
