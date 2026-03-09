# Topic constants for data packet routing between frontend and backend.
# Topics the agent listens to from the frontend
FRONTEND_CONTEXT = ["ui.context", "user.context", "user.location"]

# Topics the agent publishes to the frontend
TOPIC_UI_FLASHCARD = "ui.flashcard"
TOPIC_CONTACT_FORM = "ui.contact_form"
TOPIC_USER_LOCATION = "user.location"  # frontend → backend: GPS result
TOPIC_UI_LOCATION_REQUEST = "ui.location_request"  # backend → frontend: request GPS
TOPIC_GLOBAL_PRESENCE = "ui.global_presense"
TOPIC_NEARBY_OFFICES = "ui.nearby_offices"
TOPIC_JOB_APPLICATION = "ui.job_application"
TOPIC_MEETING_FORM = "ui.meeting_form"
TOPIC_EMAIL_DELIVERY = "ui.email_delivery"
TOPIC_WHATSAPP_DELIVERY = "ui.whatsapp_delivery"


# Metadata keys to skip when formatting vector DB results
SKIPPED_METADATA_KEYS = ["source_content_focus"]
