# 🤖 AI Spec-Driven Multi-Agent (LangGraph)

**🌐 Language / Idioma**: [English](README.md) · **Español**

> Convierte requisitos en lenguaje natural en specs formales (OpenAPI + Gherkin + Agente Claude) — generados en paralelo por un sistema multi-agente con **LangGraph**.

[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C.svg)](https://langchain-ai.github.io/langgraph/)
[![Claude](https://img.shields.io/badge/Claude-Opus%204.7-D97757.svg?logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Cloud Run](https://img.shields.io/badge/deploy-Cloud%20Run-4285F4.svg?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-38%20passing-brightgreen.svg)](./tests)
[![Pydantic v2](https://img.shields.io/badge/pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)

---

## ✨ Qué hace

Le describes un sistema en lenguaje natural y te devuelve, **en paralelo**, la documentación técnica formal para empezar a desarrollar:

| Spec | Para qué sirve |
|---|---|
| 📄 **OpenAPI 3.1.0** (YAML) | Contrato de tu API REST. Generas backend, cliente y docs con un comando. |
| 🥒 **Gherkin** (`.feature`) | Casos de prueba BDD con palabras clave en español (`Característica`, `Escenario`, `Dado`, `Cuando`, `Entonces`). |
| 🧠 **Agente Claude** (`system_prompt.md` + `tools.json`) | Definición lista para conectar a un asistente IA con herramientas. |

Todo escrito **en español** y con validación determinista (no LLM-as-judge).

## 🏛️ Arquitectura

```
                Texto en lenguaje natural
                          │
                          ▼
                ┌─────────────────────┐
                │ analyze_requirements│  ← extrae dominio, entidades, acciones…
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  route_spec_types   │  ← decide qué specs generar
                └──────────┬──────────┘
                           │  Send API (fan-out paralelo)
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ openapi  │ │ gherkin  │ │  agent   │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             └────────────┼────────────┘
                          ▼
                ┌─────────────────────┐
                │   validate_specs    │  ← parsers reales (openapi-spec-validator + gherkin-official)
                └──────────┬──────────┘
                           ▼
                ┌─────────────────────┐
                │     consolidate     │  ← escribe a disco + README
                └─────────────────────┘
```

Las ramas paralelas se fusionan en el estado con **reducers de LangGraph** (`operator.or_` para dict, `operator.add` para listas).

## 🚀 Inicio rápido

### Local

```bash
git clone https://github.com/Acquarts/ai-spec-driven-multiagent-langgraph.git
cd ai-spec-driven-multiagent-langgraph

pip install -r requirements.txt
cp .env.example .env  # añade tu ANTHROPIC_API_KEY

streamlit run app.py
```

Abre [http://localhost:8501](http://localhost:8501).

### CLI

```bash
python main.py -r "Construir una API REST para gestionar tareas con auth JWT…"
python main.py -f mis_requisitos.txt
```

### Cloud Run (despliegue de un solo paso)

```bash
# Guarda tu clave en Secret Manager
gcloud secrets create ANTHROPIC_API_KEY --replication-policy=automatic
printf 'sk-ant-...' | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-

# Despliega
PROJECT_ID=mi-proyecto ./deploy.sh         # bash
./deploy.ps1 -ProjectId mi-proyecto        # PowerShell
```

Guía completa en [DEPLOY.md](DEPLOY.md).

## 🧱 Estructura del proyecto

```
ai-spec-driven-multiagent-langgraph/
├── 🎨 app.py                  # Frontend Streamlit (auth + rate limit + UI)
├── 💻 main.py                 # CLI
├── 📦 src/
│   ├── config.py             # Cliente Anthropic, retry, logging, parsing JSON
│   ├── state.py              # SpecState (Pydantic) con reducers
│   ├── graph.py              # Ensamblaje del StateGraph
│   ├── cost.py               # Tracker de tokens y coste en USD
│   ├── rate_limit.py         # Rate limiter en memoria por IP
│   ├── logging_setup.py      # Logs JSON estructurados (Cloud Logging)
│   └── nodes/
│       ├── analyzer.py        # 🔍 extrae StructuredRequirements
│       ├── router.py          # 🔀 decide qué specs generar
│       ├── openapi.py         # 📄 genera OpenAPI YAML
│       ├── gherkin.py         # 🥒 genera .feature en español
│       ├── agent_spec.py      # 🧠 genera system prompt + tools
│       ├── validator.py       # ✅ validación determinista
│       └── consolidator.py    # 💾 escribe a disco + README
├── 🧪 tests/                  # 38 tests con pytest
├── 🐳 Dockerfile              # Imagen única para Cloud Run
├── 🏗️ cloudbuild.yaml         # Pipeline CI/CD
├── 🚀 deploy.sh / deploy.ps1  # Despliegue de un solo paso
└── 📘 DEPLOY.md / CLAUDE.md   # Documentación
```

## ⚙️ Variables de entorno

| Variable | Defecto | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(obligatoria)_ | Autenticación con la API de Claude. |
| `APP_PASSWORD` | _(vacío)_ | Si se define, exige password al abrir la UI. Vacío = modo dev sin auth. |
| `GENERATION_MODEL` | `claude-opus-4-7` | Modelo para generación pesada. |
| `UTILITY_MODEL` | `claude-haiku-4-5-20251001` | Modelo para tareas rápidas (router). |
| `RATE_LIMIT_REQUESTS` | `5` | Peticiones por IP en una ventana. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Tamaño de la ventana en segundos. |
| `MAX_REQUIREMENTS_CHARS` | `10000` | Límite del input para evitar facturas inesperadas. |
| `OUTPUT_DIR` | `./output` | Dónde se escriben los specs. En Cloud Run debe ser `/tmp/output`. |
| `LOG_LEVEL` | `INFO` | Nivel del logger estructurado. |

## 🛡️ Seguridad

- 🔐 **Auth con password compartido** (`APP_PASSWORD`) en la UI Streamlit, con `hmac.compare_digest`.
- 🚦 **Rate limit** en memoria por IP (5 req/min por defecto).
- 📏 **Límite de longitud del input** (10K caracteres por defecto) para evitar inputs abusivos.
- 🗝️ **Secretos en GCP Secret Manager** — nunca en código ni en variables de entorno hardcodeadas.
- 🚫 **Sin retry en errores 4xx** — falla rápido en auth/credenciales en vez de gastar latencia.

## 🔭 Observabilidad

Cada llamada al LLM emite un log JSON estructurado con:

```json
{
  "ts": "2026-05-17T19:30:12.345Z",
  "severity": "INFO",
  "message": "llm_call_ok",
  "request_id": "a1b2c3d4",
  "node": "generate_openapi",
  "model": "claude-opus-4-7",
  "tokens_in": 1234,
  "tokens_out": 8901,
  "usd": 0.6855,
  "stop_reason": "end_turn",
  "latency_ms": 24500
}
```

Cloud Logging los parsea automáticamente. Filtra por `jsonPayload.node="generate_openapi"` o agrega por `jsonPayload.usd`.

## 💰 Tracking de coste

El sidebar muestra el coste acumulado en USD desde que arrancó el contenedor. El precio se calcula con la tarifa pública de Anthropic por modelo (`src/cost.py`).

## 🧪 Tests

```bash
pytest                          # 38 tests, ~2.5s
pytest tests/test_nodes.py -v   # tests de un módulo
```

Cobertura:

- ✅ Parseo de respuestas JSON con prosa alrededor (`raw_decode`)
- ✅ Validación OpenAPI / Gherkin (ES + EN) / Agente
- ✅ Post-procesado defensivo de `$ref` (corrige el bug del LLM)
- ✅ Cliente Anthropic mockeado por nodo
- ✅ Rate limiter (ventanas, claves independientes, expiración)

## 🛠️ Stack

| Capa | Tecnología |
|---|---|
| Orquestación | [LangGraph](https://langchain-ai.github.io/langgraph/) (`StateGraph`, `Send` API) |
| LLM | [Anthropic Claude](https://www.anthropic.com/) (Opus 4.7 + Haiku 4.5) |
| Estado | [Pydantic v2](https://docs.pydantic.dev/) |
| Frontend | [Streamlit](https://streamlit.io/) |
| Validación | `openapi-spec-validator`, `gherkin-official`, `pyyaml` |
| Tests | `pytest`, `pytest-asyncio` |
| Empaquetado | Docker (Python 3.11-slim) |
| Despliegue | [Google Cloud Run](https://cloud.google.com/run) + Artifact Registry + Secret Manager |
| Reintentos | `tenacity` (solo errores transitorios) |

## 🗺️ Roadmap

- [ ] Persistir outputs en GCS (sobrevivir al scale-to-zero)
- [ ] Separar UI (Streamlit) de backend (FastAPI) — escalado independiente
- [ ] Tracing con OpenTelemetry / LangSmith
- [ ] Rate limit con Redis (multi-instancia coherente)
- [ ] Prompt caching de Anthropic
- [ ] Pipeline iterativo para sistemas grandes (>10 entidades): primera pasada genera estructura, siguientes refinan

## 📜 Licencia

Pendiente de definir. Mientras tanto, todos los derechos reservados.

## 🤝 Contribuciones

Issues y PRs bienvenidos. Para cambios grandes, abre un issue primero para discutir el enfoque.

---

> Hecho con LangGraph, Claude y mucho café. ☕
