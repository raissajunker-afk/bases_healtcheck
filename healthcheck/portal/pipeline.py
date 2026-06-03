"""Pipeline do portal.

Orquestra: processar.py (regras de negócio reais sobre as bases) -> payload.json
-> adapter (payload modular) -> html_builder (HTML self-contained).

Não duplica nem altera nenhuma fórmula: o processamento é o `processar.py`
original; aqui só orquestramos e adaptamos a saída para o portal.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import config
from portal.adapter import construir_portal_payload


def _achar_payload(candidatos: list[Path]) -> Path | None:
    achados = [p for p in candidatos if p.exists()]
    if not achados:
        return None
    return max(achados, key=lambda p: p.stat().st_mtime)


def rodar_processar(bases_dir: Path, verbose: bool = True) -> Path:
    """Executa o processar.py original com cwd na pasta de bases.

    Retorna o caminho do payload.json copiado para output/.
    """
    if not config.PROCESSAR_PATH.exists():
        raise FileNotFoundError(f"processar.py não encontrado em {config.PROCESSAR_PATH}")

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"[processar] rodando regras de negócio sobre as bases em: {bases_dir}")
    proc = subprocess.run(
        [sys.executable, str(config.PROCESSAR_PATH)],
        cwd=str(bases_dir),
        capture_output=True, text=True,
    )
    log_path = config.AUDIT_DIR / "processar_log.txt"
    log_path.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
    if verbose:
        # mostra as últimas linhas úteis
        for ln in (proc.stdout or "").splitlines()[-12:]:
            print("   " + ln)
    if proc.returncode != 0:
        raise RuntimeError(
            f"processar.py falhou (exit {proc.returncode}). Veja {log_path}.\n" + (proc.stderr or "")[-1000:]
        )

    # processar.py grava payload.json em OUT_DIR (OneDrive se existir, senão cwd=bases_dir)
    candidato = _achar_payload([
        bases_dir / "payload.json",
        bases_dir.parent / "payload.json",
        config.CORPORATE_BASES.parent / "payload.json",
        Path.cwd() / "payload.json",
    ])
    if candidato is None:
        raise FileNotFoundError("payload.json não foi gerado pelo processar.py.")

    shutil.copy2(candidato, config.PAYLOAD_PATH)
    # copia auditorias se existirem ao lado do payload
    for aux in ("dedup_audit.csv", "tipo_setor_audit.csv"):
        src = candidato.parent / aux
        if src.exists():
            shutil.copy2(src, config.AUDIT_DIR / aux)
    if verbose:
        print(f"[processar] payload.json copiado para {config.PAYLOAD_PATH}")
    return config.PAYLOAD_PATH


def carregar_payload_real() -> dict:
    if not config.PAYLOAD_PATH.exists():
        raise FileNotFoundError(
            f"payload.json não encontrado em {config.PAYLOAD_PATH}. "
            "Rode o processamento primeiro (python main.py)."
        )
    return json.loads(config.PAYLOAD_PATH.read_text(encoding="utf-8"))


def construir_portal(verbose: bool = True) -> dict:
    real = carregar_payload_real()
    portal_payload = construir_portal_payload(real)
    config.PORTAL_PAYLOAD_PATH.write_text(
        json.dumps(portal_payload, ensure_ascii=False, default=str), encoding="utf-8"
    )
    if verbose:
        n_sec = len(portal_payload["registry"])
        n_cons = len(portal_payload["datasets"].get("consultores", []))
        print(f"[portal] payload modular: {n_sec} seções, {n_cons} consultores")
    return portal_payload
