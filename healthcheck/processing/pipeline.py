"""Pipeline de processamento.

Encapsula a sequência de módulos de domínio e a escrita do payload.json.
Permite rodar o processamento isolado (sem regenerar o HTML).
"""

from __future__ import annotations

import json
from pathlib import Path

import config
from processing.load_sources import carregar_bases
from processing.painel import processar_painel
from processing.visitas import processar_visitas
from processing.ausencias import processar_ausencias
from processing.cobertura import calcular_cobertura
from processing.territorio import calcular_territorio
from processing.overlap import calcular_overlap
from processing.especialidades import calcular_especialidades
from processing.indices import calcular_indices
from processing.payload_builder import montar_payload


def rodar_processamento(bases_dir: Path | None = None, salvar: bool = True, verbose: bool = True) -> dict:
    def log(msg):
        if verbose:
            print(msg)

    log("1/9 Carregando bases...")
    bases = carregar_bases(bases_dir)
    log(f"      pasta: {bases['meta']['bases_dir']}")
    log(f"      arquivos: {bases['meta']['arquivos_encontrados'] or '(nenhum)'}")

    log("2/9 Processando painel...")
    painel = processar_painel(bases)

    log("3/9 Processando visitas...")
    visitas = processar_visitas(bases, painel)

    log("4/9 Processando ausencias...")
    ausencias = processar_ausencias(bases)

    log("5/9 Calculando cobertura...")
    cobertura = calcular_cobertura(bases, painel, visitas)

    log("6/9 Calculando territorio...")
    territorio = calcular_territorio(bases, visitas, painel)

    log("7/9 Calculando overlap...")
    overlap = calcular_overlap(bases, visitas, painel)

    log("    Calculando especialidades x franquias...")
    especialidades = calcular_especialidades(bases, painel, visitas, cobertura)

    log("8/9 Calculando indices...")
    indices = calcular_indices(
        painel=painel, visitas=visitas, ausencias=ausencias, cobertura=cobertura,
        territorio=territorio, overlap=overlap, especialidades=especialidades,
    )

    log("9/9 Montando payload...")
    payload = montar_payload(
        bases=bases, painel=painel, visitas=visitas, ausencias=ausencias,
        cobertura=cobertura, territorio=territorio, overlap=overlap,
        especialidades=especialidades, indices=indices,
    )

    if salvar:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        config.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        config.PAYLOAD_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        log(f"      payload salvo em {config.PAYLOAD_PATH}")

    return payload


def carregar_payload() -> dict:
    if not config.PAYLOAD_PATH.exists():
        raise FileNotFoundError(
            f"payload.json não encontrado em {config.PAYLOAD_PATH}. "
            "Rode o processamento primeiro (python main.py)."
        )
    return json.loads(config.PAYLOAD_PATH.read_text(encoding="utf-8"))
