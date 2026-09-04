"""Capacidad para indexar el proyecto para RAG Semántico."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Configurar path para importar higpertext
_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / "src"))

from higpertext.kernel.infrastructure.database.local_vector_store import LocalVectorStore
from higpertext.kernel.application.rag_service import RAGService
from higpertext.kernel.application.embedding_factory import create_embedding_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa el proyecto para búsqueda semántica (RAG).")
    parser.add_argument("--root", type=str, default=".", help="Ruta al proyecto.")
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    print(f"[*] Iniciando indexación semántica en: {project_root}")
    
    try:
        embedder = create_embedding_provider(project_root)
        store = LocalVectorStore(project_root)
        service = RAGService(embedder, store)

        chunks_indexed = service.index_project(project_root)
        print(f"[+] Indexación completada. {chunks_indexed} fragmentos semánticos indexados con éxito.")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Falló la indexación: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
