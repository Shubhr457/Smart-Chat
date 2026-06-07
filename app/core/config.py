from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Chat API"
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "smartchat"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"  # override via .env
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)


settings = Settings()
