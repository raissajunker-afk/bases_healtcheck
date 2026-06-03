"""Gera portal — delega para portal_builder (dashboard original + navegação)."""
from __future__ import annotations

from pathlib import Path

from frontend.portal_builder import gerar_portal


def gerar_html(payload_path: Path | None = None, output_path: Path | None = None) -> Path:
    return gerar_portal(payload_path=payload_path, output_path=output_path)
