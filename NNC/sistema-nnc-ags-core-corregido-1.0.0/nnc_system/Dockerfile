FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY core/ ./core/
COPY proto/ ./proto/
COPY db/ ./db/
COPY assets/ ./assets/
COPY main.py service_server.py dashboard_server.py suite_autotest_calibracion_maestra.py test_autocalibracion_continua_iss.py grpc_client_stub.py config.json security_config.json README.md LICENSE ./
RUN useradd --create-home --uid 10001 appuser && mkdir -p logs && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1
CMD ["python", "service_server.py"]
