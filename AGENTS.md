# AGENTS.md

Instructions for coding agents working in this repository. Trust this file first; see [When to search](#when-to-search).

## Overview

This is a RAG (Retrieval-Augmented Generation) chat application over rows in a PostgreSQL database. A user asks a question, the backend rewrites it into a search query plus filters, runs hybrid search (pgvector cosine similarity + full-text) against Postgres, and asks an OpenAI chat model to answer from the retrieved rows with citations.

Main technologies: Python 3.10+ / FastAPI / SQLAlchemy 2 async / asyncpg / pgvector / `openai` + `openai-agents` on the backend; React 18 + TypeScript + FluentUI + Vite on the frontend; Bicep + Azure Developer CLI (`azd`) for infrastructure; Azure Container Apps + Azure PostgreSQL Flexible Server + Azure OpenAI for hosting.

Primary entry points:

- `src/backend/fastapi_app/__init__.py` — `create_app()` FastAPI factory (run via `uvicorn fastapi_app:create_app --factory`).
- `src/backend/fastapi_app/routes/api_routes.py` — REST + chat endpoints: `GET /items/{id}`, `GET /search`, `GET /similar`, `POST /chat`, `POST /chat/stream`. Interactive docs at `/docs`.
- `src/backend/fastapi_app/setup_postgres_database.py` — creates schema + pgvector extension + HNSW indexes.
- `src/frontend/src/` — React app; `npm run build` emits into `src/backend/static/`, which the backend serves.

Two RAG flows exist and are selectable per-request via `overrides.use_advanced_flow`: the simple flow embeds the question directly, the advanced flow uses an agent with function-calling to rewrite the query and choose filters.

## Code layout

Backend (`src/backend/fastapi_app/`):

- `__init__.py` — app factory, `lifespan` (builds engine, sessionmaker, OpenAI clients), Azure Monitor wiring.
- `dependencies.py` — `common_parameters()` resolves model/deployment/embedding-column config from env; FastAPI dependency providers.
- `openai_clients.py` — builds `AsyncOpenAI` clients for chat and embeddings, branching on `OPENAI_CHAT_HOST` / `OPENAI_EMBED_HOST` (`azure`, `ollama`, else OpenAI.com).
- `postgres_engine.py` — async engine creation from env or CLI args, including Entra token auth for `*.database.azure.com` hosts.
- `postgres_models.py` — SQLAlchemy models `Item` (`items` table) and `Car` (`cars` table), each with `embedding_3l` (1024-dim, text-embedding-3-large) and `embedding_nomic` (768-dim, nomic-embed-text) columns, plus HNSW cosine indexes.
- `postgres_searcher.py` — `PostgresSearcher`: vector / text / hybrid (RRF) search with optional column filters.
- `embeddings.py` — computes query embeddings for the configured embedding host.
- `rag_base.py`, `rag_simple.py`, `rag_advanced.py` — RAG flow implementations (`RAGChatBase`, `SimpleRAGChat`, `AdvancedRAGChat`). The advanced flow routes across both the items and cars domains via separate searchers.
- `query_rewriter.py` — tool/function definitions and argument parsing for query rewriting.
- `api_models.py` — Pydantic request/response models (`ChatRequestOverrides`, `RetrievalResponse`, `ThoughtStep`, filters, …).
- `prompts/` — `answer.txt`, `query.txt`, `query_fewshots.json`. Prompt changes usually require updating snapshots (see below).
- `seed_data.json`, `cars_seed_data.json` — seed rows with pre-computed embeddings for both embedding columns.
- `setup_postgres_*.py`, `update_embeddings.py`, `update_cars_embeddings.py` — one-shot setup / maintenance scripts, each runnable standalone with `--host/--username/--password/--database/--sslmode` args or from env.
- `Dockerfile`, `entrypoint.sh`, `pyproject.toml`, `requirements.txt` (in `src/backend/`) — container build and backend dependency definitions.

Frontend (`src/frontend/`): standard Vite layout; `src/api/` holds the typed client and streaming NDJSON reader, `src/components/` the chat UI, `src/pages/chat/` the main view.

Other top-level:

- `tests/` — pytest suite (`conftest.py` fixtures and OpenAI mocks, `mocks.py`, `data.py`, `snapshots/` for `pytest-snapshot`, `e2e.py` for Playwright).
- `evals/` — quality evaluation (`evaluate.py`, `generate_ground_truth.py`, `eval_config.json`, `ground_truth.jsonl`) and AI red-teaming (`safety_evaluation.py`, `redteams/`). Has its **own** `requirements.txt`.
- `infra/` — Bicep: `main.bicep`, `main.parameters.json`, `web.bicep`, `backend-dashboard.bicep`, `core/` modules.
- `scripts/` — shell/PowerShell wrappers invoked by azd hooks (`setup_postgres_database`, `setup_postgres_azurerole`, `setup_postgres_seeddata`).
- `.github/workflows/` — `app-tests.yaml` (matrix tests + ty + Playwright), `python-code-quality.yaml` (ruff lint + format), `bicep-security-scan.yaml`.
- `.github/copilot-instructions.md` — longer-form agent guidance with command timings; overlaps with this file.
- `azure.yaml` — azd service + hook definitions (frontend build runs as a prebuild hook).
- `pyproject.toml` (root) — ruff, ty, pytest, coverage config. `requirements-dev.txt` — dev deps (includes backend requirements).
- `locustfile.py` — load-test user class. `docs/` — deployment, evaluation, monitoring, auth, load-testing guides.

## Running the code

Prerequisites: Python 3.10+ (3.12 recommended), Node.js 18+, PostgreSQL 14+ with the pgvector extension, and a running Postgres instance. The devcontainer (`.devcontainer/`) provides all of these plus `azd`, the Azure CLI, and Ollama; if you are in it, dependencies are already installed by `postCreateCommand`.

1. Create and activate a virtual environment:

    ```shell
    python3 -m venv .venv && source .venv/bin/activate
    ```

2. Install dependencies and the backend as an editable package:

    ```shell
    python -m pip install -r requirements-dev.txt
    python -m pip install -e src/backend
    ```

3. Create the env file and point it at your local database:

    ```shell
    cp .env.sample .env
    ```

    Set `POSTGRES_HOST=localhost` and the `POSTGRES_USERNAME` / `POSTGRES_PASSWORD` / `POSTGRES_DATABASE` values that match your local server, and `POSTGRES_SSL=disable`.

4. Choose a model host by editing `.env`. There is no dedicated GitHub Models / Azure AI Inference code path in this repo — `openai_clients.py` supports exactly three: `azure`, `ollama`, and OpenAI.com. For local work without Azure, prefer one of the non-Azure options:

    - **Ollama (no keys needed)**: `OPENAI_CHAT_HOST=ollama`, `OPENAI_EMBED_HOST=ollama`, `OLLAMA_ENDPOINT=http://localhost:11434/v1`, `OLLAMA_CHAT_MODEL=llama3.1`, `OLLAMA_EMBED_MODEL=nomic-embed-text`. Use `llama3.1` (or another function-calling model) or the advanced flow will fail; the seed data already contains `nomic-embed-text` embeddings.
    - **OpenAI.com**: `OPENAI_CHAT_HOST=openai`, `OPENAI_EMBED_HOST=openai`, `OPENAICOM_KEY=<key>`.
    - **Azure OpenAI**: `OPENAI_CHAT_HOST=azure`, `OPENAI_EMBED_HOST=azure`, plus `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_CHAT_DEPLOYMENT` / `AZURE_OPENAI_EMBED_DEPLOYMENT`. Requires `azd auth login` (or `AZURE_OPENAI_KEY`).

    Read `azd env get-values` to fill Azure values from an existing deployment.

5. Create the schema and seed data (order matters — schema first):

    ```shell
    python ./src/backend/fastapi_app/setup_postgres_database.py
    python ./src/backend/fastapi_app/setup_postgres_seeddata.py
    python ./src/backend/fastapi_app/setup_postgres_cars_seeddata.py
    ```

6. Build the frontend once before starting the backend — the backend serves static files from `src/backend/static/`:

    ```shell
    cd src/frontend && npm install && npm run build && cd ../..
    ```

7. Run the backend from the repository root:

    ```shell
    python -m uvicorn fastapi_app:create_app --factory --reload
    ```

    The full app (API + built frontend) is at `http://localhost:8000`, docs at `http://localhost:8000/docs`.

8. Optional — run the frontend dev server with hot reload (Vite proxies `/chat` to `http://localhost:8000`, so keep the backend running too):

    ```shell
    cd src/frontend && npm run dev
    ```

    Then open `http://localhost:5173/`. VS Code launch configs "Backend", "Frontend", and "Frontend & Backend" do the same thing.

Quick smoke check that needs no model host:

```shell
curl http://localhost:8000/items/1
```

## Running the tests

A live PostgreSQL server with pgvector on `localhost` is required — `tests/conftest.py` hardcodes `POSTGRES_HOST=localhost` and creates/seeds the schema itself. It defaults to username `admin`, password `postgres`, database `postgres`; override with `POSTGRES_USERNAME`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`. OpenAI calls are mocked, so no model credentials are needed for the unit/integration suite.

```shell
source .venv/bin/activate
python -m pytest                              # quick run
python -m pytest -s -vv --cov --cov-fail-under=85   # what CI runs; coverage gate is 85%
```

`pyproject.toml` already sets `testpaths = ["tests"]` and `pythonpath = ["src/backend"]`, so no `PYTHONPATH` juggling is needed.

Type checking (CI runs this and it must pass):

```shell
python -m ty check . --python-version 3.12
```

Lint and format (CI runs both; `--check` mode gates the PR):

```shell
ruff check .
ruff format . --check
```

End-to-end Playwright tests (slow, ~2+ minutes; needs a built frontend from step 6 above):

```shell
playwright install chromium --with-deps
python -m pytest tests/e2e.py --tracing=retain-on-failure
```

Snapshot tests: `tests/test_api_routes.py` compares chat responses against `tests/snapshots/`. If you intentionally change prompts, `ThoughtStep` contents, or response shapes, regenerate with `python -m pytest --snapshot-update` and review the diff before committing.

## Upgrading Python dependencies

Backend runtime dependencies live in `src/backend/pyproject.toml`; `src/backend/requirements.txt` is a generated lockfile (compiled by `uv`) — never hand-edit it.

1. Add or change the version constraint in `src/backend/pyproject.toml`.

2. Re-compile the lockfile from the `src/backend` directory (pin to 3.10, the minimum supported version):

    ```shell
    uv pip compile pyproject.toml -o requirements.txt --python-version 3.10
    ```

3. Reinstall and re-run the tests:

    ```shell
    python -m pip install -r src/backend/requirements.txt
    python -m pytest
    ```

Dev-only tools (ruff, ty, pytest, playwright, locust, …) go in `requirements-dev.txt`, which is unpinned and simply includes `-r src/backend/requirements.txt`. Evaluation dependencies go in `evals/requirements.txt` and are meant for a separate virtual environment (see below). Frontend dependencies: edit `src/frontend/package.json` and commit the updated `package-lock.json`.

## Release / build / deployment notes

Deployment is driven entirely by `azd`; do not add bespoke deploy scripts.

```shell
azd auth login
azd env new
azd up          # provision + deploy; can take 10+ minutes, do not cancel
```

Respect these mechanics when changing anything deployment-related:

- `azure.yaml` declares one service (`web`, `./src/backend`, Container Apps, remote Docker build) with a **prebuild hook** that runs `npm install && npm run build` in `src/frontend`. The backend image therefore expects `src/backend/static/` to be populated at build time.
- The `postprovision` hook runs `scripts/setup_postgres_database`, `setup_postgres_azurerole`, and `setup_postgres_seeddata` (`.sh` on POSIX, `.ps1` on Windows). If you add a setup step, add it to both variants and to `azure.yaml`.
- Bicep changes go in `infra/`; `bicep-security-scan.yaml` scans these files on PRs.

### Adding new azd environment variables

An azd environment variable is stored by the azd CLI per environment and is passed to `azd up`, configuring both provisioning options and application settings. When adding one, update all of:

1. `infra/main.parameters.json` — add the parameter with a Bicep-friendly name mapped to the new environment variable.
2. `infra/main.bicep` — add the parameter at the top and add it to the `webAppEnv` object.
3. `azure.yaml` — add the name under `pipeline.variables` so CI/CD passes it through.
4. The azd CI/CD workflow (`.github/workflows/azure-dev.yml`), if present in your checkout — add it under `env`, sourced from `secrets` for `@secure` Bicep parameters and from `vars` otherwise. This workflow is generated by `azd pipeline config` and is **not** currently committed in this repository, so skip this step if the file does not exist.

### Evaluation and load testing

Evaluations use a **separate** virtual environment because `evals/requirements.txt` pulls in `azure-ai-evaluation` and a git dependency:

```shell
python -m venv .evalenv && source .evalenv/bin/activate
python -m pip install uv && uv pip install -r evals/requirements.txt
python evals/generate_ground_truth.py         # regenerate ground truth (optional)
python evals/evaluate.py                      # needs the app running at eval_config.json target_url
python -m evaltools summary evals/results
python evals/safety_evaluation.py --target_url http://127.0.0.1:8000/chat --questions_per_category 1
```

Load testing (from the dev environment, with the app running): `locust`, then open `http://localhost:8089/`.

## Conventions & gotchas

- **Lint/format**: ruff only, `line-length = 120`, `target-version = "py39"`, rules `E,F,I,UP`, first-party import `fastapi_app`. Install the hooks with `pre-commit install`; `.pre-commit-config.yaml` runs `ruff --fix`, `ruff-format`, `check-yaml`, `end-of-file-fixer`, and `trailing-whitespace` (the last excludes `tests/snapshots`).
- **`main` is not currently lint-clean.** `ruff check .` reports 4 `E501` errors and `ruff format --check` wants to reformat 2 files, all in `src/backend/fastapi_app/setup_postgres_seeddata.py` and `setup_postgres_cars_seeddata.py` (the `attrs["embedding_3l"] = ...` / `attrs["embedding_nomic"] = ...` lines, ~lines 45–46). `python-code-quality.yaml` fails because of this. Do not assume your change caused it — run `ruff check .` before your edits to establish a baseline, and fix only what you touched unless asked to clean this up.
- **Async everywhere**: the engine, sessions, searchers, and OpenAI clients are all async. Use `AsyncSession` / `await`; never introduce a sync DB call into a request path.
- **Two embedding columns**: `embedding_3l` (1024 dims) and `embedding_nomic` (768 dims). The active column comes from `*_EMBEDDING_COLUMN` env vars via `common_parameters()`. If you add a model with a different dimensionality, you must add a column, an HNSW index in `postgres_models.py`, and a re-embedding path — you cannot reuse an existing column.
- **Two tables / two domains**: `items` (products) and `cars`. The advanced flow is constructed with both an `items` searcher and a `cars` searcher; if you add a table, wire a searcher through `dependencies.py`, `api_routes.py`, and `rag_advanced.py`, and add a `setup_postgres_*_seeddata.py` script.
- **Secrets**: never commit `.env` (it is gitignored; `.env.sample` is the template). Azure auth in deployed environments uses Managed Identity, and locally uses `AzureDeveloperCliCredential` via `azd auth login` — prefer credentials over keys, and never hardcode connection strings or keys.
- **Prompts are files, not string literals** (`fastapi_app/prompts/`), read at class definition time. Editing them changes snapshot tests.
- **Frontend build artifacts** land in `src/backend/static/`, which is gitignored (`.gitignore`: `static/`) and served by `frontend_routes.py`. It must be built locally before the backend or the Playwright tests will serve stale or missing assets — and never try to commit it.
- **Local chat errors without a model host are expected**: with `OPENAI_CHAT_HOST=azure` and no Azure login, chat requests fail with a credential error while `/items/{id}`, `/search`, and the frontend still work.
- **Doc drift**: `docs/evaluation.md` refers to `evals/generate_ground_truth_data.py` and `evals/generate.txt`; the real files are `evals/generate_ground_truth.py` and `evals/generate_prompt.txt`.
- Python version floor is 3.10 (CI matrix: 3.10, 3.11, 3.12 on Ubuntu/Windows, 3.11–3.12 on macOS), even though ruff's `target-version` says py39. Do not use 3.11+-only syntax.
- `src/backend/.venv/` may exist locally from a previous install; exclude it from searches and never edit files inside it.

## Validation checklist

Before opening a PR:

1. Virtual environment active and dependencies current (`python -m pip install -r requirements-dev.txt && python -m pip install -e src/backend`).
2. `ruff check .` and `ruff format .` applied — no new findings beyond the pre-existing seeddata `E501`/format baseline noted above.
3. `python -m ty check . --python-version 3.12` passes.
4. `python -m pytest -s -vv --cov --cov-fail-under=85` passes against a local pgvector-enabled Postgres.
5. Snapshots intentional: if `tests/snapshots/` changed, the diff is reviewed and explained in the PR description.
6. Frontend rebuilt (`cd src/frontend && npm run build`) and verified in the browser if you touched `src/frontend/`. The build output in `src/backend/static/` is gitignored — commit only the source changes.
7. No stray debug prints, `breakpoint()`, commented-out code, or hardcoded local paths; logging goes through `logging.getLogger("ragapp")`.
8. No secrets, keys, connection strings, or `.env` files staged.
9. If you added an env var: `.env.sample`, `infra/main.parameters.json`, `infra/main.bicep`, and `azure.yaml` `pipeline.variables` all updated.
10. If you added a dependency: `src/backend/pyproject.toml` edited and `src/backend/requirements.txt` recompiled with `uv pip compile`.
11. Docs updated (`README.md` and/or `docs/`) if behavior, setup steps, or commands changed.

## When to search

Trust this file. Run repository-wide searches only when the information you need is missing here, or when a command or path documented here turns out to be wrong or outdated — in which case fix this file as part of your change. For deeper background, `.github/copilot-instructions.md` has approximate command timings, `README.md` covers Azure deployment, and `docs/` covers evaluation, monitoring, load testing, and Entra auth.
