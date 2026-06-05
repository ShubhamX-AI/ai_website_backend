# Indusnet AI Website Backend

LiveKit-based backend for an Indus Net website voice assistant.
It runs two processes:
- A FastAPI service for health checks and LiveKit token issuance.
- A LiveKit agent worker for real-time voice conversations and tool execution.

## Quick Start

Five steps to a running stack. Both processes must be up.

```bash
# 1. Clone + install
git clone <repo-url> && cd ai_website_backend
uv sync
source .venv/bin/activate

# 2. Create .env from template, then fill in values
cp .env.example .env
#    Minimum to boot: LIVEKIT_*, OPENAI_API_KEY, CARTESIA_API_KEY, MONGODB_URL, SECRET_KEY
#    Generate SECRET_KEY: openssl rand -hex 32
#    Every var is grouped + annotated [REQUIRED]/[DEFAULT]/[FEATURE] in .env.example

# 3. Seed an admin user (MongoDB must be reachable)
python scripts/create_admin.py

# 4. Start API server  (terminal 1)
python -m src.api.main          # dev, http://localhost:8000

# 5. Start agent worker (terminal 2)
python -m src.agents.session dev
```

Or run both backgrounded: `bash run_both.sh`. Docker: `docker compose up --build`.

Health check: `curl http://localhost:8000/health` → `ok`.

Minimum env to boot (core runtime + auth):

| Var | Why |
|---|---|
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` / `LIVEKIT_URL` | Room creation, JWT, agent dispatch |
| `OPENAI_API_KEY` | Realtime LLM + transcription + embeddings |
| `CARTESIA_API_KEY` | TTS |
| `MONGODB_URL` / `MONGODB_DB_NAME` | User store, auth |
| `SECRET_KEY` | JWT signing |

Tool features (search, email, WhatsApp, maps) need extra env — see [Required for specific tools/features](#required-for-specific-toolsfeatures). Missing those vars degrades only that tool, not boot.

## What This Project Does

- Runs a realtime voice agent (`indusnet`) using LiveKit Agents.
- Uses OpenAI realtime for conversation and Cartesia for TTS.
- **Auth system** with email/password login, Google OAuth, role-based access (admin/client), and client access windows.
- Provides tool-driven flows for:
  - Knowledge base search (ChromaDB)
  - Internet search and image search (SearXNG)
  - UI flashcard publishing and recall
  - Contact form and job application preview/submit
  - Meeting invite preview/send
  - Location request + distance/route calculation
  - Context delivery via email and WhatsApp
  - Graceful call ending

## Runtime Flow

1. Client calls `GET /api/getToken`.
2. API creates/uses a LiveKit room and dispatches the `indusnet` agent.
3. Client joins the room with the returned JWT.
4. Agent worker (`src/agents/session.py`) starts an `AgentSession` and loads `IndusNetAgent`.
5. `IndusNetAgent` executes tools based on conversation intent and sends UI/data packets to frontend topics.

## Architecture Docs

Full docs site builds with `mkdocs build` and serves at `/documentation`.

- [Docs Home](docs/index.md)
- [Feature List](docs/features.md)
- [Architecture Overview](docs/architecture.md)
- [Auth System](docs/auth.md)
- [Feature Data Flows](docs/data-flows.md)
- [Tools Reference](docs/tools.md)

## Project Structure

```text
.
├── README.md
├── .env.example               # annotated env template — copy to .env
├── docs/
│   ├── architecture.md
│   ├── auth.md
│   ├── data-flows.md
│   └── tools.md
├── pyproject.toml
├── server_run.py
├── run_both.sh
├── docker-compose.yml
├── Dockerfile
├── assets/
│   └── audio/
│       ├── office-ambience_48k.wav
│       └── typing-sound_48k.wav
└── src/
    ├── auth/
    │   ├── jwt.py              # JWT create/verify
    │   └── dependencies.py     # get_current_user, require_admin FastAPI deps
    ├── api/
    │   ├── main.py
    │   ├── models/
    │   │   ├── api_schemas.py  # Auth request/response Pydantic schemas
    │   │   └── db_schemas.py   # User DB model
    │   └── routes/
    │       ├── health.py
    │       ├── token.py
    │       └── auth.py         # /auth/login, /auth/register, /auth/google, /auth/google/callback, /auth/logout
    ├── agents/
    │   ├── base.py
    │   ├── session.py
    │   ├── prompts/
    │   │   └── humanization.py
    │   └── indusnet/
    │       ├── agent.py
    │       ├── prompts.py
    │       ├── state.py
    │       ├── constants.py
    │       ├── handlers/
    │       │   └── data_handler.py
    │       ├── helpers/
    │       │   ├── filler.py
    │       │   ├── packet.py
    │       │   ├── silence.py
    │       │   └── vector_search.py
    │       └── tools/
    │           ├── knowledge.py
    │           ├── ui_publisher.py
    │           ├── forms.py
    │           ├── meeting.py
    │           ├── location.py
    │           ├── email.py
    │           ├── whatsapp.py
    │           ├── user.py
    │           └── endcall.py
    ├── core/
    │   ├── config.py
    │   ├── database.py         # Motor async MongoDB client
    │   └── logger.py
    └── services/
        ├── livekit/
        │   └── livekit_svc.py
        ├── llm/
        │   ├── client.py
        │   ├── parsers.py
        │   ├── prompts.py
        │   ├── media_assets.py
        │   └── ui_agent.py
        ├── mail/
        │   ├── calender_invite.py
        │   ├── context_email.py
        │   ├── submission_receipt.py
        │   └── templates/
        │       ├── context_email.html
        │       └── submission_receipt.html
        ├── map/googlemap/
        │   └── services.py
        ├── search/
        │   └── searxng_svc.py
        ├── vectordb/
        │   ├── vectordb_svc.py
        │   ├── chroma_db/
        │   └── chroma_db_mem0/
        └── whatsapp/
            └── context_whatsapp.py
```

## Prerequisites

- Python `>=3.12`
- `uv` (recommended) or `pip`
- MongoDB instance (local or Atlas)
- LiveKit server credentials
- OpenAI API key
- Cartesia API key

## Environment Variables

Copy the annotated template and fill it in:

```bash
cp .env.example .env
```

`.env.example` lists **every** variable the code reads (from `src/core/config.py`), grouped and tagged:
- `[REQUIRED]` — no usable default; must set
- `[DEFAULT]` — has a working default; override only if needed
- `[FEATURE]` — only needed for that tool; missing it disables only that feature, not boot

The sections below mirror the template.

### Required for core runtime

```env
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
LIVEKIT_URL=wss://...
OPENAI_API_KEY=...
CARTESIA_API_KEY=...
```

### Required for auth

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ai_website

# JWT signing key — generate with: openssl rand -hex 32
SECRET_KEY=...

# Google OAuth (register at console.cloud.google.com)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
NEXTJS_CALLBACK_URL=http://localhost:3000/api/auth/google/callback

# Domain whose Google accounts become admin (e.g. yourcompany.com)
ADMIN_DOMAIN=yourcompany.com

# Session / access window durations (hours)
CLIENT_SESSION_HOURS=4
CLIENT_ACCESS_WINDOW_HOURS=4
```

### Required for specific tools/features

```env
# Internet search tool
SEARXNG_BASE_URL=http://127.0.0.1:8090

# Email tools (context email + submission receipts + calendar invites)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@example.com
SENDER_PASSWORD=your-app-password

# WhatsApp context delivery
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_TEMPLATE_NAME=utility_agui_agent

# Location/directions tools
GOOGLE_API_KEY=...
```

### Optional

```env
PORT=8000
EMAIL_SUMMARY_MODEL=gpt-4o-mini
```

## Installation

### Using uv (recommended)

```bash
uv sync
source .venv/bin/activate
```

### Using pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running Locally

### API server

```bash
# Dev
python -m src.api.main

# Prod-style
python server_run.py
```

API base URL: `http://localhost:8000`

### Agent worker

```bash
# Dev mode
python -m src.agents.session dev

# Start mode
python -m src.agents.session start
```

### Run both together

```bash
bash run_both.sh
```

`run_both.sh` now performs a startup dependency preflight for `requests`, `urllib3`, and `livekit.agents`.
If the check fails, it automatically runs `uv sync --frozen`, then a targeted reinstall of core runtime packages, and retries before starting the API and agent.
If recovery still fails, run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen --reinstall
```

## Docker

`docker-compose.yml` defines two services:
- `api`: runs `python server_run.py`
- `agent`: runs `python -m src.agents.session start`

Start:

```bash
docker compose up --build
```

## API Endpoints

### Health

```http
GET /health
```

Response: plain text `ok`

### Auth

```http
POST /auth/login
# Body: { "email": "...", "password": "..." }
# 200 → { token, role, expires_at }
# 401 → wrong credentials
# 403 → client access window expired

GET /auth/google
# Redirects browser to Google consent screen

GET /auth/google/callback
# Google redirects here with ?code=... → FastAPI issues JWT → redirects to Next.js

POST /auth/logout
# Returns { "success": true }

POST /auth/register
# Body: { "admin_email": "...", "admin_password": "...", "email": "...", "password": "...", "role": "client" }
# Creates a new user. Gated by an existing admin's credentials (admin_email + admin_password).
# role defaults to "client"; accepts "admin" | "client".
# 200 → { "success": true, "message": "Registration successful." }
# 400 → email already registered / admin not found / invalid admin password
```

See [Auth System docs](docs/auth.md) for full flow, roles, and frontend integration guide.

### LiveKit token

```http
GET /api/getToken?user_id=<uuid>&name=guest&email=optional@domain.com&agent=indusnet&room=optional-room
```

Query params:
- `user_id` (required)
- `name` (optional, default `guest`)
- `email` (optional)
- `agent` (optional, must be `indusnet`)
- `room` (optional; auto-created if omitted)

Returns: JWT token as plain text.

## Agent Tools (Current)

- `search_indus_net_knowledge_base(question)`
- `search_internet_knowledge(question)`
- `publish_ui_stream(user_input, agent_response)`
- `recall_and_republish_ui_content(agent_response)`
- `publish_global_presence(user_input="global presence")`
- `publish_nearby_offices(offices)`
- `get_ui_history()`
- `get_user_info(user_name, user_email="", user_phone="")`
- `preview_contact_form(...)`
- `submit_contact_form(...)`
- `preview_job_application(...)`
- `submit_job_application(...)`
- `preview_meeting_invite(...)`
- `schedule_meeting(...)`
- `request_user_location()`
- `calculate_distance_to_destination(destination, origin_place?, travel_mode?)`
- `send_context_email(recipient_email="", screens_back=0)`
- `send_context_whatsapp(recipient_phone="", screens_back=0)`
- `end_call()`

## Model Usage (Current)

- Conversation LLM: `gpt-realtime`
- Realtime transcription: `gpt-4o-mini-transcribe`
- UI flashcard generation: `gpt-4o-mini`
- Filler phrase generation: `gpt-4o-mini`
- TTS: Cartesia `sonic-3`
- Embeddings: `text-embedding-3-small`

## Notes and Operational Caveats

- CORS is currently configured as open (`*`) in `src/api/main.py`; tighten for production.
- MongoDB `users` collection index on `email` (unique) is created automatically on startup via `init_db()`.
- First admin: seed via `scripts/create_admin.py` (no admin exists yet to authorize `/auth/register`). After that, create more users through `POST /auth/register` (requires existing admin credentials) or insert directly into MongoDB. See [Auth System docs](docs/auth.md).
- `SECRET_KEY` must be set in production. Generate with `openssl rand -hex 32`.
- `SEARXNG_BASE_URL` falls back to a hosted default (`http://13.126.71.22:4000/`) if unset; used for both web search and flashcard image search. Point it at your own reachable instance (e.g. `http://127.0.0.1:8090`).
- Vector stores are persisted locally under `src/services/vectordb/chroma_db*`.
- Startup script self-healing depends on `uv` being available in your shell PATH.
- Logs are written to `logs/app.log` via rotating file handler.

## Troubleshooting

### `getToken` fails

- Verify LiveKit credentials and URL.
- Ensure agent worker is running and can connect to LiveKit.

### Agent starts but tools fail

- Check missing feature-specific env vars (`GOOGLE_API_KEY`, SMTP vars, WhatsApp vars, `SEARXNG_BASE_URL`).

### No UI flashcards

- Verify `OPENAI_API_KEY` and that frontend is subscribed to data packet topics.

### Email or WhatsApp delivery fails

- Confirm sender credentials / Meta credentials and template setup.
- Review `logs/app.log` for detailed provider errors.

## License

Proprietary - Indus Net Technologies
