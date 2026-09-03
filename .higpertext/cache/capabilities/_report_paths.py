"""Resolución de raíz compartida por los scripts de reports/.

Extrae el bloque de resolución de _ROOT que estaba duplicado casi idéntico en
commit_report.py, roadmap_report.py, report_viewer.py, telemetry_report.py y
training_recommender.py.
"""
from __future__ import annotations

import sys
from pathlib import Path


def resolve_root(include_root_in_path: bool = False) -> Path:
    """Sube desde este archivo hasta encontrar src/higpertext_data/config/htx_config.json —
    esa es la raíz real del engine (Hub o agente externo). Inserta <root>/src
    en sys.path para que los imports de higpertext.* funcionen sin importar
    el cwd desde el que se invocó el script."""
    here = Path(__file__).resolve()
    root = next(
        (p for p in here.parents if (p / "src/higpertext_data/config/htx_config.json").exists()),
        here.parents[4],
    )
    src_path = str(root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if include_root_in_path:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
    return root
