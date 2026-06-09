from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str

    AI_API_KEY: str
    AI_MODEL: str

    OPENROUTER_API_KEY: str
    IMAGE_MODEL: str

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    WEBHOOK_URL: str

    THREADS_USER_ID: str
    THREADS_ACCESS_TOKEN: str

    AUTO_PUBLISH: bool = False
    GENERATE_ILLUSTRATIONS: bool = True
    BASE_URL: str

    class Config:
        env_file = ".env"

settings = Settings()
