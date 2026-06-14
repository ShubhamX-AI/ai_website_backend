# Architecture

High-level architecture for the `indusnet` voice assistant backend.

## System Context

```mermaid
flowchart LR
    C[Web Client / Frontend]
    API[FastAPI API Service\n`src/api/main.py`]
    LK[(LiveKit Server\nRooms + Agent Dispatch)]
    AG[Agent Worker\n`src/agents/session.py`]

    SST[Sarvam STT\n`saaras:v3`]
    OAI[OpenAI LLM\n`gpt-4.1`]
    STS[Sarvam TTS\n`bulbul:v3`]
    CH[(ChromaDB\ncompany_knowledge + ui_flashcard_memory)]
    SX[SearXNG]
    GM[Google Maps APIs]
    SMTP[SMTP Server]
    WA[Meta WhatsApp Graph API]

    C -->|GET /api/getToken| API
    API -->|Create room + dispatch + JWT| LK
    C -->|Join room with JWT| LK

    LK -->|Dispatch `indusnet` job| AG
    AG <--> |Audio/Text + Data Packets| LK

    AG --> SST
    AG --> OAI
    AG --> STS
    AG --> CH
    AG --> SX
    AG --> GM
    AG --> SMTP
    AG --> WA
```

## Bootstrap Sequence

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant API as FastAPI
    participant LKS as LiveKitService
    participant LK as LiveKit Server
    participant AW as Agent Worker
    participant AG as IndusNetAgent

    FE->>API: GET /api/getToken?user_id=...&name=...&agent=indusnet
    API->>LKS: create_room(agent) if room not provided
    LKS->>LK: CreateRoomRequest
    LK-->>LKS: room_name
    API->>LKS: create_agent_dispatch(room_name)
    LKS->>LK: CreateAgentDispatchRequest(agent_name="indusnet")
    API->>LKS: get_token(identity=user_id, name, metadata)
    LKS-->>API: JWT
    API-->>FE: PlainText JWT

    FE->>LK: Join room using JWT
    LK->>AW: start job entrypoint
    AW->>AG: initialize IndusNetAgent + services
    AW->>LK: bind data_received handler + start session
```

## Runtime Interaction Loop

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant FE as Frontend
    participant LK as LiveKit Room
    participant AW as AgentSession Runtime
    participant AG as IndusNetAgent

    User->>FE: speaks / asks
    FE->>LK: audio + optional text
    LK->>AW: user_state_changed(speaking)
    AW->>AW: start filler loop after 2-3s

    LK->>AW: conversation_item_added(user)
    AW->>AG: function tool calls as needed
    AG->>LK: publish UI/data packets

    LK->>AW: user_state_changed(not speaking)
    AW->>AW: cancel filler loop

    LK->>AW: conversation_item_added(assistant)
    AW->>AW: silence watchdog + idle timer updates

    LK->>AG: data_received(topic, payload)
    AG->>AG: handle_data(user.context/user.location/ui.context)
    AG->>AW: optional instruction rebuild with user context
```

## Packet Bus Contracts

### Frontend -> Backend Topics (Agent listens)

| Topic | Purpose | Key payload fields |
|---|---|---|
| `ui.context` | UI context sync (currently update flow is disabled) | `viewport`, `active_elements` |
| `user.context` | User identity sync | `user_info.user_id`, `user_info.user_name`, `user_info.user_email`, `user_info.user_phone` |
| `user.location` | Result of browser geolocation request | `status` (`success/denied/unsupported`), `latitude`, `longitude`, `accuracy`, `error` |

### Backend -> Frontend Topics (Agent publishes)

| Topic | Typical payload `type` |
|---|---|
| `ui.flashcard` | `flashcard`, `end_of_stream` |
| `ui.contact_form` | `contact_form`, `contact_form_submit` |
| `ui.job_application` | `job_application_preview`, `job_application_submit` |
| `ui.meeting_form` | `meeting_form`, `meeting_invite_submit` |
| `ui.location_request` | `location_request`, `map.polyline` |
| `ui.global_presense` | `global_presence` |
| `ui.nearby_offices` | `nearby_offices` |
| `ui.office_details` | `office_details` |
| `ui.email_delivery` | `context_email_delivery` |
| `ui.whatsapp_delivery` | `context_whatsapp_delivery` |
| `user.details` | user identity echo from `get_user_info` |

## External Interface Notes

- API token endpoint: `GET /api/getToken` returns JWT as plain text.
- Allowed `agent` query value is currently only `indusnet`.
- Runtime architecture is event-driven through LiveKit room events and function tools.
