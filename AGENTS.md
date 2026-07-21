# AGENTS.md

## Project Rules

- The canonical implementation is the Python FastAPI app under `oncallagent/`.
- Keep the public API compatible with the original OnCallAgent routes: `GET /ping`, `POST /upload`, `POST /chat`, `POST /chatStream`, and `GET /plan`.
- Use `uv` for dependency management. Do not add `requirements.txt` or install project dependencies with ad-hoc `pip` commands.
- Keep operational runbooks under `docs/runbooks/`; keep development process documents under `docs/development/`.
- Keep the service usable without external Qdrant, Ollama, OpenAI, or Prometheus. External integrations must degrade cleanly for local tests.
- Add or update tests before changing behavior. Route behavior and response envelopes should be covered in `tests/`.

## Integration Gate

Before replacing or removing core Python integration code, keep these checkpoints verified:

- API compatibility tests cover all public routes and response envelopes.
- Python modules cover harness state/budget/evidence behavior.
- Python tools cover time, RAG retrieval, Prometheus alerts, and CLS MCP integration.
- Python indexing covers Markdown splitting, embedding average/normalization, and Qdrant write/retrieve integration.
- Python agent flow covers chat agent behavior and Plan-Execute-Replan behavior with real OpenAI-compatible model integration.
- External integration tests or documented manual checks pass for Prometheus, Qdrant, Ollama, OpenAI-compatible API, and optional CLS MCP.

## Commands

Install or sync dependencies:

```bash
/home/chg/.local/bin/uv sync
```

Run the test suite:

```bash
/home/chg/.local/bin/uv run pytest
```

Run the FastAPI service:

```bash
/home/chg/.local/bin/uv run uvicorn oncallagent.main:app --host localhost --port 8819
```

Check the app manually:

```bash
curl http://localhost:8819/ping
curl http://localhost:8819/plan
```

External integration checks:

```bash
curl http://localhost:9091/api/v1/alerts
curl http://localhost:6333/collections/oncallagent
curl http://localhost:11434/api/tags
curl -F "file=@docs/runbooks/resource-community-p95-latency.md" http://localhost:8819/upload
curl http://localhost:8819/plan
```
