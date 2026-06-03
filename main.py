from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import HTML_OUTPUT_PATH, OUTPUT_DIR, PAYLOAD_PATH, resolve_bases_dir
from frontend.html_builder import gerar_html
from processing.pipeline import rodar_processamento


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Portal analitico offline para o Healthcheck Operacional."
    )
    parser.add_argument(
        "--bases-dir",
        help="Diretorio das bases CSV. Se omitido, usa o caminho padrao configurado.",
    )
    parser.add_argument(
        "--skip-processar",
        action="store_true",
        help="Pula o processamento e reaproveita o payload.json existente.",
    )
    parser.add_argument(
        "--skip-html",
        action="store_true",
        help="Pula a geracao do HTML final.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    bases_dir = resolve_bases_dir(args.bases_dir)
    payload: dict

    if not args.skip_processar:
        payload = rodar_processamento(bases_dir)
    else:
        if not PAYLOAD_PATH.exists():
            raise FileNotFoundError(
                f"Arquivo de payload nao encontrado em {PAYLOAD_PATH}. "
                "Rode sem --skip-processar primeiro."
            )
        payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))

    if not args.skip_html:
        gerar_html(payload, output_path=HTML_OUTPUT_PATH)

    print("")
    print("Concluido.")
    print(f"Bases: {bases_dir}")
    print(f"Payload: {PAYLOAD_PATH}")
    print(f"HTML: {HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
