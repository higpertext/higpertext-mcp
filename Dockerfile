FROM python:3.12-slim

WORKDIR /opt/higpertext-mcp
COPY . /opt/higpertext-mcp

RUN pip install --no-cache-dir /opt/higpertext-mcp

# Las capabilities reciben rutas relativas del cliente; deben resolverlas
# contra el proyecto montado, no contra el código del servidor instalado.
WORKDIR /workspace
EXPOSE 8790
CMD ["python", "/opt/higpertext-mcp/run-mcp-http.py"]
