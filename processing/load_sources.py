from __future__ import annotations

from pathlib import Path
import csv


DOMAIN_KEYWORDS = {
    "visitas": ("visita", "visitacao"),
    "ausencias": ("ausencia", "afastamento"),
    "painel": ("painel", "mccp", "estrutura"),
    "territorio": ("territorio", "brick", "setor"),
}


def _guess_domain(filename: str) -> str:
    lowered = filename.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return domain
    return "outros"


def _sniff_delimiter(sample: str) -> str:
    candidates = [";", ",", "\t", "|"]
    counts = {char: sample.count(char) for char in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ";"


def _read_csv(path: Path) -> tuple[list[dict[str, str]], str]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if not raw.strip():
        return [], ";"
    delimiter = _sniff_delimiter(raw[:4000])
    reader = csv.DictReader(raw.splitlines(), delimiter=delimiter)
    rows = [dict(row) for row in reader]
    return rows, delimiter


def carregar_bases(bases_dir: Path) -> dict:
    bases_dir.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(bases_dir.glob("*.csv"))

    tables: dict[str, list[dict[str, str]]] = {}
    files_meta: list[dict[str, str | int]] = []
    domains: dict[str, list[str]] = {
        "visitas": [],
        "ausencias": [],
        "painel": [],
        "territorio": [],
        "outros": [],
    }

    for file_path in csv_files:
        rows, delimiter = _read_csv(file_path)
        key = file_path.stem
        tables[key] = rows
        domain = _guess_domain(file_path.name)
        domains.setdefault(domain, []).append(key)
        files_meta.append(
            {
                "file_name": file_path.name,
                "table_key": key,
                "rows": len(rows),
                "delimiter": delimiter,
                "domain": domain,
            }
        )

    return {
        "bases_dir": str(bases_dir),
        "tables": tables,
        "domains": domains,
        "files": files_meta,
    }
