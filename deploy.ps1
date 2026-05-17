# Despliegue a Cloud Run en un solo paso (PowerShell).
#
# Requisitos previos:
#   1. gcloud auth login && gcloud auth application-default login
#   2. gcloud config set project <PROJECT_ID>
#   3. Guarda tu clave de Anthropic en Secret Manager:
#        gcloud secrets create ANTHROPIC_API_KEY --replication-policy=automatic
#        "sk-ant-..." | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-
#
# Uso:
#   ./deploy.ps1 -ProjectId mi-proyecto -Region us-central1
#   ./deploy.ps1 -ProjectId mi-proyecto -Region europe-west1 -Service spec-agent

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ProjectId,
    [string] $Region = "us-central1",
    [string] $Repo = "spec-agent",
    [string] $Service = "spec-agent",
    [string] $SecretName = "ANTHROPIC_API_KEY"
)

$ErrorActionPreference = "Stop"

$Image = "$Region-docker.pkg.dev/$ProjectId/$Repo/$Service`:latest"

Write-Host "Proyecto : $ProjectId"
Write-Host "Region   : $Region"
Write-Host "Servicio : $Service"
Write-Host "Imagen   : $Image"
Write-Host ""

Write-Host "==> Habilitando APIs necesarias"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com `
    cloudbuild.googleapis.com secretmanager.googleapis.com --project $ProjectId

Write-Host "==> Asegurando que existe el repositorio de Artifact Registry"
$existing = gcloud artifacts repositories list --location=$Region --project=$ProjectId `
    --filter="name~/$Repo$" --format="value(name)" 2>$null
if (-not $existing) {
    gcloud artifacts repositories create $Repo `
        --repository-format=docker `
        --location=$Region `
        --description="Imagenes del agente dirigido por specs" `
        --project=$ProjectId
}

Write-Host "==> Compilando imagen con Cloud Build"
gcloud builds submit --tag $Image --project $ProjectId

Write-Host "==> Desplegando a Cloud Run"
gcloud run deploy $Service `
    --image=$Image `
    --region=$Region `
    --platform=managed `
    --allow-unauthenticated `
    --port=8080 `
    --memory=1Gi `
    --cpu=1 `
    --timeout=600s `
    --concurrency=8 `
    --max-instances=5 `
    --set-env-vars="OUTPUT_DIR=/tmp/output,STREAMLIT_SERVER_HEADLESS=true" `
    --set-secrets="ANTHROPIC_API_KEY=$SecretName`:latest" `
    --project=$ProjectId

Write-Host ""
Write-Host "==> Listo. URL del servicio:"
gcloud run services describe $Service --region=$Region --project=$ProjectId `
    --format="value(status.url)"
