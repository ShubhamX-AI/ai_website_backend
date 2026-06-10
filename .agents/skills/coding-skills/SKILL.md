---
name: coding-skills
description: Activates a senior software engineer mindset for ALL coding tasks. Use this skill whenever the user asks to write code, build a feature, scaffold a project, refactor existing code, fix a bug, or make any technical decision. Also triggers on phrases like "build me", "create a script", "help me code", or "set up a project".
---

# Senior Software Engineer Skill

You think like a senior engineer. That means one thing above all else:

> **Simple, clean code is always better than complex, clever code.**

---

## Before Writing Any Code

1. **Read first.** Check existing files and understand the project before touching anything.
2. **Read `README.md`** — it's the source of truth for structure, commands, and env vars.
3. **Check `CLAUDE.md`** — it contains per-project conventions and operational caveats.
4. **Plan the simplest solution.** Only add complexity when there's a real reason for it today.

---

## While Writing Code

- Names should explain themselves. No `tmp`, `data2`, or `handleStuff()`.
- One function = one job. If you need "and" to describe it, split it.
- Handle errors explicitly. Never silently ignore them.
- Delete anything that isn't used.
- Provide simple short one line comments to explain the code.
- **Do not output unnecessary code.** Only provide the code that is strictly required for the task.
- **Do not modify indentation or formatting of existing code/files unless absolutely necessary.**

---

## README.md — Always Keep It Current

- **README.md exists** — always read it before starting. Update the **entire** README to stay parallel with the latest code. This includes updating the folder structure, descriptions, usage instructions, and env var references.
- The folder tree in the README is the source of truth for where files live. Keep it in sync.

---

## Before Handing Back Any Code

Ask yourself:
- Can I delete anything without breaking it?
- Would a new developer understand this in 5 minutes?
- Does the README still reflect the real structure?

---

## This Project: Indusnet AI Website Backend

> A real-time voice agent built on LiveKit Agents. Two processes must both be running.

### Architecture — Two Separate Processes

| Process | Entry Point | Purpose |
|---------|------------|---------|
| FastAPI API | `src/api/main.py` | Health checks + LiveKit JWT token issuance + auth routes |
| LiveKit Agent Worker | `src/agents/session.py` | `entrypoint()` starts an `AgentSession` that loads `IndusNetAgent` |

Run both with `bash run_both.sh` or `docker compose up --build`.

### Request → Conversation Flow

1. Frontend calls `GET /api/getToken` → FastAPI creates a LiveKit room, dispatches the `indusnet` agent, returns JWT.
2. Frontend joins room with JWT.
3. LiveKit dispatches a job → `entrypoint()` in `session.py` runs.
4. `AgentSession` uses OpenAI Realtime (LLM + transcription) + Sarvam TTS.
5. `IndusNetAgent` handles conversation, calls tool functions, publishes data packets to frontend via LiveKit data channels.

Three background behaviors are wired via session event handlers (not in the agent class):
- **Filler phrases** (user-is-speaking context — GPT-4o-mini generates natural interjections)
- **Silence watchdog** (triggers idle timeout if no speech detected)
- **Background audio** (office ambience + typing sound mixed under the agent)

### Data Packet Bus

Agent ↔ frontend communicate via LiveKit room data packets. Two directions:

- **Frontend → Agent** (handled in `data_handler.py`): topics `user.context`, `user.location`, `ui.context`
- **Agent → Frontend** (published via `PacketHelperMixin`): topics `ui.flashcard`, `ui.contact_form`, `ui.job_application`, `ui.meeting_form`, `ui.location_request`, `ui.global_presense`, `ui.nearby_offices`, `ui.email_delivery`, `ui.whatsapp_delivery`, `user.details`

See `docs/architecture.md` for the full packet contract table.

### Source Layout — Where Things Go

```
src/
├── auth/                        # Auth system
│   ├── jwt.py                   # JWT create/verify
│   └── dependencies.py          # get_current_user, require_admin FastAPI deps
├── api/
│   ├── main.py                  # FastAPI app, CORS, route mounting
│   ├── models/
│   │   ├── api_schemas.py       # Pydantic request/response schemas
│   │   └── db_schemas.py        # MongoDB User model
│   └── routes/
│       ├── health.py            # GET /health
│       ├── token.py             # GET /api/getToken
│       └── auth.py              # POST /auth/login, GET /auth/google, etc.
├── agents/
│   ├── base.py                  # BaseAgent
│   ├── session.py               # AgentSession + entrypoint() — START HERE for session changes
│   ├── prompts/
│   │   └── humanization.py      # TTS humanization prompts
│   └── indusnet/                # The voice agent — START HERE for agent changes
│       ├── agent.py             # IndusNetAgent (assembled via multiple inheritance)
│       ├── prompts.py           # System prompt
│       ├── state.py             # AgentState model
│       ├── constants.py         # Topic constants for data packets
│       ├── handlers/
│       │   └── data_handler.py  # DataHandlerMixin (frontend→agent packets)
│       ├── helpers/
│       │   ├── filler.py        # Filler phrase generation
│       │   ├── packet.py        # PacketHelperMixin (agent→frontend packets)
│       │   ├── silence.py       # Silence watchdog + idle shutdown
│       │   └── vector_search.py # VectorSearchHelperMixin
│       └── tools/               # ADD NEW TOOLS HERE (one mixin per file)
│           ├── knowledge.py     # KnowledgeToolsMixin
│           ├── ui_publisher.py  # UIPublisherToolsMixin
│           ├── forms.py         # FormToolsMixin
│           ├── meeting.py       # MeetingToolsMixin
│           ├── location.py      # LocationToolsMixin
│           ├── email.py         # EmailToolsMixin
│           ├── whatsapp.py      # WhatsAppToolsMixin
│           ├── user.py          # UserToolsMixin
│           └── endcall.py       # EndCallToolsMixin
├── core/
│   ├── config.py                # ALL env vars loaded here — never read .env directly
│   ├── database.py              # Motor async MongoDB client
│   └── logger.py                # Shared rotating-file logger
└── services/                    # ADD NEW EXTERNAL INTEGRATIONS HERE
    ├── livekit/
    │   └── livekit_svc.py       # Room creation, agent dispatch, JWT
    ├── llm/
    │   ├── client.py            # LLM client
    │   ├── parsers.py           # Response parsers
    │   ├── prompts.py           # Prompt templates
    │   ├── media_assets.py      # Media asset mappings
    │   └── ui_agent.py          # GPT-4o-mini flashcard generation
    ├── vectordb/
    │   ├── vectordb_svc.py      # ChromaDB similarity search
    │   ├── chroma_db/           # company_knowledge persistent store
    │   └── chroma_db_mem0/      # mem0 cross-session memory
    ├── mail/
    │   ├── calender_invite.py   # Calendar invite via SMTP
    │   ├── context_email.py     # Context email delivery
    │   ├── submission_receipt.py# Form submission receipt
    │   └── templates/
    │       ├── context_email.html
    │       └── submission_receipt.html
    ├── whatsapp/
    │   └── context_whatsapp.py  # Context delivery via Meta API
    ├── search/
    │   └── searxng_svc.py       # Web + image search
    └── map/googlemap/
        └── services.py          # Distance/route calculation
```

### IndusNetAgent Composition

`IndusNetAgent` in `agent.py` is assembled entirely through multiple inheritance (MRO order matters):

```
AgentState → PacketHelperMixin → VectorSearchHelperMixin → DataHandlerMixin
→ [Tool Mixins: Knowledge, UIPublisher, Forms, Location, Meeting, Email, WhatsApp, User, EndCall]
→ BaseAgent
```

All tool functions decorated with `@function_tool` are auto-registered by LiveKit from the mixin classes. Never put tool logic directly in `IndusNetAgent` — add a mixin in `tools/`.

### Adding a New Agent Tool

1. Create `src/agents/indusnet/tools/<tool_name>.py`
2. Define a mixin class with methods decorated with `@function_tool`
3. Add the mixin to `IndusNetAgent`'s MRO in `agent.py` (before `BaseAgent`)
4. Follow existing tool files as the pattern — do not invent a new pattern
5. Add any new env vars to `.env` and load them in `src/core/config.py`

### Adding a New Service / Integration

- Create `src/services/<category>/<service_name>.py`
- Expose a clean client or function — no business logic in the service layer
- Add any new env vars to `.env.example` and load them in `src/core/config.py`

### Adding a New API Route

1. Create `src/api/routes/<name>.py` with a FastAPI `APIRouter`
2. Mount the router in `src/api/main.py`
3. Add any new Pydantic schemas in `src/api/models/api_schemas.py`

### Tech Stack Constraints

- **Python 3.12+** — use modern syntax (match/case, `|` unions, etc.)
- **uv** for dependency management — `uv add <package>`, not pip
- **LiveKit Agents framework** — follow its session/worker lifecycle; do not bypass it
- **OpenAI Realtime API** (`livekit.plugins.openai.realtime`) for LLM + transcription; **GPT-4o-mini** for async tasks
- **Sarvam TTS** (not Cartesia) — configured in `session.py`
- **ChromaDB** for vector search — embeddings use `text-embedding-3-small`
- **Motor** async MongoDB driver — do not use synchronous pymongo for new database code
- **Alembic** is declared as a dependency but **not configured** — no migration setup exists; manage DB schema manually or via `init_db()` in `main.py`

### Critical Things Not to Break

- LiveKit session lifecycle in `src/agents/session.py` — audio pipeline timing, background audio mixing, filler/silence wiring
- ChromaDB collection names and embedding dimensions — changing these breaks the persisted knowledge base
- `.env.example` variable names — services depend on exact key names loaded in `config.py`
- Docker service names in `docker-compose.yml` — used for inter-container networking
- CORS is open (`*`) in `src/api/main.py` — tighten before production; do not loosen further

### Environment & Config

- All secrets and feature flags live in `.env`
- Access them **only** via `src/core/config.py` (the `settings` singleton) — never `os.getenv()` directly in feature code
- When adding a new integration, add its env var to `.env.example` (grouped and tagged `[REQUIRED]`/`[DEFAULT]`/`[FEATURE]`)

### Testing

- **No test suite currently exists.** Do not assume `pytest` or any test framework is set up.
- When writing new code, add tests only if explicitly asked. Prefer manual validation via `python -m src.agents.session dev` or `python -m src.api.main`.

### Deployment Caveats

- `server_run.py` runs Gunicorn with **1 worker** — ChromaDB file locks and in-process state assume single-worker. Don't scale workers without externalizing those stores.
- ChromaDB is file-persisted locally; not suitable for multi-instance deployments without changes.
- Logs are written to `logs/app.log` via rotating file handler. `setup_logging()` is called once at process startup (both `main.py` and `session.py`).