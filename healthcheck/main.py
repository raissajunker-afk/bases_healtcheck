"""Orquestrador único do Healthcheck Operacional -> Portal Analítico.

Mesmo com a modularização interna, a operação é simples:

    python main.py                  # roda tudo (processamento + HTML)
    python main.py --skip-html      # refaz apenas o processamento / payload
    python main.py --skip-processar # refaz apenas o HTML usando payload existente
    python main.py --demo           # gera bases de exemplo se não houver bases reais
    python main.py --bases CAMINHO  # usa uma pasta de bases específica

O usuário final não precisa conhecer os módulos internos para executar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from processing.pipeline import rodar_processamento, carregar_payload
from frontend.html_builder import gerar_html


def _tem_bases(bases_dir: Path) -> bool:
    return bases_dir.exists() and any(bases_dir.glob("*.csv"))


def _tem_bases_de_dados(bases_dir: Path) -> bool:
    """Há bases de fato (visitas/ausências/painel), não só o template de config?"""
    if not bases_dir.exists():
        return False
    nomes = [p.name.lower() for p in bases_dir.glob("*.csv")]
    return any(("visita" in n or "ausenc" in n or "painel" in n or "estrutura" in n) for n in nomes)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Portal Analítico Healthcheck")
    parser.add_argument("--skip-processar", action="store_true", help="Refaz apenas o HTML usando payload.json existente")
    parser.add_argument("--skip-html", action="store_true", help="Refaz apenas o processamento/payload")
    parser.add_argument("--bases", type=str, default=None, help="Caminho da pasta de bases (CSV)")
    parser.add_argument("--demo", action="store_true", help="Gera bases de exemplo se não houver bases reais")
    args = parser.parse_args(argv)

    bases_dir = Path(args.bases) if args.bases else config.resolve_bases_dir()

    # Geração de dados de exemplo (opcional) para validar o portal offline.
    if args.demo and not _tem_bases_de_dados(bases_dir):
        from tools.gerar_dados_exemplo import gerar
        bases_dir = config.LOCAL_BASES
        print(f"--demo: gerando bases de exemplo em {bases_dir} ...")
        gerar(bases_dir)

    payload = None
    if not args.skip_processar:
        if not _tem_bases_de_dados(bases_dir):
            print(f"[aviso] Nenhuma base de dados (visitas/ausências/painel) encontrada em {bases_dir}.")
            print("        Use --demo para gerar bases de exemplo ou --bases para apontar a pasta correta.")
        payload = rodar_processamento(bases_dir=bases_dir)

    if not args.skip_html:
        if payload is None:
            payload = carregar_payload()
        print("Gerando HTML...")
        caminho = gerar_html(payload)
        print(f"      HTML gerado em {caminho}")

    print("Concluido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
