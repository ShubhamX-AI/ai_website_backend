# Indusnet AI Website Backend

A LiveKit-powered AI voice agent backend for Indus Net Technologies website, providing intelligent conversational experiences with dynamic UI flashcard generation and interactive contact forms.

## Features

- **Voice AI Agent**: Real-time voice interaction using LiveKit Agents with GPT-4 Realtime
- **Dynamic UI Generation**: Generates 1-4 visual flashcards synchronized with voice responses using OpenAI o4-mini
- **Smart Deduplication**: UI context synchronization prevents duplicate content from being displayed
- **Knowledge Base Search**: Vector database powered by ChromaDB with Indus Net company information
- **Contact Form Workflow**: Two-step preview and submit process for user inquiries
- **User Context Management**: Tracks user identity, email, and phone with dynamic prompt updates
- **Multi-language Support**: English, Hindi, and Bengali with natural code-mixing (Hinglish/Banglish)
- **Background Audio**: Ambient office sounds and typing effects during processing

## Architecture

```
src/
├── agents/              # AI Agent logic
│   ├── indusnet/       # Indusnet-specific agent implementation
│   │   ├── agent.py    # Main agent with tools and data handling
│   │   └── prompts.py  # Voice agent system prompt
│   ├── prompts/        # Shared prompts (TTS humanization)
│   ├── base.py         # Base agent class
│   ├── factory.py      # Agent factory pattern
│   └── session.py      # LiveKit session management
├── api/                # FastAPI REST endpoints
│   ├── routes/         # API route handlers
│   │   ├── token.py    # Room token generation
│   │   └── health.py   # Health check endpoint
│   └── models/         # Pydantic schemas
├── core/               # Core configuration
│   ├── config.py       # Environment settings
│   └── logger.py       # Logging setup
└── services/           # External service integrations
    ├── livekit/        # LiveKit room & token management
    ├── openai/         # OpenAI integration for UI generation
    │   └── indusnet/   # Indusnet UI agent
    │       ├── openai_scv.py        # Streaming UI generation
    │       └── ui_system_prompt.py  # UI flashcard prompt
    ├── vectordb/       # ChromaDB vector knowledge base
    └── memory/         # User context and memory management
```

## Prerequisites

- Python 3.12+
- UV package manager (recommended) or pip
- LiveKit server (self-hosted or cloud)
- OpenAI API key
- Cartesia API key

## Environment Variables

Create a `.env` file in the project root:

```env
# LiveKit Configuration
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_URL=wss://your-livekit-server.com

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Cartesia TTS Configuration
CARTESIA_API_KEY=your_cartesia_api_key

# Server Configuration
PORT=8000
```

## Installation

### Using UV (Recommended)

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

## Running the Application

### 1. Start the API Server

```bash
# Development mode
python -m src.api.main

# Production mode (with Gunicorn)
python server_run.py
```

The API server will start on `http://localhost:8000`

### 2. Start the LiveKit Agent

```bash
# Development mode with auto-reload
python -m livekit.agents.cli dev

# Production mode
python -m livekit.agents.cli start
```

## API Endpoints

### Health Check

```
GET /health
```

### Generate Room Token

```
GET /api/getToken?name=guest&agent=indusnet&room=optional-room-name
```

**Query Parameters:**

- `name`: User identity (default: "guest")
- `agent`: Agent type (must be "indusnet")
- `room`: Optional room name (auto-generated if not provided)

**Response:** JWT token for LiveKit room access

## Agent Features

### Voice Interaction

- Real-time conversation with GPT-4 Realtime model
- Sonic-3 TTS by Cartesia for natural voice output with humanization prompts
- Automatic transcription and context-aware responses
- Noise cancellation support for SIP calls
- Multi-language support (English, Hindi, Bengali) with natural code-mixing

### Agent Tools

#### 1. Knowledge Base Search

- **Tool**: `search_indus_net_knowledge_base(question: str)`
- Searches the official Indus Net knowledge base for company information
- Returns formatted markdown results with metadata
- Fetches top 5 most relevant documents using vector similarity

#### 2. UI Flashcard Publishing

- **Tool**: `publish_ui_stream(user_input: str, agent_response: str)`
- Generates 1-4 visual flashcards using OpenAI o4-mini
- Runs asynchronously to avoid delaying voice responses
- Streams flashcards in real-time to the frontend
- Includes deduplication based on active UI elements

#### 3. User Information Management

- **Tool**: `get_user_info(user_name: str, user_email: str, user_phone: str)`
- Captures and syncs user identity to the system
- Updates agent instructions dynamically with user context
- Publishes user details to frontend via data packets

#### 4. Contact Form Preview

- **Tool**: `preview_contact_form(user_name, user_email, user_phone, contact_details)`
- Displays contact form on UI for user review
- Requires all fields (name, email, phone, reason) before calling
- Agent asks follow-up questions to understand user's specific needs
- Waits for user confirmation before submission

#### 5. Contact Form Submission

- **Tool**: `submit_contact_form(user_name, user_email, user_phone, contact_details)`
- Submits contact form after user confirmation
- Only called after `preview_contact_form` and explicit user approval
- Sends confirmation message to user

### UI Synchronization

- Generates 1-4 flashcards per interaction using structured streaming
- Smart deduplication: tracks active UI elements to prevent redundant content
- Supports multiple visual intents (neutral, urgent, success, warning, processing, cyberpunk)
- Dynamic media from curated asset map or stock sources (Pixabay/Pexels)
- UI context synchronization: viewport, theme, screen size, max visible cards
- Stream grouping with `stream_id` and `card_index` for proper ordering

### Knowledge Base

- Pre-loaded Indus Net Technologies information
- Vector similarity search using ChromaDB
- Text embeddings via OpenAI `text-embedding-3-small`
- Excel data source: `src/services/vectordb/chroma_db/website_extracted_data.xlsx`
- Formatted results with dynamic metadata extraction

## Project Structure Details

### Agent Types

- **IndusNetAgent**: Main agent for Indus Net website interactions
  - Knowledge base search tool
  - UI flashcard publishing tool (with streaming and deduplication)
  - Contact form preview and submission tools
  - User information management tool
  - Multi-language support (English, Hindi, Bengali with code-mixing)
  - Dynamic instruction updates based on user and UI context

### UI Flashcard Schema

Cards are generated with the following properties:

- `type`: Always "flashcard"
- `id`: Semantic kebab-case identifier for deduplication (e.g., "cloud-migration-services")
- `title`: Card heading (5-10 words, scannable)
- `value`: Main content (1-3 sentences, markdown supported)
- `visual_intent`: Color theme (neutral, urgent, success, warning, processing, cyberpunk)
- `animation_style`: Entry animation (slide, pop, fade, flip, scale)
- `icon`: Lucide icon reference with type and fallback
- `media`: Images/videos from curated asset map or stock sources (Pixabay/Pexels)
  - Prioritizes curated assets for known entities (CEO, offices, partners, case studies)
  - Falls back to IT/software-themed stock media with contextual queries
- `layout`: Card layout type (default, horizontal, centered, media-top)
- `size`: Card size (sm, md, lg) - lg for primary card, md for supporting
- `accentColor`: Theme color (emerald, blue, amber, indigo, rose, violet, orange, zinc)
- `stream_id`: UUID for grouping cards in the same response
- `card_index`: Position in the stream for ordering

## Development

### File Naming Conventions

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/Variables: `snake_case`
- Services: `*_svc.py` suffix

### Key Files

- `src/agents/indusnet/agent.py`: Main agent logic with tools and data handling
- `src/agents/indusnet/prompts.py`: Voice agent system prompt (v4.0)
- `src/agents/prompts/humanization.py`: TTS humanization prompt for Cartesia
- `src/services/openai/indusnet/ui_system_prompt.py`: UI flashcard generation prompt
- `src/services/openai/indusnet/openai_scv.py`: OpenAI o4-mini streaming service for UI
- `src/agents/session.py`: LiveKit session entry point
- `src/api/routes/token.py`: Room token generation endpoint
- `src/services/vectordb/vectordb_svc.py`: ChromaDB vector search service

## Deployment

### Docker

See `docker-compose.yml` for containerized deployment.

### Production Considerations

- Use `server_run.py` with Gunicorn for production API server
- Configure proper CORS origins in `src/api/main.py`
- Set up reverse proxy (Nginx/Caddy) for HTTPS
- Monitor LiveKit agent process with systemd or supervisor
- Implement rate limiting for token generation endpoint

## Troubleshooting

### Import Errors

- Ensure virtual environment is activated
- Run `uv sync` or `pip install -e .` to install dependencies

### LiveKit Connection Issues

- Verify `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`
- Check LiveKit server status
- Ensure firewall allows WebSocket connections

### Agent Not Responding

- Check OpenAI API key is valid
- Verify Cartesia API key for TTS
- Review logs in `src/core/logger.py` output

## License

Proprietary - Indus Net Technologies

## Support

For issues or questions, contact the Indus Net Technologies development team.
