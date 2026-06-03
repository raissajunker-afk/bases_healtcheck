from __future__ import annotations

import argparse
from pathlib import Path
import json

from config import build_config
from frontend.html_builder import gerar_html
from processing.pipeline import rodar_processamento


def main() -> None:
    parser = argparse.ArgumentParser(description="Orquestrador do Healthcheck Portal Analitico.")
    parser.add_argument(
        "--bases-dir",
        help="Diretorio com arquivos CSV. Se omitido, usa env HEALTHCHECK_BASES_DIR, caminho padrao Windows, ou ./bases.",
    )
    parser.add_argument("--skip-processar", action="store_true", help="Nao roda processamento; reutiliza payload existente.")
    parser.add_argument("--skip-html", action="store_true", help="Nao gera HTML final.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    config = build_config(project_root, args.bases_dir)

    payload = None
    if not args.skip_processar:
        payload = rodar_processamento(config)
    elif config.payload_path.exists():
        payload = json.loads(config.payload_path.read_text(encoding="utf-8"))
    else:
        raise FileNotFoundError(
            f"Voce usou --skip-processar, mas o payload nao existe em {config.payload_path}. "
            "Execute sem --skip-processar pelo menos uma vez."
        )

    if not args.skip_html:
        html_path = gerar_html(config, payload)
        print(f"HTML gerado em: {html_path}")

    print("Concluido.")


if __name__ == "__main__":
    main()
