# 🤖 AI Spec-Driven Multi-Agent (LangGraph)

**🌐 Language / Idioma**: **English** · [Español](README.es.md)

> Turn natural-language requirements into formal specs (OpenAPI + Gherkin + Claude Agent) — generated in parallel by a multi-agent system built with **LangGraph**.

[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C.svg)](https://langchain-ai.github.io/langgraph/)
[![Claude](https://img.shields.io/badge/Claude-Opus%204.7-D97757.svg?logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Cloud Run](https://img.shields.io/badge/deploy-Cloud%20Run-4285F4.svg?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-38%20passing-brightgreen.svg)](./tests)
[![Pydantic v2](https://img.shields.io/badge/pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## ✨ What it does

You describe a system in natural language and it returns, **in parallel**, the formal technical documentation you need to start building:

| Spec | What it's for |
|---|---|
| 📄 **OpenAPI 3.1.0** (YAML) | REST API contract. Generate backend, client SDKs and docs with one command. |
| 🥒 **Gherkin** (`.feature`) | BDD test scenarios with Spanish keywords (`Característica`, `Escenario`, `Dado`, `Cuando`, `Entonces`). |
| 🧠 **Claude Agent** (`system_prompt.md` + `tools.json`) | Ready-to-wire system prompt and tool definitions for an AI assistant. |

All generated content is written **in Spanish** (by design — the prompts are tuned for Spanish output) and validated with deterministic parsers (no LLM-as-judge).

## 🏛️ Architecture

```
                Natural-language requirements
                          │
                          ▼
                ┌─────────────────────┐
                │ analyze_requirements│  ← extracts domain, entities, actions…
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  route_spec_types   │  ← decides which specs to generate
                └──────────┬──────────┘
                           │  Send API (parallel fan-out)
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ openapi  │ │ gherkin  │ │  agent   │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             └────────────┼────────────┘
                          ▼
                ┌─────────────────────┐
                │   validate_specs    │  ← real parsers (openapi-spec-validator + gherkin-official)
                └──────────┬──────────┘
                           ▼
                ┌─────────────────────┐
                │     consolidate     │  ← writes to disk + README
                └─────────────────────┘
```

Parallel branches are merged in the shared state via **LangGraph reducers** (`operator.or_` for dicts, `operator.add` for lists).

## 🚀 Quick start

### Local

```bash
git clone https://github.com/Acquarts/ai-spec-driven-multiagent-langgraph.git
cd ai-spec-driven-multiagent-langgraph

pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY

streamlit run app.py
```

### CLI

```bash
python main.py -r "Build a REST API for task management with JWT auth…"
python main.py -f my_requirements.txt
```

### Cloud Run (one-shot deploy)

```bash
# Store your key in Secret Manager
gcloud secrets create ANTHROPIC_API_KEY --replication-policy=automatic
printf 'sk-ant-...' | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-

# Deploy
PROJECT_ID=my-project ./deploy.sh         # bash
./deploy.ps1 -ProjectId my-project        # PowerShell
```

Full guide in [DEPLOY.md](DEPLOY.md).

## 🧱 Project layout

```
ai-spec-driven-multiagent-langgraph/
├── 🎨 app.py                  # Streamlit frontend (auth + rate limit + UI)
├── 💻 main.py                 # CLI
├── 📦 src/
│   ├── config.py             # Anthropic client, retry, logging, JSON parsing
│   ├── state.py              # SpecState (Pydantic) with LangGraph reducers
│   ├── graph.py              # StateGraph assembly
│   ├── cost.py               # Token + USD cost tracker
│   ├── rate_limit.py         # In-memory per-IP rate limiter
│   ├── logging_setup.py      # Structured JSON logs (Cloud Logging-friendly)
│   └── nodes/
│       ├── analyzer.py        # 🔍 extracts StructuredRequirements
│       ├── router.py          # 🔀 decides which specs to generate
│       ├── openapi.py         # 📄 generates OpenAPI YAML
│       ├── gherkin.py         # 🥒 generates .feature files (Spanish keywords)
│       ├── agent_spec.py      # 🧠 generates system prompt + tools
│       ├── validator.py       # ✅ deterministic validation
│       └── consolidator.py    # 💾 writes to disk + README
├── 🧪 tests/                  # 38 tests with pytest
├── 🐳 Dockerfile              # Single image for Cloud Run
├── 🏗️ cloudbuild.yaml         # CI/CD pipeline
├── 🚀 deploy.sh / deploy.ps1  # One-shot deploy scripts
└── 📘 DEPLOY.md / CLAUDE.md   # Documentation
```

## ⚙️ Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(required)_ | Auth with the Claude API. |
| `APP_PASSWORD` | _(empty)_ | If set, the UI requires this password to enter. Empty = dev mode, no auth. |
| `GENERATION_MODEL` | `claude-opus-4-7` | Model for heavy generation (analyzer + spec generators). |
| `UTILITY_MODEL` | `claude-haiku-4-5-20251001` | Model for fast tasks (router). |
| `RATE_LIMIT_REQUESTS` | `5` | Requests per IP within the window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window size in seconds. |
| `MAX_REQUIREMENTS_CHARS` | `10000` | Input size cap to avoid runaway bills. |
| `OUTPUT_DIR` | `./output` | Where specs are written. On Cloud Run must be `/tmp/output`. |
| `LOG_LEVEL` | `INFO` | Structured logger level. |

## 🛡️ Security

- 🔐 **Shared-password auth** (`APP_PASSWORD`) for the Streamlit UI, using `hmac.compare_digest`.
- 🚦 **In-memory rate limit** per IP (5 req/min by default).
- 📏 **Input length cap** (10K chars by default) to block abusive prompts.
- 🗝️ **Secrets in GCP Secret Manager** — never in code or hardcoded env vars.
- 🚫 **No retry on 4xx errors** — fail fast on auth/credentials issues instead of burning latency.

## 🔭 Observability

Every LLM call emits a structured JSON log line:

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

Cloud Logging parses these automatically. Filter by `jsonPayload.node="generate_openapi"` or aggregate `jsonPayload.usd` for total cost.

## 💰 Cost tracking

The sidebar shows accumulated USD cost since the container started. Prices are computed from Anthropic's public per-model rates (`src/cost.py`).

## 🧪 Tests

```bash
pytest                          # 38 tests, ~2.5s
pytest tests/test_nodes.py -v   # tests for one module
```

Coverage:

- ✅ JSON response parsing tolerating prose before/after (`raw_decode`)
- ✅ OpenAPI / Gherkin (ES + EN) / Agent validation
- ✅ Defensive `$ref` post-processing (fixes a recurring LLM bug)
- ✅ Mocked Anthropic client per node
- ✅ Rate limiter (windows, independent keys, expiration)

## 🛠️ Stack

| Layer | Technology |
|---|---|
| Orchestration | [LangGraph](https://langchain-ai.github.io/langgraph/) (`StateGraph`, `Send` API) |
| LLM | [Anthropic Claude](https://www.anthropic.com/) (Opus 4.7 + Haiku 4.5) |
| State | [Pydantic v2](https://docs.pydantic.dev/) |
| Frontend | [Streamlit](https://streamlit.io/) |
| Validation | `openapi-spec-validator`, `gherkin-official`, `pyyaml` |
| Tests | `pytest`, `pytest-asyncio` |
| Packaging | Docker (Python 3.11-slim) |
| Deployment | [Google Cloud Run](https://cloud.google.com/run) + Artifact Registry + Secret Manager |
| Retries | `tenacity` (transient errors only) |

## 🗺️ Roadmap

- [ ] Persist outputs to GCS (survive scale-to-zero)
- [ ] Split UI (Streamlit) from backend (FastAPI) — independent scaling
- [ ] Tracing with OpenTelemetry / LangSmith
- [ ] Rate limit backed by Redis (coherent across multiple instances)
- [ ] Anthropic prompt caching
- [ ] Iterative pipeline for large systems (>10 entities): first pass generates structure, subsequent passes refine

## 📜 License

Released under the [Apache License 2.0](LICENSE). You are free to use, modify, distribute and sublicense the code, including commercially, as long as you keep the copyright notice, state significant changes you made, and don't use the project's name/marks to endorse derived work without permission.

Copyright © 2026 Acquarts.

## 🤝 Contributing

Issues and PRs welcome. For larger changes, please open an issue first to discuss the approach.

---

> Built with LangGraph, Claude and lots of coffee. ☕
