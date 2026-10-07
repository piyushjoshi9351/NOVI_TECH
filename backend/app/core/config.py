from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = ../../ (the folder that contains both `backend` and `frontend`)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "NOVI API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    FRONTEND_DIR: str = str(FRONTEND_DIR)

    # --- Database (MySQL) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "novi_db"

    # --- Auth / JWT ---
    SECRET_KEY: str = "novi-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # --- Google OAuth (server-side authorization-code flow) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Must match one of the registered redirect URIs in Google Cloud Console.
    GOOGLE_REDIRECT_URI: str = ""
    # Origin the browser is redirected back to after Google sign-in completes.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Gemini ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_SYNC_DELAY: float = 4.0  # seconds between calls (free-tier friendly)
    GEMINI_TIMEOUT_SECONDS: float = 60.0

    # --- Local LLM fallback (keeps every AI feature working when Gemini is out of quota) ---
    OLLAMA_BASE_URL: str = "https://ollama.com/v1"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_API_KEY: str = ""

    # --- Letta memory (optional; falls back to Gemini-only when unreachable) ---
    LETTA_BASE_URL: str = "http://localhost:8283"
    LETTA_API_KEY: str = ""
    LETTA_ENABLED: bool = True
    LETTA_MODEL: str = "ollama/llama3.2:3b"
    LETTA_EMBEDDING: str = "ollama/nomic-embed-text:latest"

    # --- Voice onboarding (ElevenLabs) ---
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"

    # --- Internal callbacks (Letta tools) ---
    INTERNAL_SHARED_SECRET: str = ""
    INTERNAL_CALLBACK_BASE_URL: str = "http://localhost:8000"

    @property
    def database_url(self) -> str:
        encoded_password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{self.DB_USER}:{encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
