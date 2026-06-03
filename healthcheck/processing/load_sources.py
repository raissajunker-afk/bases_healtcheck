"""Leitura das bases brutas.

Responsabilidade única: localizar e ler os arquivos de entrada, normalizando
cabeçalhos para nomes canônicos. NÃO calcula KPIs nem aplica regras de negócio.

As bases esperadas (todas opcionais; o pipeline degrada com elegância):
  - relatorio_visitas_*.csv  -> visitas
  - ausencias_*.csv          -> ausências
  - painel*.csv              -> snapshot de painel (médico x consultor)
  - estrutura.csv / .xlsx    -> hierarquia consultor/SF/GD + território
  - franquias_especialidades.csv -> mapa estratégico especialidade x franquia
"""

from __future__ import annotations

from pathlib import Path

import config
from processing import util


def _coletar(bases_dir: Path, *prefixos: str) -> list[Path]:
    arquivos: list[Path] = []
    for p in sorted(bases_dir.glob("*")):
        nome = util.norm_header(p.stem)
        if p.suffix.lower() not in {".csv"}:
            continue
        if any(nome.startswith(util.norm_header(pref)) or util.norm_header(pref) in nome for pref in prefixos):
            arquivos.append(p)
    return arquivos


def _ler_lista(arquivos: list[Path], schema: dict) -> list[dict]:
    todas: list[dict] = []
    for arq in arquivos:
        rows = util.read_csv_rows(arq)
        if not rows:
            continue
        hmap = util.build_header_map(rows[0].keys(), schema)
        mapped = util.map_rows(rows, hmap)
        for m in mapped:
            m["__arquivo__"] = arq.name
        todas.extend(mapped)
    return todas


def carregar_bases(bases_dir: Path | None = None) -> dict:
    """Carrega todas as bases disponíveis e devolve estruturas canônicas.

    Retorna um dict com:
      visitas, ausencias, painel, estrutura, franquias (listas de dicts)
      meta (arquivos lidos, contagens, pasta de origem)
    """
    bases_dir = Path(bases_dir) if bases_dir else config.resolve_bases_dir()

    arquivos_disponiveis = []
    if bases_dir.exists():
        arquivos_disponiveis = [p.name for p in sorted(bases_dir.glob("*")) if p.is_file()]

    visitas_files = _coletar(bases_dir, "relatorio_visitas", "visitas", "visita")
    ausencias_files = _coletar(bases_dir, "ausencia", "ausencias", "tot")
    painel_files = _coletar(bases_dir, "painel", "snapshot", "mccp")
    estrutura_files = _coletar(bases_dir, "estrutura", "hierarquia")
    franquias_files = _coletar(bases_dir, "franquias_especialidades", "franquia_especialidade", "franquias")

    visitas = _ler_lista(visitas_files, config.COLUNAS_VISITAS)
    ausencias = _ler_lista(ausencias_files, config.COLUNAS_AUSENCIAS)
    painel = _ler_lista(painel_files, config.COLUNAS_PAINEL)
    estrutura = _ler_lista(estrutura_files, config.COLUNAS_ESTRUTURA)
    franquias = _ler_lista(franquias_files, config.COLUNAS_FRANQUIAS)

    meta = {
        "bases_dir": str(bases_dir),
        "bases_dir_existe": bases_dir.exists(),
        "arquivos_encontrados": arquivos_disponiveis,
        "arquivos_lidos": {
            "visitas": [p.name for p in visitas_files],
            "ausencias": [p.name for p in ausencias_files],
            "painel": [p.name for p in painel_files],
            "estrutura": [p.name for p in estrutura_files],
            "franquias": [p.name for p in franquias_files],
        },
        "contagens_brutas": {
            "visitas": len(visitas),
            "ausencias": len(ausencias),
            "painel": len(painel),
            "estrutura": len(estrutura),
            "franquias": len(franquias),
        },
    }

    return {
        "visitas": visitas,
        "ausencias": ausencias,
        "painel": painel,
        "estrutura": estrutura,
        "franquias": franquias,
        "meta": meta,
    }
