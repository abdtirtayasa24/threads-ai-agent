from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    AI_API_KEY: str
    AI_MODEL: str = "gemini-3.1-flash-lite"

    OPENROUTER_API_KEY: str
    IMAGE_MODEL: str = "x-ai/grok-imagine-image-quality"

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    WEBHOOK_URL: str = ""

    THREADS_USER_ID: str
    THREADS_ACCESS_TOKEN: str

    AUTO_PUBLISH: bool = False
    GENERATE_ILLUSTRATIONS: bool = True
    BASE_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"

settings = Settings()