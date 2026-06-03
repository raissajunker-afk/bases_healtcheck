from __future__ import annotations

import json
from pathlib import Path

from config import AUDIT_DIR, PAYLOAD_PATH
from processing.ausencias import processar_ausencias
from processing.cobertura import calcular_cobertura
from processing.indices import calcular_indices
from processing.load_sources import carregar_bases
from processing.overlap import calcular_overlap
from processing.painel import processar_painel
from processing.payload_builder import montar_payload
from processing.territorio import calcular_territorio
from processing.visitas import processar_visitas


def rodar_processamento(bases_dir: Path) -> dict:
    print("1/8 Carregando bases...")
    bases = carregar_bases(bases_dir)

    print("2/8 Processando painel...")
    painel = processar_painel(bases)

    print("3/8 Processando visitas...")
    visitas = processar_visitas(bases, painel)

    print("4/8 Processando ausencias...")
    ausencias = processar_ausencias(bases)

    print("5/8 Calculando cobertura...")
    cobertura = calcular_cobertura(bases, painel, visitas)

    print("6/8 Calculando territorio...")
    territorio = calcular_territorio(bases, visitas, painel)

    print("7/8 Calculando overlap e indices...")
    overlap = calcular_overlap(bases, visitas, painel)
    indices = calcular_indices(
        painel=painel,
        visitas=visitas,
        ausencias=ausencias,
        cobertura=cobertura,
        territorio=territorio,
        overlap=overlap,
    )

    print("8/8 Montando payload...")
    payload = montar_payload(
        bases=bases,
        painel=painel,
        visitas=visitas,
        ausencias=ausencias,
        cobertura=cobertura,
        territorio=territorio,
        overlap=overlap,
        indices=indices,
    )

    payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))

    PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOAD_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (AUDIT_DIR / "warnings.json").write_text(
        json.dumps(payload["meta"].get("warnings", []), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
