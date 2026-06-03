# bases_healtcheck

Portal Analítico Modular do **Healthcheck Operacional** (MSD Oncologia).

O projeto lê as bases reais em CSV, aplica as **regras de negócio do
`processar.py` original** (deduplicação, exclusões, cobertura ICP-F2F/Multi,
MCCP, IPT, território, overlap) e gera um **portal analítico HTML
self-contained** (arquivo único, offline, fácil de compartilhar) com navegação
Home → Macro Seção → Sub Seção → Página.

➡️ O projeto vive em [`healthcheck/`](healthcheck/). Veja
[`healthcheck/README.md`](healthcheck/README.md) para instruções completas.

O portal gerado (com os dados reais) está em
[`healthcheck/dist/Healthcheck_Portal.html`](healthcheck/dist/Healthcheck_Portal.html).

## Início rápido

```bash
cd healthcheck
pip install pandas numpy openpyxl      # apenas para o processar.py
# coloque as bases em healthcheck/bases/ (ou use --bases "C:\...\bases")
python main.py
# saída: healthcheck/output/Healthcheck_Portal.html
```

> O fluxo é: `bases → processar.py (regras reais) → payload.json → adapter →
> portal HTML`. Nenhuma fórmula do `processar.py` foi alterada.
