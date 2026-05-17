#!/usr/bin/env bash
# Despliegue a Cloud Run en un solo paso (bash).
#
# Requisitos previos:
#   1. gcloud auth login && gcloud auth application-default login
#   2. gcloud config set project <PROJECT_ID>
#   3. Guarda tu clave de Anthropic en Secret Manager:
#        gcloud secrets create ANTHROPIC_API_KEY --replication-policy=automatic
#        printf 'sk-ant-...' | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-
#
# Uso:
#   PROJECT_ID=mi-proyecto ./deploy.sh
#   PROJECT_ID=mi-proyecto REGION=europe-west1 SERVICE=spec-agent ./deploy.sh

set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID es obligatorio}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-spec-agent}"
SERVICE="${SERVICE:-spec-agent}"
SECRET_NAME="${SECRET_NAME:-ANTHROPIC_API_KEY}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:latest"

echo "Proyecto : ${PROJECT_ID}"
echo "Region   : ${REGION}"
echo "Servicio : ${SERVICE}"
echo "Imagen   : ${IMAGE}"
echo

echo "==> Habilitando APIs necesarias"
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    --project "${PROJECT_ID}"

echo "==> Asegurando que existe el repositorio de Artifact Registry"
if ! gcloud artifacts repositories describe "${REPO}" \
        --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${REPO}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Imagenes del agente dirigido por specs" \
        --project="${PROJECT_ID}"
fi

echo "==> Compilando imagen con Cloud Build"
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}"

echo "==> Desplegando a Cloud Run"
gcloud run deploy "${SERVICE}" \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=1Gi \
    --cpu=1 \
    --timeout=600s \
    --concurrency=8 \
    --max-instances=5 \
    --set-env-vars="OUTPUT_DIR=/tmp/output,STREAMLIT_SERVER_HEADLESS=true" \
    --set-secrets="ANTHROPIC_API_KEY=${SECRET_NAME}:latest" \
    --project="${PROJECT_ID}"

echo
echo "==> Listo. URL del servicio:"
gcloud run services describe "${SERVICE}" \
    --region="${REGION}" --project="${PROJECT_ID}" \
    --format='value(status.url)'
