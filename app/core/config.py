from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Chat API"
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "smartchat"

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

settings = Settings()
