from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    OPENAI_API_KEY: str
    AI_MODEL: str = "gemini-3.1-flash-lite"

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    WEBHOOK_URL: str = ""

    THREADS_USER_ID: str
    THREADS_ACCESS_TOKEN: str

    AUTO_PUBLISH: bool = False

    class Config:
        env_file = ".env"

settings = Settings()