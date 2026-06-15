# AGENTS.md

Read `CLAUDE.md` first for full architecture, commands, and config reference. This file only flags things an agent is likely to miss.

## TL;DR Must-Knows

- **Two processes** — API (`python -m src.api.main`) + Agent worker (`python -m src.agents.session dev`). Both must run.
- **No tests exist** — verify by starting both services and hitting `GET /health`.
- **No linter/formatter** — only ruff cache artifacts; no config.
- **Alembic migrations exist but are inert** — auth uses Motor/MongoDB directly.
- **CORS is open (`*`)** — tighten before production.

## Agent Worker (Unusual Setup)

Not a regular Python app — it's a LiveKit Agents worker that connects to a LiveKit server:

```
python -m src.agents.session dev              # dev (hot-reload)
python -m src.agents.session start             # prod
python -m src.agents.session download-files    # prefetch models (Docker build)
```

**Three hidden behaviors** wired via event handlers in `session.py`, not in the agent class:
1. **Filler phrases** — gpt-4o-mini generates acknowledgements while user speaks
2. **Silence watchdog** — auto-disconnect on idle
3. **Background audio** — office ambience + typing sounds looped under agent voice

## IndusNetAgent MRO (Order Matters)

Multiple inheritance order in `src/agents/indusnet/agent.py`:

```
AgentState → PacketHelperMixin → VectorSearchHelperMixin → DataHandlerMixin
→ [Knowledge, UIPublisher, Forms, Location, Meeting, Email, WhatsApp, User, EndCall]
→ BaseAgent
```

- Tools live in `src/agents/indusnet/tools/` as mixins with `@function_tool` decorators.
- Never put tool logic directly in `IndusNetAgent` — add a mixin.

## Frontend Communication

Agent ↔ frontend sends **LiveKit room data packets** (not HTTP). Topics are listed in `CLAUDE.md` §Data Packet Bus and `docs/architecture.md`.

## Constraints

- ChromaDB is file-persisted at `src/services/vectordb/chroma_db*` → single-worker only.
- `server_run.py` hard-codes 1 Gunicorn worker. Do not scale workers without externalizing ChromaDB.
- Language switching is **prompt-driven** (§9 of system prompt), not a TTS model swap. TTS stays en-IN always.

## Quick Ref

| Action | Command |
|---|---|
| Install | `uv sync && source .venv/bin/activate` |
| Both services | `bash run_both.sh` |
| Docker | `docker compose up --build` |
| Deploy | `bash deploy.sh` (port 3011) |
| Admin seed | `python scripts/create_admin.py` |
| MkDocs build | `mkdocs build` (served at `/documentation`) |
| SECRET_KEY | `openssl rand -hex 32` |
