FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 \
    OUTPUT_DIR=/tmp/output \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Cachebust: cambia este valor para forzar a Docker a no reutilizar capas
# de COPY src ./src cuando sospechamos que el código no se actualizó.
ARG CACHEBUST=2026-05-17-fix-refs-v2
RUN echo "cachebust=${CACHEBUST}"

COPY src ./src
COPY app.py main.py ./

# Cloud Run solo permite escrituras en /tmp; OUTPUT_DIR apunta ahí por defecto.
RUN mkdir -p /tmp/output

# Cloud Run inyecta $PORT (por defecto 8080). Se vincula a 0.0.0.0.
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" || exit 1

# Forma shell para que $PORT se expanda en tiempo de ejecución.
CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
