# Tools Reference

Tool contract guide for `src/agents/indusnet/tools/*`.

## Tool Catalog

| Tool | Purpose | Required inputs | Side effects | Output shape |
|---|---|---|---|---|
| `search_indus_net_knowledge_base` | Vector DB search | `question` | Updates `self.db_results` | Markdown text results |
| `search_internet_knowledge` | Parallel web/news/IT search via SearXNG; query is auto-enriched to remove conversational fluff | `question` | Three concurrent SearXNG calls (general, news, IT); images from same query drive frontend flashcard visuals | Sectioned snippet text (`[General]`, `[News]`, `[Tech / IT]`) or no-results string |
| `publish_ui_stream` | Stream flashcards to UI | `user_input`, `agent_response` | Publishes `ui.flashcard`; stores snapshot; schedules async stream + Mem0 save | Confirmation string |
| `recall_and_republish_ui_content` | Replay prior cards from memory | `agent_response` | Mem0 read; publishes recalled cards + end marker | Success/fallback string |
| `publish_global_presence` | Show global locations | optional `user_input` | Publishes `ui.global_presense`; stores snapshot | Confirmation string |
| `publish_nearby_offices` | Show nearby office cards | `offices` list | Publishes `ui.nearby_offices`; stores snapshot | Confirmation string |
| `get_ui_history` | Show server-side UI history | none | none | newline list string |
| `preview_contact_form` | Review contact details | `user_name`, `user_email`, `user_phone`, `contact_details` | Publishes `ui.contact_form`; stores snapshot | Prompt-for-confirmation string |
| `submit_contact_form` | Final contact submit | same as preview | Sends receipt email; publishes submit packet; stores snapshot | Success/fallback string |
| `preview_job_application` | Review job application | `user_name`, `user_email`, `user_phone`, `job_details` | Publishes `ui.job_application`; stores snapshot | Prompt-for-confirmation string |
| `submit_job_application` | Final job application submit | same as preview | Sends receipt email; publishes submit packet; stores snapshot | Success/fallback string |
| `request_user_location` | Ask browser for GPS coordinates — only when user explicitly requests exact/current location | none | Publishes location request; waits for `user.location`; updates location state | Status/result string |
| `calculate_distance_to_destination` | Directions from origin to destination | `destination` (required); `origin_place` (optional — place name stated by user; omit to use GPS); `travel_mode` (optional, default `driving`) | Resolves origin via geocoding if `origin_place` provided, else uses GPS state; Google Routes call; publishes `map.polyline`; stores snapshot | Distance/time string or failure |
| `preview_meeting_invite` | Review meeting before send | `recipient_email`, `subject`, `description`, `location`, `start_time_iso`, `duration_hours?` | Publishes `ui.meeting_form`; stores snapshot | Prompt-for-confirmation string |
| `schedule_meeting` | Send final calendar invite | same as preview | Sends calendar invite; publishes sent status; stores snapshot | Success/failure string |
| `send_context_email` | Email summarized screen context | optional `recipient_email`, `screens_back?` | Snapshot resolve; SMTP send; publishes `ui.email_delivery` | Success/failure string |
| `send_context_whatsapp` | WhatsApp summarized context | `recipient_phone`, `screens_back?` | Snapshot resolve; Meta API send; publishes `ui.whatsapp_delivery` | Success/failure string |
| `get_user_info` | Push known user identity to FE | `user_name`, optional `user_email`, `user_phone` | Publishes `user.details` | Confirmation string |
| `end_call` | Graceful shutdown | none | `context.session.shutdown()` | Fixed farewell instruction |

## Preconditions and Postconditions

| Tool | Preconditions | Postconditions |
|---|---|---|
| `calculate_distance_to_destination` | Either GPS state set (via `request_user_location`) OR `origin_place` provided directly | `map.polyline` published to `ui.location_request`; distance/time summary returned |
| `schedule_meeting` | User should confirm after `preview_meeting_invite` | Invite send attempted; UI status packet published on success |
| `submit_contact_form` / `submit_job_application` | User should confirm previewed data | Submit packet sent; receipt email attempted |
| `send_context_email` / `send_context_whatsapp` | Valid recipient + available snapshot (or Mem0 fallback) | Delivery status packet published with sent/failed |
| `recall_and_republish_ui_content` | `user_id` should be present | Recalled cards re-emitted with `recalled=true` |

## Topic Contracts by Tool

| Topic | Producer tools | Payload `type` |
|---|---|---|
| `ui.flashcard` | `publish_ui_stream`, `recall_and_republish_ui_content` | `flashcard`, `end_of_stream` |
| `ui.contact_form` | `preview_contact_form`, `submit_contact_form` | `contact_form`, `contact_form_submit` |
| `ui.job_application` | `preview_job_application`, `submit_job_application` | `job_application_preview`, `job_application_submit` |
| `ui.meeting_form` | `preview_meeting_invite`, `schedule_meeting` | `meeting_form`, `meeting_invite_submit` |
| `ui.location_request` | `request_user_location`, `calculate_distance_to_destination` | `location_request`, `map.polyline` |
| `ui.global_presense` | `publish_global_presence` | `global_presence` |
| `ui.nearby_offices` | `publish_nearby_offices` | `nearby_offices` |
| `ui.email_delivery` | `send_context_email` | `context_email_delivery` |
| `ui.whatsapp_delivery` | `send_context_whatsapp` | `context_whatsapp_delivery` |
| `user.details` | `get_user_info` | user identity object |

## Failure Modes and Fallbacks

- Vector/web lookup failures: tool returns explicit failure text; no crash path expected.
- Location timeout/denial/unsupported: `request_user_location` returns explicit status and distance tool blocks until success.
- Email failures: invalid address or SMTP failure returns failure string; submit flows still complete with reference ID.
- WhatsApp failures: invalid number, template/authorization errors, or API/network failures return explicit failure string.
- Snapshot missing for email/WhatsApp: fallback attempts Mem0 recall when `user_id` exists.
- Mem0 recall/save exceptions: logged and treated as non-fatal; user gets graceful fallback response.

## Public API and Data Interfaces

- `GET /api/getToken`
  - Query: `name` (default `guest`), `user_id` (required), `email` (optional), `agent` (default `indusnet`), `room` (optional).
  - Response: plain text JWT.
  - Side effects: may create room and always creates agent dispatch for selected room.
- LiveKit data interfaces are topic-driven (see `docs/architecture.md` packet contract table).
