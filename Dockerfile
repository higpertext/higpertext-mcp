# El contexto de build es el directorio padre que contiene higpertext-cli y
# higpertext-mcp (ver deploy/docker-compose.yml del profile server).
FROM python:3.12-slim

WORKDIR /opt/higpertext-mcp
COPY higpertext-cli /opt/higpertext-cli
COPY higpertext-mcp /opt/higpertext-mcp

RUN pip install --no-cache-dir /opt/higpertext-cli /opt/higpertext-mcp

EXPOSE 8790
CMD ["python", "/opt/higpertext-mcp/run-mcp-http.py"]
