"""Funções utilitárias compartilhadas pelos módulos de processamento.

Tudo aqui usa apenas a biblioteca padrão. As funções são puras (recebem
dados e devolvem dados) para facilitar teste, debug e reuso.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from config import VERDADEIRO


# ---------------------------------------------------------------------------
# Normalização de texto / cabeçalhos
# ---------------------------------------------------------------------------
def strip_accents(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def norm_header(texto: str) -> str:
    """Normaliza um cabeçalho de coluna para comparação tolerante."""
    if texto is None:
        return ""
    t = strip_accents(str(texto)).lower().strip()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    return t.strip("_")


def norm_text(texto) -> str:
    """Normaliza um valor textual mantendo legibilidade (sem snake_case)."""
    if texto is None:
        return ""
    return str(texto).strip()


def norm_key(texto) -> str:
    """Chave canônica (minúscula, sem acento) para deduplicar/cruzar."""
    return strip_accents(norm_text(texto)).lower()


# ---------------------------------------------------------------------------
# Conversões
# ---------------------------------------------------------------------------
def to_bool(valor) -> bool:
    if valor is None:
        return False
    return norm_key(valor) in VERDADEIRO


def to_float(valor, default: float = 0.0) -> float:
    if valor is None or valor == "":
        return default
    s = str(valor).strip().replace("%", "")
    # Trata vírgula decimal pt-BR.
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


def to_int(valor, default: int = 0) -> int:
    return int(round(to_float(valor, default)))


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%y",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
)


def parse_date(valor) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (date, datetime)):
        return valor.date() if isinstance(valor, datetime) else valor
    s = str(valor).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # tenta extrair só a parte de data
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def ym(d: date | None) -> str | None:
    """Retorna 'AAAA-MM' a partir de uma data."""
    if d is None:
        return None
    return f"{d.year:04d}-{d.month:02d}"


# ---------------------------------------------------------------------------
# Leitura tolerante de CSV
# ---------------------------------------------------------------------------
def detect_delimiter(sample: str) -> str:
    candidatos = [";", ",", "\t", "|"]
    primeira_linha = sample.splitlines()[0] if sample.splitlines() else sample
    contagem = {d: primeira_linha.count(d) for d in candidatos}
    melhor = max(contagem, key=contagem.get)
    return melhor if contagem[melhor] > 0 else ","


def read_csv_rows(path: Path) -> list[dict]:
    """Lê um CSV com detecção de delimiter e encoding tolerante.

    Retorna lista de dicts com cabeçalhos originais preservados.
    """
    encodings = ("utf-8-sig", "utf-8", "latin-1", "cp1252")
    texto = None
    for enc in encodings:
        try:
            texto = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue
    if texto is None:
        return []
    delim = detect_delimiter(texto[:4096])
    reader = csv.DictReader(texto.splitlines(), delimiter=delim)
    linhas = []
    for row in reader:
        linhas.append(row)
    return linhas


def build_header_map(headers: Iterable[str], schema: dict[str, list[str]]) -> dict[str, str]:
    """Mapeia nome canônico -> cabeçalho real existente no arquivo.

    `schema` é um dict canônico -> sinônimos. A comparação usa norm_header.
    """
    norm_to_real = {norm_header(h): h for h in headers if h is not None}
    resultado: dict[str, str] = {}
    for canonico, sinonimos in schema.items():
        # tenta match direto pelo próprio nome canônico também
        candidatos = [canonico] + list(sinonimos)
        for cand in candidatos:
            nc = norm_header(cand)
            if nc in norm_to_real:
                resultado[canonico] = norm_to_real[nc]
                break
    return resultado


def map_rows(rows: list[dict], header_map: dict[str, str]) -> list[dict]:
    """Reescreve as linhas usando os nomes canônicos definidos no header_map."""
    saida = []
    for row in rows:
        nova = {}
        for canonico, real in header_map.items():
            nova[canonico] = row.get(real)
        saida.append(nova)
    return saida


# ---------------------------------------------------------------------------
# Agregação
# ---------------------------------------------------------------------------
def safe_div(num: float, den: float, default: float = 0.0) -> float:
    return num / den if den else default


def pct(num: float, den: float) -> float:
    return round(100.0 * safe_div(num, den), 1)


def rounded(valor: float, casas: int = 1) -> float:
    try:
        return round(float(valor), casas)
    except (TypeError, ValueError):
        return 0.0
