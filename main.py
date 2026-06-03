#!/usr/bin/env python3
"""
Orquestrador único do Healthcheck Operacional.

  python main.py                  # processar + portal (recomendado)
  python main.py --with-legacy      # também gera dashboard legado (6 abas)
  python main.py --skip-processar   # só HTML portal
  python main.py --skip-html      # só processar.py
  python main.py --legacy-only    # só dashboard legado (6 abas)
  python main.py --portal-only    # só portal modular
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import config

HEALTHCHECK = config.HEALTHCHECK_DIR


def _preparar_ambiente() -> None:
    """Garante que processar.py encontre bases e grave saídas no lugar certo."""
    os.chdir(HEALTHCHECK)
    sys.path.insert(0, str(HEALTHCHECK))
    sys.path.insert(0, str(config.PROJECT_ROOT))

    # Recarrega processar para aplicar caminhos (evita cache com BASES_DIR errado)
    if "processar" in sys.modules:
        del sys.modules["processar"]
    import processar  # noqa: E402

    bases = config.BASES_PATH.resolve()
    saida = config.OUT_PATH.resolve()
    processar.BASES_DIR = str(bases)
    processar.OUT_DIR = str(saida)
    processar._BASES_PREF = str(bases)
    processar._OUT_PREF = str(saida)
    print(f"  Bases: {bases}")
    print(f"  Saída: {saida}")


def rodar_processamento() -> None:
    print("=" * 60)
    print("1/3 Processamento (processar.py)")
    print("=" * 60)
    _preparar_ambiente()
    import processar

    processar.main()
    print(f"\n✓ payload: {config.PAYLOAD_PATH}\n")


def rodar_html_legado() -> None:
    print("=" * 60)
    print("2/3 Dashboard legado (6 abas)")
    print("=" * 60)
    _preparar_ambiente()
    import gerar_html_legacy

    gerar_html_legacy.main()
    print()


def rodar_portal() -> None:
    print("=" * 60)
    print("3/3 Portal analítico modular (15 seções)")
    print("=" * 60)
    if not config.PAYLOAD_PATH.exists():
        raise FileNotFoundError(
            f"payload.json não encontrado em {config.PAYLOAD_PATH}. Rode sem --skip-processar."
        )
    from frontend.html_builder import gerar_html

    gerar_html(
        payload_path=config.PAYLOAD_PATH,
        output_path=config.PORTAL_HTML_PATH,
    )
    print(f"✓ Portal: {config.PORTAL_HTML_PATH}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Healthcheck Operacional — pipeline completa")
    parser.add_argument("--skip-processar", action="store_true", help="Pula processar.py")
    parser.add_argument("--skip-html", action="store_true", help="Pula geração de HTML")
    parser.add_argument("--legacy-only", action="store_true", help="Só dashboard legado")
    parser.add_argument("--portal-only", action="store_true", help="Só portal modular")
    parser.add_argument("--with-legacy", action="store_true", help="Gera também o HTML legado completo")
    args = parser.parse_args()

    if not HEALTHCHECK.is_dir():
        raise SystemExit(f"Pasta healthcheck não encontrada: {HEALTHCHECK}")

    config.OUT_PATH.mkdir(parents=True, exist_ok=True)

    if not args.skip_processar and not args.portal_only:
        rodar_processamento()
    elif not config.PAYLOAD_PATH.exists():
        print(f"Aviso: {config.PAYLOAD_PATH} não existe. Use sem --skip-processar.")

    if args.skip_html:
        return

    if args.legacy_only:
        rodar_html_legado()
        return
    if args.portal_only:
        rodar_portal()
        return

    if args.with_legacy:
        rodar_html_legado()
    rodar_portal()
    print("=" * 60)
    print("Concluído.")
    if args.with_legacy:
        print(f"  Legado: {config.OUT_PATH}/Healthcheck_*.html")
    print(f"  Portal: {config.PORTAL_HTML_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
