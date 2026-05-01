import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    # LiveKit
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
    LIVEKIT_URL = os.getenv("LIVEKIT_URL")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMAIL_SUMMARY_MODEL = os.getenv("EMAIL_SUMMARY_MODEL", "gpt-4o-mini")

    # Cartesia
    CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

    # Server
    PORT = int(os.getenv("PORT", "8000"))

    # Paths
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")

    # Email config
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")

    # WhatsApp config
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "110377482141989")
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "utility_agui_agent")

    # SearXNG config
    SEARXNG_BASE_URL = os.getenv("SEARXNG_BASE_URL", "http://13.126.71.22:4000/")

    # MongoDB
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "ai_website")

    # Auth / JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    CLIENT_SESSION_HOURS: int = int(os.getenv("CLIENT_SESSION_HOURS", "4"))
    CLIENT_ACCESS_WINDOW_HOURS: int = int(os.getenv("CLIENT_ACCESS_WINDOW_HOURS", "4"))

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    # Next.js callback URL (FastAPI redirects here after Google OAuth)
    NEXTJS_CALLBACK_URL: str = os.getenv("NEXTJS_CALLBACK_URL", "http://localhost:3000/api/auth/google/callback")

    # Google OAuth domain → admin (e.g. "yourcompany.com")
    ADMIN_DOMAIN: str = os.getenv("ADMIN_DOMAIN", "intglobal.com")


settings = Settings()
