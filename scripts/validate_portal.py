#!/usr/bin/env python3
"""Valida que o portal foi gerado a partir do dashboard original."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "healthcheck" / "Healthcheck_Portal.html"
PAYLOAD = ROOT / "healthcheck" / "payload.json"


def main() -> int:
    errors = []
    if not PAYLOAD.exists():
        errors.append(f"Falta {PAYLOAD} — rode: python main.py")
    if not PORTAL.exists():
        errors.append(f"Falta {PORTAL} — rode: python main.py --portal-only")
        for e in errors:
            print("ERRO:", e)
        return 1

    html = PORTAL.read_text(encoding="utf-8")
    required = [
        ("bootPortal", "Navegação portal"),
        ("function renderKPIs", "Dashboard original (KPIs)"),
        ("function renderSim3", "Simulador original"),
        ("id=\"vista-overview\"", "Aba Visão Geral"),
        ("id=\"vista-detail\"", "Aba Detalhe"),
        ("PORTAL_SECTIONS", "15 seções configuradas"),
        ("DATA_B64", "Payload embutido"),
    ]
    for token, label in required:
        if token not in html:
            errors.append(f"Ausente ({label}): {token}")

    if "function renderKPIs" not in html and "kpi_consultores" in html:
        errors.append("Parece portal genérico antigo — regenere com portal_builder.py")

    if len(html) < 500_000:
        errors.append(f"HTML pequeno demais: {len(html)} bytes")

    if errors:
        for e in errors:
            print("ERRO:", e)
        return 1

    print(f"OK: portal legado integrado — {PORTAL.name} ({len(html)/1024/1024:.2f} MB)")
    print(f"OK: payload — {PAYLOAD.stat().st_size/1024/1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
