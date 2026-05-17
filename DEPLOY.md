# Despliegue en Google Cloud Run

El frontend Streamlit (`app.py`) se empaqueta en un único contenedor que
ejecuta tanto la UI como el pipeline LangGraph. Cloud Run inyecta `$PORT`
(por defecto `8080`); el Dockerfile vincula Streamlit a ese puerto.

## 1. Configuración inicial (una sola vez)

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <TU_PROJECT_ID>
```

Habilita las APIs que usarán los scripts de despliegue:

```bash
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com
```

## 2. Guarda la clave de Anthropic en Secret Manager

```bash
gcloud secrets create ANTHROPIC_API_KEY --replication-policy=automatic
printf 'sk-ant-...' | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-
```

Concede acceso a la cuenta de servicio runtime por defecto de Cloud Run:

```bash
PROJECT_NUMBER=$(gcloud projects describe <TU_PROJECT_ID> --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## 3. Despliegue (elige una opción)

### Opción A — script de un solo paso

bash:

```bash
PROJECT_ID=<TU_PROJECT_ID> ./deploy.sh
```

PowerShell:

```powershell
./deploy.ps1 -ProjectId <TU_PROJECT_ID>
```

Ambos scripts: habilitan las APIs, crean el repositorio de Artifact Registry
si no existe, compilan vía Cloud Build y despliegan a Cloud Run con el
secreto montado.

### Opción B — trigger de Cloud Build

`cloudbuild.yaml` ejecuta el mismo flujo. Lanza manualmente:

```bash
gcloud builds submit --config cloudbuild.yaml \
    --substitutions=_REGION=us-central1,_REPO=spec-agent,_SERVICE=spec-agent
```

O engánchalo a un trigger de GitHub para que cada push a `main` reconstruya
y redepliegue.

## 4. Parámetros de runtime

| Variable | Defecto | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(secreto)_ | Autenticación del LLM — obligatoria. |
| `GENERATION_MODEL` | `claude-opus-4-7` | Generación pesada de specs. |
| `UTILITY_MODEL` | `claude-haiku-4-5-20251001` | Pasos rápidos de enrutado/validación. |
| `OUTPUT_DIR` | `/tmp/output` | Cloud Run solo permite escrituras en `/tmp`. |
| `PORT` | `8080` | Inyectado por Cloud Run; no lo hardcodees. |

## 5. Restricciones importantes

- **Filesystem efímero.** El contenedor solo tiene `/tmp` (un `tmpfs`) para
  escribir. Los archivos que escribe el consolidator son visibles en la
  sesión activa por la UI, pero **desaparecen cuando la instancia escala a
  cero**. Para almacenamiento a largo plazo conecta un bucket de GCS
  (ver "Próximos pasos" más abajo).
- **Los arranques en frío cuestan latencia LLM.** Una primera petición tras
  el escalado a cero paga el arranque del contenedor + el de Streamlit.
  Configura `--min-instances=1` si quieres instancias calientes (más coste).
- **Concurrencia conservadora (8).** Streamlit guarda estado por sesión en
  la memoria del proceso; súbela con cuidado si ves saturación de CPU.
- **CORS / XSRF deshabilitados en el contenedor.** Cloud Run termina TLS y
  Streamlit es lo único servido — bien para esta app de propósito único,
  pero no rehosps la misma imagen detrás de otro proxy sin volver a
  habilitarlos.

## 6. Próximos pasos (no implementado)

- Persistir `output/` en un bucket de GCS para que los specs generados
  sobrevivan al escalado a cero.
- Añadir autenticación IAM de Cloud Run (`--no-allow-unauthenticated`) y
  ponerla detrás de IAP.
- Exponer un endpoint HTTP `/api/generate` (FastAPI) junto a Streamlit para
  clientes programáticos.
