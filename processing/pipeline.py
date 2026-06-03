from __future__ import annotations

from config import AppConfig
from processing.ausencias import processar_ausencias
from processing.cobertura import calcular_cobertura
from processing.indices import calcular_indices
from processing.load_sources import carregar_bases
from processing.overlap import calcular_overlap
from processing.painel import processar_painel
from processing.payload_builder import montar_payload, salvar_payload
from processing.territorio import calcular_territorio
from processing.visitas import processar_visitas


def rodar_processamento(config: AppConfig) -> dict:
    print("1/9 Carregando bases...")
    bases = carregar_bases(config.bases_dir)

    print("2/9 Processando painel...")
    painel = processar_painel(bases)

    print("3/9 Processando visitas...")
    visitas = processar_visitas(bases, painel)

    print("4/9 Processando ausencias...")
    ausencias = processar_ausencias(bases)

    print("5/9 Calculando cobertura...")
    cobertura = calcular_cobertura(bases, painel, visitas)

    print("6/9 Calculando territorio...")
    territorio = calcular_territorio(bases, visitas, painel)

    print("7/9 Calculando overlap...")
    overlap = calcular_overlap(bases, visitas, painel)

    print("8/9 Calculando indices finais...")
    indices = calcular_indices(
        painel=painel,
        visitas=visitas,
        ausencias=ausencias,
        cobertura=cobertura,
        territorio=territorio,
        overlap=overlap,
    )

    print("9/9 Montando payload modular...")
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
    salvar_payload(payload, config.payload_path)
    print(f"Payload salvo em: {config.payload_path}")
    return payload
