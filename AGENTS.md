# Repository Guidelines

## Project Structure & Module Organization
- `aila/`: Core Python package (LLM models, interfaces, analyzers). Key files: `legal_analyzer.py`, `llm_interface.py`, `llm_models.py`, `config.py`.
- `aila/api/`: FastAPI backend (`main.py`) with endpoints and CORS.
- `frontend/`: Minimal web UI and API wrapper. Entrypoint: `frontend/main.py`; static assets in `frontend/static/`; env bridging in `frontend/generate_config.py`.
- `tests/`: Pytest test suite scaffold (`tests/test_*.py`).
- `documentation/`, `scripts/`, `prompt_templates/`, `data/`, `cache/`, `results/`: Supporting assets; do not commit secrets or large raw data.

## Build, Test, and Development Commands
- Install deps: `poetry install --with api` (Python 3.12).
- Run API only: `uvicorn aila.api.main:app --reload`.
- Run frontend+API: `uvicorn frontend.main:app --host 0.0.0.0 --port 8000 --reload`.
- Type check: `pyright`.
- Lint/format: `ruff check .` and `ruff format .`.
- Docker (optional): `docker compose up --build -d`.

## Coding Style & Naming Conventions
- Python: 4-space indents, max line length 120, double quotes (ruff format). Target `py312`.
- Names: modules/files `snake_case.py`; functions/vars `snake_case`; classes `PascalCase`; constants `UPPER_SNAKE`.
- Types: follow `CLAUDE.md` — use built-in generics (`list`, `dict`, `tuple`) and `|` for unions; add clear annotations.
- Data models: prefer Pydantic `BaseModel` over dataclasses for simple containers; set `arbitrary_types_allowed=True` when storing SDK clients.
- Imports: keep unused imports out (ruff enforces). Group stdlib/third-party/local.
 - Time: use `time.monotonic()` for TTLs/timeouts to avoid wall-clock jumps.
 - Services vs data: use plain classes for services (locks, I/O, background tasks) and Pydantic models for data.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`; HTTP tests via `httpx` against FastAPI app.
- Layout: place tests under `tests/` as `test_*.py`. Mirror package structure where useful.
- Scope: unit-test `aila/*` modules and endpoint behavior; mock LLM/network calls.
- Run: `pytest` locally; add async tests with `pytest.mark.asyncio`.

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits (e.g., `feat:`, `fix:`, `refactor:`, `docs:`, `build:`, `chore:`) as used in history.
- PRs: include clear description, linked issues, and testing notes. For API/UI changes, add screenshots or `curl`/request examples. Update `README.md` when user-visible behavior changes.

## Security & Configuration Tips
- Secrets: never commit API keys. Use `.env` (see `.env.example`).
- Frontend config: generate `frontend/static/config.js` via `python frontend/generate_config.py` with `AILA_ENVIRONMENT` set.
- Logs: avoid printing secrets; validate via `/health` before testing endpoints.
