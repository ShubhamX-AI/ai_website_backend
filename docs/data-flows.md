# Data Flows

End-to-end feature flows for the `indusnet` agent.

## 1) Knowledge -> Flashcard Streaming

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant A as Agent LLM
    participant T as Knowledge Tool
    participant V as VectorStore (Chroma)
    participant UI as UI Publisher Tool
    participant UAG as UIAgentFunctions
    participant FE as Frontend

    U->>A: Ask company/service question
    A->>T: search_indus_net_knowledge_base(question)
    T->>V: similarity_search(query, k)
    V-->>T: docs + metadata
    T-->>A: markdown-formatted db_results

    A->>UI: publish_ui_stream(user_input, agent_response)
    UI->>UAG: query_process_stream(user_input, db_results, agent_response, user_id)
    UAG-->>UI: flashcard payloads (stream)
    UI->>FE: topic ui.flashcard (card by card)
    UI->>FE: topic ui.flashcard end_of_stream
```

## 2) Internet Search (Optional branch)

```mermaid
flowchart LR
    Q[Question requires web data] --> E[_enrich_query strips conversational fluff]
    E --> S[search_internet_knowledge]
    S --> G[SearXNG general search]
    S --> N[SearXNG news search]
    S --> I[SearXNG IT/tech search]
    G --> PG[preprocess_for_llm]
    N --> PN[preprocess_news_for_llm]
    I --> PI[preprocess_for_llm]
    PG --> R["Sectioned result: [General] + [News] + [Tech / IT]"]
    PN --> R
    PI --> R
    R --> LLM[cleaned snippets returned to LLM]
```

> All three searches run concurrently via `asyncio.gather`. The same enriched query is also used by the image search that drives flashcard visuals on the frontend.

## 3) Flashcard Media + Memory Lifecycle

```mermaid
flowchart TD
    C[Raw card JSON chunk] --> N[_normalize_card_payload]
    N --> M{media.asset_key mapped?}
    M -->|Yes| A[Resolve from MEDIA_ASSETS urls]
    M -->|No| I["search_images(query) via SearXNG"]
    A --> O[Publish flashcard]
    I --> O
    O --> B[Batch complete]
    B --> S[_save_to_memory user_id + cards JSON]
    S --> MM[(Mem0 on ChromaDB)]

    R[recall_and_republish_ui_content] --> SR[Mem0 search by user_id + query]
    SR --> RP[Re-publish saved cards with recalled=true]
```

## 4) Contact Form Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent LLM
    participant F as FormTools
    participant FE as Frontend
    participant MR as SubmissionReceipt Mail Service
    participant SMTP as SMTP

    A->>F: preview_contact_form(...)
    F->>FE: ui.contact_form type=contact_form
    FE-->>A: user confirms
    A->>F: submit_contact_form(...)
    F->>MR: send_submission_receipt(contact_form)
    MR->>SMTP: send email receipt
    F->>FE: ui.contact_form type=contact_form_submit
    F-->>A: success/fallback response
```

## 5) Job Application Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent LLM
    participant F as FormTools
    participant FE as Frontend
    participant MR as SubmissionReceipt Mail Service
    participant SMTP as SMTP

    A->>F: preview_job_application(...)
    F->>FE: ui.job_application type=job_application_preview
    FE-->>A: user confirms
    A->>F: submit_job_application(...)
    F->>MR: send_submission_receipt(job_application)
    MR->>SMTP: send email receipt
    F->>FE: ui.job_application type=job_application_submit
```

## 6) Meeting Invite Flow

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent LLM
    participant M as MeetingTools
    participant FE as Frontend
    participant CI as Calendar Invite Service
    participant SMTP as SMTP

    A->>M: preview_meeting_invite(...)
    M->>FE: ui.meeting_form type=meeting_form
    FE-->>A: explicit confirmation
    A->>M: schedule_meeting(...)
    M->>CI: send_calendar_invite(...)
    CI->>SMTP: email with ICS invite
    M->>FE: ui.meeting_form type=meeting_invite_submit (sent)
```

## 7) Location + Directions + Polyline

Two paths depending on whether the user provides a place name or asks for GPS.

**Path A — User states a place name (no GPS needed)**

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent LLM
    participant L as LocationTools
    participant GM as GoogleMapService
    participant FE as Frontend

    A->>L: calculate_distance_to_destination(destination, origin_place="Salt Lake", travel_mode="driving")
    L->>GM: geocode origin_place to coordinates
    L->>GM: computeRoutes(origin_coords, destination) + polyline
    L->>FE: ui.location_request type=map.polyline
    L-->>A: spoken distance/time summary
```

**Path B — User explicitly requests GPS location**

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent LLM
    participant L as LocationTools
    participant FE as Frontend
    participant DH as DataHandler
    participant GM as GoogleMapService

    A->>L: request_user_location()
    L->>FE: ui.location_request type=location_request
    FE->>DH: user.location status + coords/denied/unsupported
    DH->>L: set _location_event
    L->>GM: reverse geocode (on success)
    L-->>A: location result string

    A->>L: calculate_distance_to_destination(destination)
    L->>GM: computeRoutes + distance + duration + polyline
    L->>FE: ui.location_request type=map.polyline
    L-->>A: spoken distance/time summary
```

> `request_user_location` is only called when the user explicitly says "use my GPS" or "from my exact location". For all other distance/directions requests the agent asks for a place name and uses Path A.

## 8) Context Sharing (Email + WhatsApp)

```mermaid
flowchart TD
    S["send_context_email / send_context_whatsapp"] --> RS["_resolve_snapshot(screens_back)"]
    RS --> H{session snapshot exists?}
    H -->|Yes| SNAP[Use current/back snapshot]
    H -->|No + user_id| MEM[Mem0 recall fallback]
    SNAP --> CH[Compose message via LLM + fallback format]
    MEM --> CH

    CH --> E1[Email path: SMTP send]
    CH --> W1[WhatsApp path: Meta Graph API template]

    E1 --> P1[Publish ui.email_delivery status packet]
    W1 --> P2[Publish ui.whatsapp_delivery status packet]
```

## 9) End Call Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant A as Agent LLM
    participant E as end_call tool
    participant S as Agent Session

    U->>A: goodbye / end request
    A->>E: end_call()
    E->>S: context.session.shutdown()
    E-->>A: fixed farewell instruction
```
