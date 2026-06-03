# bases_healtcheck

Portal Analítico Modular do **Healthcheck Operacional** (pharma/SFE).

Pipeline offline em Python que lê as bases em CSV e gera um **portal analítico
HTML self-contained** (arquivo único, abre em qualquer navegador, sem internet).

➡️ O projeto vive em [`healthcheck/`](healthcheck/). Veja
[`healthcheck/README.md`](healthcheck/README.md) para instruções completas.

## Início rápido

```bash
cd healthcheck
python main.py --demo   # gera bases de exemplo e o portal em output/Healthcheck_BU.html
```

Para usar suas bases reais, coloque os CSVs em `healthcheck/bases/` (ou aponte
com `--bases "C:\caminho\bases"`) e rode `python main.py`.
