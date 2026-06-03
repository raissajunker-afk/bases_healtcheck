"""Orquestrador único do Portal Analítico do Healthcheck.

Fluxo:
    bases CSV  --(processar.py: regras de negócio reais)-->  payload.json
              --(adapter)-->  payload modular  --(html_builder)-->  HTML self-contained

Operação simples (o usuário não precisa conhecer os módulos internos):

    python main.py                  # roda tudo (processar.py + portal + HTML)
    python main.py --skip-processar # refaz só o portal/HTML usando payload.json existente
    python main.py --skip-html      # roda só o processar.py (gera payload.json)
    python main.py --bases CAMINHO  # aponta para a pasta de bases

Requisitos do processar.py: pandas, numpy, openpyxl (como no projeto original).
O portal em si (adapter + HTML) usa apenas a biblioteca padrão.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from portal.pipeline import rodar_processar, construir_portal
from frontend.html_builder import gerar_html


def _tem_bases(bases_dir: Path) -> bool:
    if not bases_dir.exists():
        return False
    nomes = [p.name.lower() for p in bases_dir.glob("*")]
    return any("relatorio_visitas" in n for n in nomes) or any("estrutura" in n for n in nomes)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Portal Analítico Healthcheck")
    parser.add_argument("--skip-processar", action="store_true", help="Refaz só o portal/HTML (usa payload.json existente)")
    parser.add_argument("--skip-html", action="store_true", help="Roda só o processar.py (gera payload.json)")
    parser.add_argument("--bases", type=str, default=None, help="Caminho da pasta de bases (CSV/xlsx)")
    args = parser.parse_args(argv)

    bases_dir = Path(args.bases) if args.bases else config.resolve_bases_dir()

    if not args.skip_processar:
        if not _tem_bases(bases_dir):
            print(f"[erro] Bases não encontradas em {bases_dir}.")
            print("       Aponte com --bases CAMINHO ou use --skip-processar para reaproveitar o payload.json existente.")
            if not config.PAYLOAD_PATH.exists():
                return 1
        else:
            rodar_processar(bases_dir)

    if not args.skip_html:
        portal_payload = construir_portal()
        print("Gerando HTML...")
        caminho = gerar_html(portal_payload)
        print(f"      HTML gerado em {caminho}")

    print("Concluido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
