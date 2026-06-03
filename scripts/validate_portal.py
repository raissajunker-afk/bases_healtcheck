#!/usr/bin/env python3
"""Validação rápida do HTML do portal (sem navegador)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / "healthcheck" / "Healthcheck_Portal.html"
PAYLOAD = ROOT / "healthcheck" / "payload.json"


def main() -> int:
    errors = []
    if not PAYLOAD.exists():
        errors.append(f"Falta {PAYLOAD} — rode: python main.py --skip-html")
    if not PORTAL.exists():
        errors.append(f"Falta {PORTAL} — rode: python main.py --skip-processar --portal-only")
        for e in errors:
            print("ERRO:", e)
        return 1

    html = PORTAL.read_text(encoding="utf-8")
    required = [
        "PAYLOAD_B64",
        "Executive Overview",
        "Canal Digital",
        "DecompressionStream",
        "exportCsv",
        "f-janela",
    ]
    for token in required:
        if token not in html:
            errors.append(f"Token ausente no HTML: {token}")

    if len(html) < 100_000:
        errors.append(f"HTML suspeitamente pequeno: {len(html)} bytes")

    if errors:
        for e in errors:
            print("ERRO:", e)
        return 1

    print(f"OK: {PORTAL.name} ({len(html)/1024/1024:.2f} MB)")
    print(f"OK: payload.json ({PAYLOAD.stat().st_size/1024/1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
