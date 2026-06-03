from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import (
    HTML_OUTPUT_PATH,
    LEGACY_ARCHIVE_PATH,
    LEGACY_PROJECT_DIR,
    OUTPUT_DIR,
    PAYLOAD_PATH,
    resolve_bases_dir,
)
from frontend.html_builder import gerar_html
from processing.legacy_integration import rodar_processamento_legado
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
        "--source-mode",
        choices=["auto", "legacy", "heuristic"],
        default="auto",
        help=(
            "Seleciona a origem do processamento: legacy usa o processar.py real extraido do 7z; "
            "heuristic usa a pipeline nova baseada em inferencia; auto prioriza legacy quando disponivel."
        ),
    )
    parser.add_argument(
        "--legacy-project-dir",
        default=str(LEGACY_PROJECT_DIR),
        help="Diretorio do projeto legado extraido.",
    )
    parser.add_argument(
        "--legacy-archive",
        default=str(LEGACY_ARCHIVE_PATH),
        help="Caminho do arquivo .7z com o projeto legado.",
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


def _should_use_legacy(args: argparse.Namespace) -> bool:
    if args.source_mode == "legacy":
        return True
    if args.source_mode == "heuristic":
        return False
    return Path(args.legacy_project_dir).exists() or Path(args.legacy_archive).exists()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    bases_dir = resolve_bases_dir(args.bases_dir)
    payload: dict
    runtime = {"source_mode": "skip", "bases_dir": str(bases_dir)}

    if not args.skip_processar:
        if _should_use_legacy(args):
            payload, runtime = rodar_processamento_legado(
                custom_bases_dir=bases_dir if bases_dir.exists() else None,
                project_dir=Path(args.legacy_project_dir),
                archive_path=Path(args.legacy_archive),
            )
        else:
            payload = rodar_processamento(bases_dir)
            runtime = {"source_mode": "heuristic", "bases_dir": str(bases_dir)}
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
    print(f"Modo: {runtime.get('source_mode', args.source_mode)}")
    print(f"Bases: {runtime.get('bases_dir', bases_dir)}")
    if runtime.get("legacy_payload_path"):
        print(f"Payload legado: {runtime['legacy_payload_path']}")
    print(f"Payload portal: {PAYLOAD_PATH}")
    print(f"HTML: {HTML_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
