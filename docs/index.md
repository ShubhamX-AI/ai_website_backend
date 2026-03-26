# AGUI Backend

Real-time voice agent backend architecture for AI-powered website assistants. Built on [LiveKit Agents](https://docs.livekit.io/agents/) with OpenAI Realtime and Cartesia TTS.

The `indusnet` agent is the reference implementation of this architecture, deployed for **Indus Net Technologies**.

---

## What This System Does

A visitor to a website can start a voice conversation directly in the browser. This backend handles everything behind that interaction:

1. Issues a LiveKit room token via a FastAPI endpoint so the browser can join a room.
2. Spawns a voice agent in the room that listens and responds using OpenAI's realtime LLM.
3. Executes **12 specialized tools** based on conversation intent — searching the knowledge base, rendering interactive UI cards, collecting form submissions, booking meetings, sharing directions, and delivering summaries by email or WhatsApp.
4. Publishes structured data packets over LiveKit's data channel so the frontend can render UI components in sync with the voice response.

The two runtime processes — FastAPI API server and LiveKit Agent Worker — run independently and can be deployed as separate Docker containers.

---

## Quick Navigation

| Section | What you'll find |
|---|---|
| [Architecture](architecture.md) | System context diagram, bootstrap sequence, runtime interaction loop, data packet bus contracts |
| [Data Flows](data-flows.md) | End-to-end Mermaid sequence diagrams for all 9 feature flows |
| [Tools Reference](tools.md) | Tool catalog, preconditions/postconditions, topic contracts, failure modes |

---

## Runtime Stack

| Layer | Technology |
|---|---|
| Voice transport | LiveKit (WebRTC rooms + data channel) |
| Conversation LLM | OpenAI Realtime (`gpt-4o-realtime`) |
| Transcription | OpenAI (`gpt-4o-mini-transcribe`) |
| Text-to-speech | Cartesia (`sonic-3`) |
| Knowledge retrieval | ChromaDB vector store + `text-embedding-3-small` |
| Web / image search | SearXNG (self-hosted) |
| UI card generation | OpenAI (`gpt-4o-mini`) |
| Email delivery | SMTP (configurable) |
| WhatsApp delivery | Meta Graph API |
| Directions | Google Routes API |
| Memory (flashcard recall) | Mem0 on ChromaDB |

---

## Tool Capabilities at a Glance

The agent selects tools automatically based on conversation context. All tools live under `src/agents/indusnet/tools/`.

??? info "Knowledge and Search"
    | Tool | What it does |
    |---|---|
    | `search_indus_net_knowledge_base` | Semantic search over the company knowledge vector store |
    | `search_internet_knowledge` | Live web search via SearXNG for questions outside the knowledge base |

??? info "UI Flashcards"
    | Tool | What it does |
    |---|---|
    | `publish_ui_stream` | Streams AI-generated flashcard cards to the frontend over `ui.flashcard` |
    | `recall_and_republish_ui_content` | Replays previously shown cards from Mem0 memory |
    | `publish_global_presence` | Renders a global office location panel |
    | `publish_nearby_offices` | Renders nearby office cards based on user location |
    | `get_ui_history` | Returns a server-side log of what has been shown |

??? info "Forms and Scheduling"
    | Tool | What it does |
    |---|---|
    | `preview_contact_form` / `submit_contact_form` | Guided contact submission with email receipt |
    | `preview_job_application` / `submit_job_application` | Guided job application with email receipt |
    | `preview_meeting_invite` / `schedule_meeting` | Calendar invite preview and ICS email delivery |

??? info "Location and Directions"
    | Tool | What it does |
    |---|---|
    | `request_user_location` | Requests browser geolocation; waits for response on `user.location` topic |
    | `calculate_distance_to_destination` | Google Routes call; publishes a map polyline to the frontend |

??? info "Context Delivery"
    | Tool | What it does |
    |---|---|
    | `send_context_email` | Emails a summary of the current or prior screen context to the user |
    | `send_context_whatsapp` | Sends the same summary via WhatsApp template message |

??? info "Session"
    | Tool | What it does |
    |---|---|
    | `get_user_info` | Echoes confirmed user identity to the frontend on `user.details` |
    | `end_call` | Gracefully shuts down the session with a farewell |

---

## API Entry Point

The only HTTP endpoint a frontend needs:

```
GET /api/getToken?user_id=<uuid>&name=guest&agent=indusnet
```

Returns a plain-text LiveKit JWT. The frontend uses this token to join the room. The agent worker is dispatched automatically as part of token issuance.

See [Architecture → Bootstrap Sequence](architecture.md#bootstrap-sequence) for the full flow.

---

## Data Packet Bus

All real-time UI updates flow through LiveKit's data channel, not HTTP. The agent publishes to named topics; the frontend subscribes and renders components accordingly.

**Frontend-subscribed topics:** `ui.flashcard`, `ui.contact_form`, `ui.job_application`, `ui.meeting_form`, `ui.location_request`, `ui.global_presense`, `ui.nearby_offices`, `ui.email_delivery`, `ui.whatsapp_delivery`

See [Architecture → Packet Bus Contracts](architecture.md#packet-bus-contracts) for the full topic and payload reference.
