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

    # Cartesia
    CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

    # Server
    PORT = int(os.getenv("PORT", "8000"))

    # Database
    # Using postgresql+psycopg which is the new psycopg3 driver (supports async)
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/dbname")

    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")

    # Email config
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")

settings = Settings()
