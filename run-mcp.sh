#!/bin/bash
set -euo pipefail
export HIGPERTEXT_PROJECT_ROOT=/home/aomerge/Documentos/Proyects/higpertext-cli
cd /home/aomerge/Documentos/Proyects/higpertext-mcp
exec /home/aomerge/Documentos/Proyects/higpertext-mcp/.venv/bin/python -m higpertext_mcp.server 2>>/tmp/higpertext-mcp-stderr.log
